"""Black-box checks over /plan/generate: every program combination and random edit sequences.

These tests only use the HTTP API and the catalog's printed rules (prerequisites, co-requisites,
course load), the way a student would judge a plan, not the engine's internals.
"""
import itertools
import os
import random
import re
import sys
import unittest
from collections import Counter

from fastapi.testclient import TestClient

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
for path in (BACKEND_DIR, CURRENT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from _isolation import IsolatedTestCase  # noqa: E402
from test_plan_invariants import _course_prereq_groups  # noqa: E402

import main  # noqa: E402

PLACEHOLDER_RE = re.compile(r"ELECTIVE", re.I)
COURSE_RE = re.compile(r"^[A-Z]{2,4} \d{4}$")


class _ApiCase(IsolatedTestCase):
    excel_index = "real"

    def setUp(self):
        super().setUp()
        self.client = TestClient(main.app)
        self.info = self.client.get("/catalog/load-default").json()
        self.catalog = main.getCatalogCache().default_catalog

    def _options(self, majors, minors):
        chosen = {}
        programs = [(m, "program_info") for m in majors] + [(n, "minor_info") for n in minors]
        for name, source in programs:
            options = (self.info[source].get(name) or {}).get("options")
            if options and options.get("required"):
                chosen[name] = [options["choices"][0]]
        return chosen

    def _generate(self, majors, minors, overrides=None):
        body = {
            "catalog_id": self.info["catalog_id"],
            "majors": majors,
            "minors": minors,
            "program_options": self._options(majors, minors),
            "start_term_season": "Fall",
            "start_term_year": 2027,
            "overrides": overrides,
        }
        response = self.client.post("/plan/generate", json=body)
        self.assertEqual(response.status_code, 200, response.text[:500])
        return response.json()

    def _assert_structure(self, plan, max_term_credits):
        seen = Counter()
        for term in plan["semester_plan"]:
            self.assertEqual(term["credits"], sum(c["credits"] for c in term["courses"]), term["term"])
            self.assertLessEqual(term["credits"], max_term_credits, term["term"])
            ids = Counter(c["instance_id"] for c in term["courses"])
            self.assertEqual([i for i, n in ids.items() if n > 1], [], term["term"])
            for course in term["courses"]:
                if not PLACEHOLDER_RE.search(course["code"]) and not course.get("is_retake"):
                    seen[course["code"]] += 1
        self.assertEqual({c: n for c, n in seen.items() if n > 1}, {}, "a course is planned twice")
        self.assertLessEqual(len(plan["semester_plan"]), 12)

    def _assert_catalog_order(self, plan):
        term_of = {}
        for index, term in enumerate(plan["semester_plan"]):
            for course in term["courses"]:
                term_of.setdefault(course["code"], index)
        for code, index in term_of.items():
            required, or_groups = _course_prereq_groups(self.catalog, code)
            for prereq in required:
                if prereq in term_of:
                    self.assertLess(term_of[prereq], index, f"{code} is planned with or before its prerequisite {prereq}")
            for group in or_groups:
                self.assertTrue(
                    any(option in term_of and term_of[option] < index for option in group),
                    f"{code} needs one of {sorted(group)} first",
                )
            for coreq in (self.catalog["course_meta"].get(code) or {}).get("coreq_codes") or []:
                if coreq in term_of:
                    self.assertEqual(term_of[coreq], index, f"{code} and its co-requisite {coreq} are split")


class ProgramCombinationSweepTests(_ApiCase):
    def _combinations(self):
        majors = [m for m in self.info["majors"] if m != "Self-Designed Major"]
        minors = list(self.info["minors"])
        yield from (([m], []) for m in majors)
        yield from ((list(pair), []) for pair in itertools.combinations(majors, 2))
        yield from (([m], [n]) for m in majors for n in minors if n != m)

    def test_every_untouched_plan_is_well_formed_and_valid(self):
        for majors, minors in self._combinations():
            with self.subTest(majors=majors, minors=minors):
                plan = self._generate(majors, minors)
                self._assert_structure(plan, max_term_credits=17)
                self._assert_catalog_order(plan)
                summary = plan["summary"]
                self.assertGreaterEqual(summary["projected_credits"], 120)
                self.assertEqual(
                    summary["projected_credits"],
                    sum(t["credits"] for t in plan["semester_plan"]) + summary["completed_credits"],
                )
                self.assertTrue(plan["is_valid"], plan["validation_errors"])

    def test_literature_minor_schedules_eng_2010_before_3000_level_eng(self):
        # Computer Science + Literature minor used to plan ENG 2010 in the same term as ENG 3005 (a
        # GenEd pick), so the student's untouched plan failed its own sequence rule (p.122).
        plan = self._generate(["Computer Science"], ["Literature"])
        self.assertTrue(plan["is_valid"], plan["validation_errors"])
        term_of = {c["code"]: i for i, t in enumerate(plan["semester_plan"]) for c in t["courses"]}
        later = [code for code, i in term_of.items() if code.startswith("ENG 3") or code.startswith("ENG 4")]
        self.assertTrue(later)
        self.assertTrue(all(term_of[code] > term_of["ENG 2010"] for code in later), term_of)


class RandomEditWalkTests(_ApiCase):
    PROGRAMS = [
        (["Computer Science"], []),
        (["Business Administration"], ["Finance"]),
        (["Psychology"], ["Creative Writing"]),
        (["Economics", "Mathematics"], []),
        (["European Studies"], []),
    ]
    STEPS = 10

    def _locate(self, plan, instance_id):
        for term in plan["semester_plan"]:
            for course in term["courses"]:
                if course["instance_id"] == instance_id:
                    return term["term"]
        return None

    def test_student_edits_stick_or_are_explained(self):
        rng = random.Random(20261012)
        codes = sorted(c for c in self.catalog["courses"] if COURSE_RE.match(c))
        for majors, minors in self.PROGRAMS:
            overrides = {"add": [], "remove": [], "move": []}
            placed = {}  # instance id -> term the student put it in
            removed = set()
            for step in range(self.STEPS):
                plan = self._generate(majors, minors, overrides)
                terms = [t["term"] for t in plan["semester_plan"]]
                real = [
                    (t["term"], c) for t in plan["semester_plan"] for c in t["courses"]
                    if not PLACEHOLDER_RE.search(c["code"]) and c["instance_id"] not in placed
                ]
                action = rng.choice(["move", "remove", "add"])
                if action == "move" and real:
                    term, course = rng.choice(real)
                    target = rng.choice([t for t in terms if t != term])
                    overrides["move"].append({"from_term": term, "to_term": target,
                                              "instance_id": course["instance_id"], "code": course["code"]})
                    placed[course["instance_id"]] = target
                elif action == "remove" and real:
                    term, course = rng.choice(real)
                    overrides["remove"].append({"term": term, "instance_id": course["instance_id"], "code": course["code"]})
                    removed.add(course["instance_id"])
                else:
                    instance_id = f"sweep-{step}"
                    target = rng.choice(terms)
                    overrides["add"].append({"term": target, "code": rng.choice(codes), "instance_id": instance_id})
                    placed[instance_id] = target

                plan = self._generate(majors, minors, overrides)
                warned = any(str(w.get("type", "")).startswith("OVERRIDE") for w in plan["warnings"])
                with self.subTest(majors=majors, minors=minors, step=step, action=action):
                    # Edits may push a term past 22 credits: the API reports it rather than refusing.
                    self._assert_structure(plan, max_term_credits=10_000)
                    for instance_id, term in placed.items():
                        if instance_id not in removed and not warned:
                            self.assertEqual(self._locate(plan, instance_id), term, instance_id)
                    for instance_id in removed:
                        if not warned:
                            self.assertIsNone(self._locate(plan, instance_id), instance_id)

            cached = self._generate(majors, minors, overrides)
            main.PLAN_CACHE.clear()
            fresh = self._generate(majors, minors, overrides)
            self.assertEqual(cached["semester_plan"], fresh["semester_plan"], "plans must not depend on the cache")

    def test_moved_free_elective_placeholders_stay_where_the_student_put_them(self):
        # Making room in a full semester used to take the student's own moved placeholder as the one to
        # replace; a new placeholder of the same name then appeared elsewhere, with no warning (QA F2).
        rng = random.Random(1)
        for majors, minors in self.PROGRAMS[:3]:
            overrides = {"add": [], "remove": [], "move": []}
            placed = {}  # instance id -> (term, code)
            for step in range(12):
                plan = self._generate(majors, minors, overrides)
                terms = [t["term"] for t in plan["semester_plan"]]
                candidates = [
                    (t["term"], c) for t in plan["semester_plan"] for c in t["courses"] if c["instance_id"] not in placed
                ]
                free = [p for p in candidates if p[1]["code"].startswith("FREE ELECTIVE")]
                pool = free if rng.random() < 0.7 and free else candidates
                term, course = rng.choice(pool)
                if rng.random() < 0.8:
                    target = rng.choice([t for t in terms if t != term])
                    overrides["move"].append({"from_term": term, "to_term": target,
                                              "instance_id": course["instance_id"], "code": course["code"]})
                    placed[course["instance_id"]] = (target, course["code"])
                else:
                    overrides["remove"].append({"term": term, "instance_id": course["instance_id"], "code": course["code"]})
                    placed.pop(course["instance_id"], None)
                plan = self._generate(majors, minors, overrides)
                warned = {w.get("course") for w in plan["warnings"] if str(w.get("type", "")).startswith("OVERRIDE")}
                with self.subTest(majors=majors, minors=minors, step=step):
                    for instance_id, (term, code) in placed.items():
                        if code not in warned:
                            self.assertEqual(self._locate(plan, instance_id), term, code)


if __name__ == "__main__":
    unittest.main()

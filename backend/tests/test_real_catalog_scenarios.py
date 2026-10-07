"""Generate plans for realistic students on the shipped catalog and audit them independently.

Each sweep test checks one invariant for every major at several stages (fresh student, and the same
student after completing the first N terms of their fresh plan), plus a few double-major combinations.
The targeted tests below reproduce individual bugs found on the real catalog.
"""
import os
import re
import sys
import unittest
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Set
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase, load_real_excel_index  # noqa: E402

import degree_engine  # noqa: E402
import excel_course_catalog  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import (  # noqa: E402
    _course_credits,
    _course_prereq_expr,
    _is_free_elective,
    _prereq_expr_satisfied,
    build_requirement_slots,
    generate_plan,
    select_courses_for_slots,
)

START_SEASON, START_YEAR = "Spring", 2027
MAX_CREDITS = 16
STAGES = (0, 2, 5)
COMBINATIONS = (
    (["Business Administration", "Economics"], ["Mathematics"]),
    (["Computer Science", "Mathematics"], ["Physics"]),
    (["Psychology"], ["Economics", "Philosophy"]),
)
STANDING_CREDITS = {"sophomore standing": 30, "junior standing": 60, "senior standing": 90}
COMPLETED_CREDITS_RE = re.compile(r"completion of (\d+) credits", re.IGNORECASE)


@dataclass
class Scenario:
    label: str
    majors: List[str]
    minors: List[str]
    completed: Set[str]
    stage: int
    result: Dict = field(default_factory=dict)


def _plan(catalog: Dict, majors: List[str], minors: List[str], completed: Set[str], **kwargs) -> Dict:
    return generate_plan(
        catalog=catalog,
        majors=majors,
        minors=minors,
        completed_courses=set(completed),
        max_credits_per_semester=MAX_CREDITS,
        start_term_season=START_SEASON,
        start_term_year=START_YEAR,
        **kwargs,
    )


def _real_courses(term: Dict) -> List[Dict]:
    return [c for c in term.get("courses", []) if not _is_free_elective(c["code"])]


def _completed_after(fresh: Dict, terms: int) -> Set[str]:
    return {c["code"] for term in fresh["semester_plan"][:terms] for c in _real_courses(term)}


def _min_credits_stated_in_catalog(catalog: Dict, code: str) -> int:
    text = (catalog.get("course_meta", {}).get(code, {}).get("prereq_text") or "").lower()
    required = max([credits for phrase, credits in STANDING_CREDITS.items() if phrase in text], default=0)
    for match in COMPLETED_CREDITS_RE.finditer(text):
        required = max(required, int(match.group(1)))
    return required


def _term_of(result: Dict, code: str) -> str | None:
    for term in result["semester_plan"]:
        if any(c["code"] == code for c in term["courses"]):
            return term["term"]
    return None


class RealCatalogScenarioTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        clock = patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026))
        clock.start()
        cls.addClassCleanup(clock.stop)
        cls.addClassCleanup(
            excel_course_catalog.restore_course_catalog_state,
            excel_course_catalog.snapshot_course_catalog_state(),
        )
        load_real_excel_index()

        cls.catalog = getCatalogCache().default_catalog
        cls.scenarios: List[Scenario] = []
        for major in cls.catalog["majors"]:
            fresh = _plan(cls.catalog, [major], [], set())
            for stage in STAGES:
                completed = _completed_after(fresh, stage)
                result = fresh if stage == 0 else _plan(cls.catalog, [major], [], completed)
                cls.scenarios.append(Scenario(f"{major} after {stage} terms", [major], [], completed, stage, result))
        for majors, minors in COMBINATIONS:
            result = _plan(cls.catalog, majors, minors, set())
            cls.scenarios.append(Scenario(f"{' + '.join(majors + minors)}", majors, minors, set(), 0, result))

    def _earned_before_each_term(self, scenario: Scenario) -> List[int]:
        earned = sum(_course_credits(self.catalog, code) for code in scenario.completed)
        totals = []
        for term in scenario.result["semester_plan"]:
            totals.append(earned)
            earned += term["credits"]
        return totals

    # --- Sweep invariants -------------------------------------------------------------------------

    def test_generated_plans_pass_the_engines_own_validation(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                self.assertTrue(s.result["is_valid"], s.result["validation_errors"])

    def test_plans_cover_every_requirement(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                planned = {c["code"] for t in s.result["semester_plan"] for c in _real_courses(t)}
                taken = s.completed | planned
                slots = build_requirement_slots(self.catalog, s.majors, s.minors)
                selection = select_courses_for_slots(self.catalog, slots, taken)
                unmet = sorted(
                    {sid for sid, code in selection["slot_assignment"].items() if code not in taken}
                    | set(selection["remaining_slots"])
                )
                self.assertEqual(unmet, [])

    def test_no_duplicate_courses_and_per_term_credit_limits(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                seen: Set[str] = set()
                for term in s.result["semester_plan"]:
                    self.assertLessEqual(term["credits"], MAX_CREDITS, term["term"])
                    for course in _real_courses(term):
                        self.assertNotIn(course["code"], seen | s.completed, term["term"])
                        seen.add(course["code"])

    def test_prerequisites_are_completed_in_earlier_terms(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                done = set(s.completed)
                for term in s.result["semester_plan"]:
                    for course in _real_courses(term):
                        expr = _course_prereq_expr(self.catalog, course["code"])
                        if expr:
                            self.assertTrue(
                                _prereq_expr_satisfied(expr, done),
                                f"{course['code']} in {term['term']} before its prerequisites",
                            )
                    done |= {c["code"] for c in _real_courses(term)}

    @unittest.expectedFailure  # Bug 4: senior standing / "completion of N credits" are not checked.
    def test_standing_stated_in_the_catalog_is_met(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                earned_before = self._earned_before_each_term(s)
                for idx, term in enumerate(s.result["semester_plan"]):
                    for course in _real_courses(term):
                        required = _min_credits_stated_in_catalog(self.catalog, course["code"])
                        self.assertGreaterEqual(
                            earned_before[idx],
                            required,
                            f"{course['code']} in {term['term']} needs {required} credits",
                        )

    @unittest.expectedFailure  # Bug 5: ENG 1000 parsed as needing ENG 1001; rebalance moves foundation courses.
    def test_fresh_students_take_foundation_courses_in_the_first_year(self):
        foundation = set(self.catalog.get("foundation_courses") or [])
        for s in self.scenarios:
            if s.stage != 0:
                continue
            with self.subTest(s.label):
                for idx, term in enumerate(s.result["semester_plan"]):
                    for course in _real_courses(term):
                        if course["code"] in foundation:
                            self.assertLess(idx, 2, f"{course['code']} planned for {term['term']}")
                self.assertEqual(_term_of(s.result, "ENG 1000"), _term_of(s.result, "ENG 1001"))

    @unittest.expectedFailure  # Bug 6: plans never check the graduation credit total.
    def test_plans_reach_the_graduation_credit_total(self):
        total_required = self.catalog.get("degree_total_credits") or 120
        for s in self.scenarios:
            with self.subTest(s.label):
                completed = sum(_course_credits(self.catalog, code) for code in s.completed)
                planned = sum(term["credits"] for term in s.result["semester_plan"])
                self.assertGreaterEqual(completed + planned, total_required)

    @unittest.expectedFailure  # Plan step 2.9: courses carry no structured reason yet.
    def test_every_planned_course_states_why_it_is_there(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                for term in s.result["semester_plan"]:
                    for course in _real_courses(term):
                        self.assertTrue(
                            course.get("requirements") or course.get("unlocks"),
                            f"{course['code']} in {term['term']} has no stated reason",
                        )

    # --- Targeted regressions ----------------------------------------------------------------------

    def _fresh(self, major: str) -> Dict:
        return next(s.result for s in self.scenarios if s.majors == [major] and s.stage == 0)

    @unittest.expectedFailure  # Bug 1: coverage is checked against the pre-scheduling selection.
    def test_removing_a_required_course_makes_the_plan_invalid(self):
        result = _plan(self.catalog, ["Computer Science"], [], set(), overrides={"remove": [{"code": "COS 2021"}]})
        self.assertIsNone(_term_of(result, "COS 2021"))
        self.assertFalse(result["is_valid"])
        self.assertTrue(any("COS 2021" in error or "Computer Science" in error for error in result["validation_errors"]))

    @unittest.expectedFailure  # Bug 2: the validator counted every term's credits twice.
    def test_moving_a_course_before_its_standing_is_reported(self):
        fresh = self._fresh("Business Administration")
        source = _term_of(fresh, "BUS 3000")
        target = fresh["semester_plan"][2]["term"]
        result = _plan(
            self.catalog,
            ["Business Administration"],
            [],
            set(),
            overrides={"move": [{"from_term": source, "to_term": target, "code": "BUS 3000"}]},
        )
        self.assertEqual(_term_of(result, "BUS 3000"), target)
        self.assertTrue(any("BUS 3000" in e and "junior standing" in e for e in result["validation_errors"]))

    @unittest.expectedFailure  # Bug 3: 3000/4000-level courses held back by fixed term offsets.
    def test_continuing_students_can_take_upper_level_courses_right_away(self):
        fresh = self._fresh("Computer Science")
        completed = {
            c["code"] for t in fresh["semester_plan"] for c in _real_courses(t) if c["code"] != "COS 4091"
        }
        # The CS plan's own courses come to ~85 credits; add courses from another plan to reach senior standing.
        for term in self._fresh("Economics")["semester_plan"]:
            for course in _real_courses(term):
                if sum(_course_credits(self.catalog, c) for c in completed) < 95:
                    completed.add(course["code"])
        self.assertGreaterEqual(sum(_course_credits(self.catalog, c) for c in completed), 90)
        result = _plan(self.catalog, ["Computer Science"], [], completed)
        self.assertEqual(_term_of(result, "COS 4091"), result["semester_plan"][0]["term"])

    @unittest.expectedFailure  # Bug 7: a one-term schedule was treated as permanent availability.
    def test_excel_only_courses_can_be_added_to_future_terms(self):
        result = _plan(
            self.catalog,
            ["Computer Science"],
            [],
            set(),
            overrides={"add": [{"term": "Fall 2027", "code": "BUS 4482", "instance_id": "added-bus-4482"}]},
        )
        self.assertEqual(_term_of(result, "BUS 4482"), "Fall 2027")

    @unittest.expectedFailure  # Bug 8: zero-credit policy overrides fell through to the 3-credit default.
    def test_zero_credit_policy_overrides_are_honored(self):
        self.assertEqual(_course_credits(self.catalog, "AUB 1000"), 0)
        self.assertEqual(_course_credits(self.catalog, "MAT 1001"), 0)

    @unittest.expectedFailure  # Bug 11: a restored slot (add) beat the later replace (remove) of the same id.
    def test_a_chosen_elective_can_be_swapped_for_another(self):
        fresh = self._fresh("Computer Science")
        term, slot = next(
            (t["term"], c) for t in fresh["semester_plan"] for c in t["courses"] if _is_free_elective(c["code"])
        )
        # Overrides exactly as the frontend sent them: elective A was put in the slot and removed again
        # (the slot was "restored" as an add), then elective B was put into the same slot.
        overrides = {
            "remove": [
                {"term": term, "instance_id": str(uuid.uuid4())},
                {"term": term, "code": slot["code"], "instance_id": slot["instance_id"]},
            ],
            "add": [
                {"term": term, "code": slot["code"], "instance_id": slot["instance_id"]},
                {"term": term, "code": "COS 3031", "instance_id": str(uuid.uuid4())},
            ],
        }
        result = _plan(self.catalog, ["Computer Science"], [], set(), overrides=overrides)
        term_courses = next(t["courses"] for t in result["semester_plan"] if t["term"] == term)
        self.assertIn("COS 3031", [c["code"] for c in term_courses])
        self.assertNotIn(slot["instance_id"], [c["instance_id"] for c in term_courses])


if __name__ == "__main__":
    unittest.main()

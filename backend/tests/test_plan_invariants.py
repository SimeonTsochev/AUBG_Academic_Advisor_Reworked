import os
import sys
import unittest
import random
import re

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import generate_plan  # noqa: E402

COURSE_RE = re.compile(r"^[A-Z]{2,4}\s\d{4}$")
OR_GROUP_RE = re.compile(
    r"(?:[A-Z]{2,4}\s?\d{3,4})(?:\s*(?:/|OR)\s*(?:[A-Z]{2,4}\s?\d{3,4}))+"
)


def _normalize_code(code: str) -> str:
    code = code.strip().upper()
    m = re.match(r"^([A-Z]{2,4})\s?(\d{3,4})$", code)
    if not m:
        return code
    return f"{m.group(1)} {m.group(2)}"


def _extract_or_groups(text: str) -> list[list[str]]:
    if not text:
        return []
    groups = []
    for match in OR_GROUP_RE.finditer(text.upper()):
        codes = [_normalize_code(c) for c in re.findall(r"[A-Z]{2,4}\s?\d{3,4}", match.group(0))]
        if len(set(codes)) >= 2:
            groups.append(codes)
    return groups


def _course_prereq_groups(catalog: dict, code: str) -> tuple[set[str], list[set[str]]]:
    meta = catalog.get("course_meta", {}).get(code, {}) or {}
    prereq_text = meta.get("prereq_text") or ""
    prereq_codes = {_normalize_code(c) for c in meta.get("prereq_codes", []) if isinstance(c, str)}
    if not prereq_codes:
        return set(), []
    raw_groups = _extract_or_groups(prereq_text)
    grouped: list[set[str]] = []
    grouped_codes: set[str] = set()
    for group in raw_groups:
        filtered = {_normalize_code(c) for c in group if _normalize_code(c) in prereq_codes}
        if len(filtered) >= 2:
            grouped.append(filtered)
            grouped_codes |= filtered
    required = prereq_codes - grouped_codes
    return required, grouped


def _minimal_prereqs_for_course(
    catalog: dict,
    code: str,
    prefer_set: set[str],
    completed: set[str],
    memo: dict,
    visiting: set[str],
) -> set[str]:
    if code in memo:
        return memo[code]
    if code in visiting:
        return set()
    visiting.add(code)
    catalog_courses = set(catalog.get("courses", {}).keys())
    required, or_groups = _course_prereq_groups(catalog, code)
    chosen = set(required)
    for group in or_groups:
        options = [c for c in group if c in catalog_courses]
        if not options:
            continue
        preferred = [c for c in options if c in prefer_set or c in completed]
        if preferred:
            options = preferred
        best = None
        best_cost = None
        for opt in options:
            opt_prereqs = _minimal_prereqs_for_course(
                catalog, opt, prefer_set, completed, memo, visiting
            )
            cost = 0 if opt in prefer_set or opt in completed else 1
            cost += len([p for p in opt_prereqs if p not in prefer_set and p not in completed])
            if best_cost is None or cost < best_cost or (cost == best_cost and opt < (best or "")):
                best_cost = cost
                best = opt
        if best:
            chosen.add(best)
    result = set()
    for prereq in chosen:
        if prereq in completed or prereq not in catalog_courses:
            continue
        result.add(prereq)
        result |= _minimal_prereqs_for_course(catalog, prereq, prefer_set, completed, memo, visiting)
    visiting.remove(code)
    memo[code] = result
    return result


def _expand_prereqs_minimal(catalog: dict, required: set[str], completed: set[str], prefer_set: set[str]) -> set[str]:
    memo: dict = {}
    visiting: set[str] = set()
    needed: set[str] = set()
    for code in sorted(required):
        needed |= _minimal_prereqs_for_course(catalog, code, prefer_set, completed, memo, visiting)
    return needed - required - completed


def build_random_catalog() -> dict:
    courses = {
        "AAA 1000": {"name": "Alpha I", "credits": 3, "gen_ed": []},
        "AAA 2000": {"name": "Alpha II", "credits": 3, "gen_ed": []},
        "BBB 1000": {"name": "Beta I", "credits": 3, "gen_ed": []},
        "BBB 2000": {"name": "Beta II", "credits": 3, "gen_ed": []},
        "CCC 1000": {"name": "Arts", "credits": 3, "gen_ed": ["Arts"]},
        "DDD 1000": {"name": "SocSci", "credits": 3, "gen_ed": ["Social Science"]},
        "ENG 1000": {"name": "Writing", "credits": 3, "gen_ed": ["First-Year Writing"]},
        "MAT 1000": {"name": "Quant", "credits": 3, "gen_ed": ["Quantitative Reasoning"]},
    }
    course_meta = {
        "AAA 1000": {"credits": 3, "prereq_codes": []},
        "AAA 2000": {
            "credits": 3,
            "prereq_codes": ["AAA 1000", "BBB 1000"],
            "prereq_text": "Prerequisite: AAA 1000 or BBB 1000.",
        },
        "BBB 1000": {"credits": 3, "prereq_codes": []},
        "BBB 2000": {"credits": 3, "prereq_codes": ["BBB 1000"], "prereq_text": "Prerequisite: BBB 1000."},
        "CCC 1000": {"credits": 3, "prereq_codes": []},
        "DDD 1000": {"credits": 3, "prereq_codes": []},
        "ENG 1000": {"credits": 3, "prereq_codes": []},
        "MAT 1000": {"credits": 3, "prereq_codes": []},
    }
    gen_ed_categories = {
        "Arts": ["CCC 1000"],
        "Social Science": ["DDD 1000"],
        "First-Year Writing": ["ENG 1000"],
        "Quantitative Reasoning": ["MAT 1000"],
    }
    gen_ed_rules = {k: 1 for k in gen_ed_categories.keys()}
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Alpha": {"required_courses": ["AAA 2000"], "elective_requirements": []},
            "Beta": {"required_courses": ["BBB 2000"], "elective_requirements": []},
        },
        "minors": {
            "Alpha Minor": {"required_courses": ["AAA 1000"], "elective_requirements": []},
            "Beta Minor": {"required_courses": ["BBB 1000"], "elective_requirements": []},
        },
        "foundation_courses": ["ENG 1000", "MAT 1000"],
        "gen_ed": {"categories": gen_ed_categories, "rules": gen_ed_rules},
    }


def build_filler_catalog() -> dict:
    courses = {
        "AAA 1000": {"name": "Alpha", "credits": 3, "gen_ed": []},
    }
    course_meta = {
        "AAA 1000": {"credits": 3, "prereq_codes": []},
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Alpha": {"required_courses": ["AAA 1000"], "elective_requirements": []},
        },
        "minors": {},
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }


class PlanInvariantTests(unittest.TestCase):
    def test_no_unjustified_real_courses(self):
        catalog = build_random_catalog()
        majors = list(catalog["majors"].keys())
        minors = list(catalog["minors"].keys())
        rng = random.Random(7)
        combos = []
        for _ in range(5):
            combos.append((
                [rng.choice(majors)],
                rng.sample(minors, k=rng.randint(0, len(minors))),
            ))

        allowed_reasons = {
            "MAJOR_REQUIRED",
            "MINOR_REQUIRED",
            "GENED_REQUIRED",
            "PREREQ_FOR_REQUIRED",
        }

        for majors_sel, minors_sel in combos:
            plan = generate_plan(
                catalog=catalog,
                majors=majors_sel,
                minors=minors_sel,
                completed_courses=set(),
                max_credits_per_semester=16,
                start_term_season="Fall",
                start_term_year=2025,
            )
            direct_required = set()
            for m in majors_sel:
                direct_required |= set(catalog["majors"][m]["required_courses"])
            for m in minors_sel:
                direct_required |= set(catalog["minors"][m]["required_courses"])
            for term in plan["semester_plan"]:
                for course in term["courses"]:
                    if course.get("source_reason") == "GENED_REQUIRED":
                        direct_required.add(course.get("code"))
            completed = set(plan.get("completed_courses", []))
            prefer_set = set(direct_required) | completed
            needed_prereqs = _expand_prereqs_minimal(
                catalog,
                required=direct_required - completed,
                completed=completed,
                prefer_set=prefer_set,
            )
            allowed_auto = (direct_required - completed) | needed_prereqs

            for term in plan["semester_plan"]:
                for course in term["courses"]:
                    code = course.get("code", "")
                    if COURSE_RE.match(code):
                        self.assertIn(course.get("source_reason"), allowed_reasons)
                        self.assertIn(code, allowed_auto)

    def test_no_real_filler(self):
        catalog = build_filler_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        filler_seen = False
        for term in plan["semester_plan"]:
            for course in term["courses"]:
                code = course.get("code", "")
                if course.get("source_reason") == "FREE_ELECTIVE_PLACEHOLDER":
                    filler_seen = True
                    self.assertTrue(code.startswith("FREE ELECTIVE"))
        self.assertTrue(filler_seen)

    def test_program_separation(self):
        catalog = build_random_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=["Beta Minor"],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        required_program = set(catalog["majors"]["Alpha"]["required_courses"])
        required_program |= set(catalog["minors"]["Beta Minor"]["required_courses"])
        for term in plan["semester_plan"]:
            for course in term["courses"]:
                if course.get("type") == "PROGRAM":
                    self.assertIn(course.get("code"), required_program)


if __name__ == "__main__":
    unittest.main()

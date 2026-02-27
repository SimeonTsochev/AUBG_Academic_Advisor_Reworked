import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import generate_plan  # noqa: E402
from models import GeneratePlanResponse  # noqa: E402


def build_tiny_catalog() -> dict:
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


class PlanWarningSerializationTests(unittest.TestCase):
    def test_term_credit_warning_serializes(self):
        catalog = build_tiny_catalog()
        overrides = {
            "add": [{"term": "Fall 2026", "code": "FREE ELECTIVE 99"}],
            "remove": [],
            "move": [],
        }
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides=overrides,
        )
        response = GeneratePlanResponse(
            catalog_id="test",
            **plan,
        )
        term_warnings = [w for w in response.warnings if w.type == "TERM_CREDITS_EXCEED_MAX"]
        self.assertTrue(term_warnings)
        self.assertIsNone(term_warnings[0].course)

    def test_no_duplicate_free_elective_codes(self):
        catalog = build_tiny_catalog()
        overrides = {
            "add": [],
            "remove": [{"term": "Fall 2026", "code": "AAA 1000"}],
            "move": [],
        }
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides=overrides,
        )
        codes = [c["code"] for term in plan["semester_plan"] for c in term["courses"]]
        free_codes = [code for code in codes if code.startswith("FREE ELECTIVE")]
        self.assertEqual(len(free_codes), len(set(free_codes)))


if __name__ == "__main__":
    unittest.main()

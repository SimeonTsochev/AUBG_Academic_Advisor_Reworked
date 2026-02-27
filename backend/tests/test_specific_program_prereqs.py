import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import generate_plan  # noqa: E402


def build_bus_eco_catalog():
    courses = {
        "BUS 2020": {"name": "Accounting I", "credits": 3, "gen_ed": []},
        "BUS 2021": {"name": "Accounting II", "credits": 3, "gen_ed": []},
        "ENT 2020": {"name": "Accounting for Entrepreneurs", "credits": 3, "gen_ed": []},
        "ECO 2000": {"name": "Microeconomics", "credits": 3, "gen_ed": []},
        "ECO 3000": {"name": "Quant Methods", "credits": 3, "gen_ed": []},
    }
    course_meta = {
        "BUS 2020": {"credits": 3, "prereq_codes": []},
        "BUS 2021": {
            "credits": 3,
            "prereq_codes": ["BUS 2020", "ENT 2020"],
            "prereq_text": "Prerequisite: BUS 2020 (or ENT 2020).",
        },
        "ENT 2020": {"credits": 3, "prereq_codes": []},
        "ECO 2000": {"credits": 3, "prereq_codes": []},
        "ECO 3000": {"credits": 3, "prereq_codes": []},
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Business Administration": {
                "required_courses": ["BUS 2020", "BUS 2021"],
                "elective_requirements": [],
            }
        },
        "minors": {
            "Economics": {
                "required_courses": ["ECO 2000"],
                "elective_requirements": [],
            }
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }


class SpecificProgramPrereqTests(unittest.TestCase):
    def test_bus_major_eco_minor_does_not_include_eco3000(self):
        catalog = build_bus_eco_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Business Administration"],
            minors=["Economics"],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        scheduled = {c["code"] for term in plan["semester_plan"] for c in term["courses"]}
        self.assertIn("ECO 2000", scheduled)
        self.assertNotIn("ECO 3000", scheduled)

    def test_bus2021_prereq_prefers_bus2020_over_ent2020(self):
        catalog = build_bus_eco_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        scheduled = {c["code"] for term in plan["semester_plan"] for c in term["courses"]}
        self.assertIn("BUS 2021", scheduled)
        self.assertIn("BUS 2020", scheduled)
        self.assertNotIn("ENT 2020", scheduled)


if __name__ == "__main__":
    unittest.main()

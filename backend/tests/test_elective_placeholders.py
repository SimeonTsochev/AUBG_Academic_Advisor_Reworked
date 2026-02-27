import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from catalog_parser import extract_program_requirements  # noqa: E402
from degree_engine import generate_plan  # noqa: E402


def build_min_catalog():
    courses = {
        "BUS 1100": {"name": "Intro", "credits": 4, "gen_ed": []},
        "BUS 2100": {"name": "OOP", "credits": 4, "gen_ed": []},
        "BUS 2200": {"name": "Systems", "credits": 4, "gen_ed": []},
        "MAT 1000": {"name": "College Algebra", "credits": 3, "gen_ed": ["Quantitative Reasoning"]},
        "ENG 1000": {"name": "English", "credits": 3, "gen_ed": ["First-Year Writing"]},
    }
    course_meta = {
        "BUS 1100": {"credits": 4, "prereq_codes": []},
        "BUS 2100": {"credits": 4, "prereq_codes": []},
        "BUS 2200": {"credits": 4, "prereq_codes": []},
        "MAT 1000": {"credits": 3, "gen_ed": "Quantitative Reasoning", "prereq_codes": []},
        "ENG 1000": {"credits": 3, "gen_ed": "First-Year Writing", "prereq_codes": []},
    }
    gen_ed_categories = {
        "Quantitative Reasoning": ["MAT 1000"],
        "First-Year Writing": ["ENG 1000"],
    }
    gen_ed_rules = {"Quantitative Reasoning": 1, "First-Year Writing": 1}
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {},
        "minors": {},
        "foundation_courses": ["ENG 1000", "MAT 1000"],
        "gen_ed": {"categories": gen_ed_categories, "rules": gen_ed_rules},
    }


class ElectivePlaceholderTests(unittest.TestCase):
    def test_elective_free_text_placeholder(self):
        text = """
        BUSINESS
        Required Courses
        BUS 1100
        Elective Courses
        Nine credit hours out of any additional 3000- and 4000-level BUS courses.
        """
        reqs = extract_program_requirements(text, ["Business"])
        cs = reqs["Business"]
        self.assertIn("BUS 1100", cs["required_courses"])
        self.assertEqual(len(cs["elective_requirements"]), 1)
        block = cs["elective_requirements"][0]
        self.assertEqual(block.get("credits_required"), 9)
        self.assertEqual(block.get("allowed_courses", []), [])
        self.assertTrue(block.get("rule_text"))

    def test_elective_list_placeholder_with_allowed_courses(self):
        text = """
        BUSINESS
        Required Courses
        BUS 1100
        Elective Courses (6 credit hours)
        Choose from the following:
        BUS 2100 BUS 2200
        """
        reqs = extract_program_requirements(text, ["Business"])
        cs = reqs["Business"]
        block = cs["elective_requirements"][0]
        self.assertEqual(block.get("credits_required"), 6)
        self.assertIn("BUS 2100", block.get("allowed_courses", []))
        self.assertIn("BUS 2200", block.get("allowed_courses", []))

    def test_required_choice_moves_to_elective_placeholder(self):
        text = """
        ECONOMICS
        Required Courses
        ECO 1000
        Choose two of the following:
        ECO 3001 ECO 3002 ECO 3003
        """
        reqs = extract_program_requirements(text, ["Economics"])
        econ = reqs["Economics"]
        self.assertIn("ECO 1000", econ["required_courses"])
        self.assertNotIn("ECO 3001", econ["required_courses"])
        self.assertEqual(len(econ["elective_requirements"]), 1)
        block = econ["elective_requirements"][0]
        self.assertIn("ECO 3001", block.get("allowed_courses", []))
    def test_minor_elective_placeholder(self):
        text = """
        ECONOMICS
        Required Courses
        ECO 1000
        Elective Courses
        Three courses out of the following list.
        ECO 2000 ECO 3000
        """
        reqs = extract_program_requirements(text, ["Economics"])
        econ = reqs["Economics"]
        self.assertEqual(len(econ["elective_requirements"]), 1)
        block = econ["elective_requirements"][0]
        self.assertEqual(block.get("courses_required"), 3)
        self.assertIn("ECO 2000", block.get("allowed_courses", []))

    def test_generate_plan_does_not_auto_pick_electives(self):
        catalog = build_min_catalog()
        catalog["majors"] = {
            "Business": {
                "required_courses": ["BUS 1100"],
                "elective_requirements": [
                    {
                        "id": "business-elective-1",
                        "label": "Elective Courses",
                        "credits_required": 6,
                        "courses_required": None,
                        "allowed_courses": ["BUS 2100", "BUS 2200"],
                        "rule_text": "Choose electives",
                    }
                ],
            }
        }
        plan = generate_plan(
            catalog=catalog,
            majors=["Business"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        scheduled_codes = {c["code"] for term in plan["semester_plan"] for c in term["courses"]}
        self.assertIn("BUS 1100", scheduled_codes)
        self.assertNotIn("BUS 2100", scheduled_codes)
        self.assertNotIn("BUS 2200", scheduled_codes)
        self.assertTrue(plan.get("elective_placeholders"))

    def test_generate_plan_has_no_free_fillers(self):
        catalog = build_min_catalog()
        catalog["majors"] = {
            "Business": {
                "required_courses": ["BUS 1100"],
                "elective_requirements": [],
            }
        }
        plan = generate_plan(
            catalog=catalog,
            majors=["Business"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        free_seen = False
        for term in plan["semester_plan"]:
            for course in term["courses"]:
                code = course.get("code", "")
                if code.startswith("FREE ELECTIVE"):
                    free_seen = True
                    self.assertEqual(course.get("type"), "FREE_ELECTIVE")
                    self.assertEqual(course.get("source_reason"), "FREE_ELECTIVE_PLACEHOLDER")
        # We expect at least one filler since only one 4-credit course is required.
        self.assertTrue(free_seen)

    def test_free_elective_codes_are_placeholders(self):
        catalog = build_min_catalog()
        catalog["majors"] = {
            "Business": {
                "required_courses": ["BUS 1100"],
                "elective_requirements": [],
            }
        }
        plan = generate_plan(
            catalog=catalog,
            majors=["Business"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        for term in plan["semester_plan"]:
            for course in term["courses"]:
                code = course.get("code", "")
                if course.get("type") == "FREE_ELECTIVE":
                    self.assertTrue(code.startswith("FREE ELECTIVE"))
                    self.assertNotRegex(code, r"^[A-Z]{2,4}\s\d{4}$")
                    self.assertEqual(course.get("source_reason"), "FREE_ELECTIVE_PLACEHOLDER")
                if code.startswith("FREE ELECTIVE"):
                    self.assertRegex(code, r"^FREE ELECTIVE\s\d+$")


if __name__ == "__main__":
    unittest.main()

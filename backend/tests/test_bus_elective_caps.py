import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from catalog_parser import extract_program_requirements  # noqa: E402
from degree_engine import compute_elective_recommendations, generate_plan  # noqa: E402


BUS_NON_BUS = {"EUR 3003", "EUR 3020", "JMC 2020", "JMC 3070", "JMC 3089", "SUS 3001", "SUS 4500"}


def _course_entry(code: str) -> dict:
    return {"name": code, "credits": 3, "gen_ed": []}


def _course_meta_entry() -> dict:
    return {"credits": 3, "prereq_codes": []}


def build_bus_jmc_catalog(with_excel: bool = False) -> dict:
    codes = [
        "BUS 1001",
        "BUS 3001",
        "BUS 4090",
        "BUS 4091",
        "ENT 3001",
        "JMC 2020",
        "JMC 3070",
        "JMC 3089",
    ]
    courses = {code: _course_entry(code) for code in codes}
    course_meta = {code: _course_meta_entry() for code in codes}
    catalog = {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Business Administration": {
                "required_courses": ["BUS 1001"],
                "elective_requirements": [
                    {
                        "id": "business-administration-elective-1",
                        "label": "Elective Courses",
                        "credits_required": 9,
                        "courses_required": None,
                        "allowed_courses": [],
                        "rule_text": "Business Administration major electives: 9 credits required.",
                        "is_total": True,
                    }
                ],
            },
            "Journalism and Mass Communication": {
                "required_courses": ["JMC 2020", "JMC 3070"],
                "elective_requirements": [],
            },
        },
        "minors": {},
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }
    if with_excel:
        catalog["excel_catalog"] = {
            "courses": [],
            "codes": set(codes),
            "by_code": {
                "JMC 2020": {"tags": ["BUS Major Elective"]},
                "JMC 3070": {"tags": ["BUS Major Elective"]},
                "JMC 3089": {"tags": ["BUS Major Elective"]},
                "BUS 3001": {"tags": ["BUS Major Elective"]},
                "ENT 3001": {"tags": ["BUS Major Elective"]},
            },
        }
    return catalog


class BusinessAdministrationElectiveCapTests(unittest.TestCase):
    def test_business_admin_electives_are_structured_in_parser(self):
        text = """
        Major Programs
        Business Administration
        Required Courses
        BUS 1001
        Elective Courses (9 credit hours)
        Courses
        """
        reqs = extract_program_requirements(
            text,
            ["Business Administration"],
            section_hint="major",
        )
        bus = reqs["Business Administration"]
        blocks = bus["elective_requirements"]

        self.assertEqual(len(blocks), 4)
        self.assertEqual(blocks[0].get("credits_required"), 9)
        self.assertTrue(blocks[0].get("is_total"))

        non_bus_block = blocks[1]
        self.assertEqual(non_bus_block.get("credits_required"), 3)
        self.assertEqual(set(non_bus_block.get("allowed_courses", [])), BUS_NON_BUS)

        thesis_block = blocks[2]
        self.assertEqual(thesis_block.get("credits_required"), 3)
        self.assertEqual(set(thesis_block.get("allowed_courses", [])), {"BUS 4090", "BUS 4091", "BUS 4092"})

        upper_block = blocks[3]
        self.assertIn("BUS/ENT 3000-4000", upper_block.get("rule_text", ""))

    def test_bus_jmc_only_one_jmc_course_counts_for_bus_electives(self):
        catalog = build_bus_jmc_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Business Administration", "Journalism and Mass Communication"],
            minors=[],
            completed_courses={"BUS 1001", "JMC 2020", "JMC 3070"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        major_progress = plan["category_progress"]["majors"]
        bus_progress = major_progress["Business Administration"]
        jmc_progress = major_progress["Journalism and Mass Communication"]

        self.assertEqual(bus_progress["required"], 12)
        self.assertEqual(bus_progress["completed"], 6)
        self.assertEqual(jmc_progress["required"], 6)
        self.assertEqual(jmc_progress["completed"], 6)

    def test_non_bus_and_thesis_caps_do_not_overcount_bus_electives(self):
        catalog = build_bus_jmc_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            completed_courses={
                "BUS 1001",
                "BUS 3001",
                "BUS 4090",
                "BUS 4091",
                "ENT 3001",
                "JMC 2020",
                "JMC 3070",
            },
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        bus_progress = plan["category_progress"]["majors"]["Business Administration"]
        self.assertEqual(bus_progress["required"], 12)
        self.assertEqual(bus_progress["completed"], 12)

    def test_recommendations_limit_bus_non_bus_candidates(self):
        catalog = build_bus_jmc_catalog(with_excel=True)
        recs = compute_elective_recommendations(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            completed_courses=set(),
            planned_courses=[],
            limit=30,
        )
        codes = [entry["code"] for entry in recs]
        non_bus_count = len([code for code in codes if code in BUS_NON_BUS])
        self.assertLessEqual(non_bus_count, 1)
        self.assertIn("BUS 3001", codes)

        plan = generate_plan(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            completed_courses={"BUS 1001"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        planned_non_bus = [code for code in (plan.get("elective_course_codes") or []) if code in BUS_NON_BUS]
        self.assertLessEqual(len(planned_non_bus), 1)


if __name__ == "__main__":
    unittest.main()

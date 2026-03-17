import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import generate_plan  # noqa: E402


class PsychologyRequiredCourseRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = getCatalogCache().default_catalog

    def test_psychology_lower_level_required_courses_have_explicit_intro_prereqs(self):
        for code in ("PSY 2002", "PSY 2003", "PSY 2004", "PSY 2005"):
            meta = self.catalog.get("course_meta", {}).get(code, {})
            prereq_codes = set(meta.get("prereq_codes") or [])
            self.assertEqual(prereq_codes, {"PSY 1001", "PSY 1002"})
            self.assertNotIn("ALL 1000", prereq_codes)

    def test_psychology_required_courses_are_scheduled_for_sample_student(self):
        plan = generate_plan(
            catalog=self.catalog,
            majors=["Business Administration", "Psychology"],
            minors=["Modern Languages and Cultures"],
            completed_courses={
                "ECO 1001",
                "ECO 1002",
                "ENG 1000",
                "ENG 1001",
                "ENG 1002",
                "FAR 2300",
                "MAT 1000",
                "MAT 1003",
                "PHI 2020",
                "PSY 1001",
                "PSY 1002",
                "STA 1005",
            },
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )

        scheduled = {
            course["code"]
            for term in plan["semester_plan"]
            for course in term["courses"]
        }

        for code in ("PSY 2000", "PSY 2002", "PSY 2003", "PSY 2004", "PSY 2005"):
            self.assertIn(code, scheduled)


if __name__ == "__main__":
    unittest.main()

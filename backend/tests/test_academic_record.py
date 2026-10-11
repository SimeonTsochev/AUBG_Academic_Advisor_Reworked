"""GPA, honors and course-load rules (AY 2026-27 catalog pp.59-60, 65-66)."""
import os
import sys
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

import degree_engine  # noqa: E402
from academic_record import academic_record, honors_outlook, latest_grades  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import build_requirement_slots, generate_plan  # noqa: E402


def grade(code, letter, term="Fall 2025"):
    return {"code": code, "grade": letter, "term": term}


class AcademicRecordTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = getCatalogCache().default_catalog

    def _record(self, grades, majors=(), semester_plan=(), earned=0, options=None):
        slots = build_requirement_slots(self.catalog, list(majors), [], program_options=options)
        return academic_record(
            self.catalog,
            grades=grades,
            majors=list(majors),
            slots=slots,
            elective_progress=[],
            semester_plan=list(semester_plan),
            earned_credits=earned,
        )

    def test_gpa_weights_grades_by_credits(self):
        # ENG 1001 is 4 credits, STA 1005 is 3: (4 * 4.0 + 3 * 3.0) / 7.
        _, record = self._record([grade("ENG 1001", "A"), grade("STA 1005", "B")])
        self.assertEqual(record["gpa"], 3.571)
        self.assertEqual(record["attempted_credits"], 7)

    def test_a_retake_replaces_the_earlier_grade(self):
        latest = latest_grades(self.catalog, [grade("STA 1005", "F", "Fall 2025"), grade("STA 1005", "A", "Spring 2026")])
        self.assertEqual(latest["STA 1005"]["grade"], "A")
        latest = latest_grades(self.catalog, [grade("STA 1005", "A", "Spring 2026"), grade("STA 1005", "F", "Fall 2025")])
        self.assertEqual(latest["STA 1005"]["grade"], "A")

    def test_pass_and_withdrawal_are_not_in_gpa_but_x_is_zero(self):
        _, record = self._record([grade("STA 1005", "A"), grade("ECO 1001", "P"), grade("ECO 1002", "W")])
        self.assertEqual((record["gpa"], record["attempted_credits"]), (4.0, 3))
        _, record = self._record([grade("STA 1005", "A"), grade("ECO 1001", "X")])
        self.assertEqual(record["gpa"], 2.0)

    def test_deans_and_presidents_lists(self):
        grades = [
            grade("STA 1005", "A", "Fall 2025"), grade("ECO 1001", "A-", "Fall 2025"),
            grade("ECO 1002", "A", "Spring 2026"), grade("BUS 1001", "W", "Spring 2026"),
        ]
        _, record = self._record(grades)
        self.assertEqual([t["deans_list"] for t in record["terms"]], [True, False])
        self.assertFalse(record["presidents_list"])
        _, record = self._record(grades[:3])
        self.assertTrue(record["presidents_list"])

    def test_honors_outlook(self):
        outlook = honors_outlook(3.4, 60, 204.0, 60)
        self.assertIsNone(outlook["current"])
        self.assertEqual(outlook["next"]["name"], "Cum Laude")
        self.assertEqual(outlook["next"]["needed_average"], 3.6)
        self.assertTrue(outlook["next"]["reachable"])
        outlook = honors_outlook(3.8, 100, 380.0, 20)
        self.assertEqual(outlook["current"], "Magna Cum Laude")
        self.assertEqual(outlook["next"]["name"], "Summa Cum Laude")
        self.assertFalse(honors_outlook(2.0, 110, 220.0, 10)["next"]["reachable"])

    def test_gpa_in_major_below_minimum(self):
        grades = [grade("ECO 1001", "C-"), grade("ECO 1002", "D"), grade("STA 1005", "A")]
        errors, record = self._record(grades, majors=["Economics"])
        economics = record["majors"][0]
        self.assertEqual(economics["courses"], ["ECO 1001", "ECO 1002"])
        self.assertLess(economics["gpa"], 2.5)
        self.assertTrue(any("GPA in the Economics major" in e for e in errors))

    def test_collateral_language_courses_are_not_in_the_major_gpa(self):
        grades = [grade("EUR 1011", "A"), grade("MLL 1015", "F")]
        errors, record = self._record(grades, majors=["European Studies"], options={"European Studies": ["French"]})
        self.assertEqual(record["majors"][0]["courses"], ["EUR 1011"])
        self.assertFalse(any("European Studies major is" in e for e in errors))

    def test_overload_rules(self):
        term = [{"term": "Fall 2026", "credits": 18, "courses": []}]
        errors, _ = self._record([], semester_plan=term, earned=0)
        self.assertTrue(any("first-year students" in e for e in errors))
        errors, record = self._record([grade("STA 1005", "B")], semester_plan=term, earned=40)
        self.assertTrue(any("3.300" in e for e in errors))
        self.assertEqual(record["max_load"], 17)
        errors, record = self._record([grade("STA 1005", "A")], semester_plan=term, earned=40)
        self.assertEqual(errors, [])
        self.assertEqual(record["max_load"], 19)
        errors, _ = self._record([grade("STA 1005", "A")], semester_plan=[{"term": "Fall 2026", "credits": 20}], earned=40)
        self.assertTrue(any("Dean of Faculty" in e for e in errors))

    def test_an_overload_without_grades_asks_for_the_transcript(self):
        errors, _ = self._record([], semester_plan=[{"term": "Fall 2027", "credits": 18}], earned=40)
        self.assertEqual(len(errors), 1)
        self.assertIn("Import your transcript", errors[0])

    def test_nobody_takes_more_than_22_credits(self):
        errors, _ = self._record([grade("STA 1005", "A")], semester_plan=[{"term": "Fall 2027", "credits": 23}], earned=40)
        self.assertEqual(len(errors), 1)
        self.assertIn("more than 22 credits", errors[0])

    def test_overloads_are_one_error_per_rule_and_first_year_comes_first(self):
        terms = [{"term": t, "credits": 20} for t in ("Fall 2026", "Spring 2027", "Fall 2027")]
        errors, _ = self._record([grade("STA 1005", "C")], semester_plan=terms, earned=10)
        # Fall 2026 starts with 10 earned credits (first year); after it the student has 30.
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("Fall 2026 has more than 17 credits; first-year students"))
        self.assertTrue(errors[1].startswith("Spring 2027 and Fall 2027 have more than 19 credits"))

    def test_generate_plan_returns_the_record(self):
        with patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026)):
            plan = generate_plan(
                catalog=self.catalog,
                majors=["Economics"],
                minors=[],
                completed_courses={"STA 1005", "ECO 1001"},
                start_term_season="Fall",
                start_term_year=2026,
                grades=[grade("STA 1005", "A"), grade("ECO 1001", "B+")],
            )
        record = plan["academic_record"]
        self.assertTrue(record["has_grades"])
        self.assertEqual(record["gpa"], round((3 * 4.0 + 3 * 3.33) / 6, 3))
        self.assertEqual(record["majors"][0]["courses"], ["ECO 1001"])
        self.assertGreater(record["remaining_credits"], 0)

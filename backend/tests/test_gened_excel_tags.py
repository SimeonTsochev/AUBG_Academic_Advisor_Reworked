import os
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import build_requirement_slots, generate_plan, select_courses_for_slots  # noqa: E402
from excel_course_catalog import load_course_catalog  # noqa: E402


def _write_excel_course_universe(rows: list[list[object]]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Department", "Course", "Label", "Area of Study", "Course Notes"])
    for row in rows:
        ws.append(row)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()
    wb.save(tmp.name)
    return Path(tmp.name)


class GenEdExcelTagsTests(unittest.TestCase):
    def test_excel_only_completed_course_counts_for_all_tagged_gened_categories(self):
        path = _write_excel_course_universe([
            [
                "SCI",
                "1010",
                "Integrated Science",
                "Quantitative Reasoning; Scientific Investigation",
                "",
            ],
        ])
        try:
            load_course_catalog(path)
            catalog = {
                "courses": {},
                "course_meta": {},
                "majors": {},
                "minors": {},
                "foundation_courses": [],
                "gen_ed": {
                    "categories": {
                        "Quantitative Reasoning": [],
                        "Scientific Investigation": [],
                    },
                    "rules": {
                        "Quantitative Reasoning": 1,
                        "Scientific Investigation": 1,
                    },
                },
                "excel_catalog": {"loaded": True},
            }

            slots = build_requirement_slots(catalog, majors=[], minors=[])
            selection = select_courses_for_slots(catalog, slots, {"SCI 1010"})

            self.assertEqual(selection["remaining_slots"], set())
            assigned_slot_ids = selection["course_assignments"].get("SCI 1010", set())
            assigned_categories = {slots["by_id"][sid]["category"] for sid in assigned_slot_ids}
            self.assertEqual(
                assigned_categories,
                {"Quantitative Reasoning", "Scientific Investigation"},
            )
        finally:
            path.unlink(missing_ok=True)

    def test_excel_only_wic_course_is_marked_in_plan_output(self):
        path = _write_excel_course_universe([
            [
                "PHI",
                "1100",
                "Ethics and Society",
                "Moral and Philosophical Reasoning; Writing Intensive Course",
                "",
            ],
        ])
        try:
            load_course_catalog(path)
            catalog = {
                "courses": {},
                "course_meta": {},
                "majors": {},
                "minors": {},
                "foundation_courses": [],
                "gen_ed": {
                    "categories": {"Moral and Philosophical Reasoning": []},
                    "rules": {"Moral and Philosophical Reasoning": 1},
                },
                "excel_catalog": {"loaded": True},
            }

            plan = generate_plan(
                catalog=catalog,
                majors=[],
                minors=[],
                completed_courses=set(),
                max_credits_per_semester=16,
                start_term_season="Fall",
                start_term_year=2025,
                fill_underloaded_terms=False,
            )

            planned_courses = [
                course
                for term in plan.get("semester_plan", [])
                for course in term.get("courses", [])
                if isinstance(course, dict)
            ]
            self.assertTrue(any(c.get("code") == "PHI 1100" for c in planned_courses))
            target = next(c for c in planned_courses if c.get("code") == "PHI 1100")
            self.assertIn("Writing Intensive Course", target.get("tags", []))
            self.assertIn("GenEd: Moral and Philosophical Reasoning", target.get("satisfies", []))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

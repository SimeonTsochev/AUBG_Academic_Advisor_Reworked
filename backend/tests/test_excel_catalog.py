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

from excel_catalog import load_excel_catalog, get_recommended_electives, get_case_studies_gened_courses  # noqa: E402
from degree_engine import generate_plan  # noqa: E402


def _write_xlsx(rows: list[list[object]]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(["Department", "Course", "Area of Study"])
    for row in rows:
        ws.append(row)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()
    wb.save(tmp.name)
    return Path(tmp.name)


class ExcelCatalogTests(unittest.TestCase):
    def test_multiline_area_of_study_parses_tags(self):
        path = _write_xlsx([
            [
                "ECO",
                "3000",
                "Case Studies in Textual Analysis Gen Ed\nLIT Major Elective\nWriting Intensive Course",
            ],
        ])
        try:
            catalog = load_excel_catalog(path)
            tags = catalog["by_code"]["ECO 3000"]["tags"]
            self.assertEqual(
                tags,
                [
                    "Case Studies in Textual Analysis Gen Ed",
                    "LIT Major Elective",
                    "Writing Intensive Course",
                ],
            )
        finally:
            path.unlink(missing_ok=True)

    def test_recommended_electives_exclude_required(self):
        path = _write_xlsx([
            ["BUS", "1000", "BUS Major Elective"],
            ["BUS", "2000", "BUS Major Required"],
            ["ECO", "3000", "ECO Major Elective"],
        ])
        try:
            catalog = load_excel_catalog(path)
            recs = get_recommended_electives(
                excel_catalog=catalog,
                selected_majors=["Business Administration"],
                selected_minors=[],
            )
            codes = {r["code"] for r in recs}
            self.assertIn("BUS 1000", codes)
            self.assertNotIn("BUS 2000", codes)
            self.assertNotIn("ECO 3000", codes)
        finally:
            path.unlink(missing_ok=True)

    def test_case_studies_gened_discovery(self):
        path = _write_xlsx([
            ["ENG", "2100", "Case Studies in Textual Analysis Gen Ed"],
            ["ENG", "2200", "Writing Intensive Course"],
        ])
        try:
            catalog = load_excel_catalog(path)
            codes = get_case_studies_gened_courses(catalog)
            self.assertEqual(codes, ["ENG 2100"])
        finally:
            path.unlink(missing_ok=True)

    def test_excel_courses_do_not_auto_appear_in_plan(self):
        path = _write_xlsx([
            ["ELEC", "2000", "BUS Major Elective"],
        ])
        try:
            excel_catalog = load_excel_catalog(path)
            catalog = {
                "courses": {
                    "GEN 1000": {"name": "GenEd", "credits": 3, "gen_ed": ["Historical Research"]},
                    "ELEC 2000": {"name": "Elective", "credits": 3, "gen_ed": []},
                },
                "course_meta": {
                    "GEN 1000": {"credits": 3, "gen_ed": "Historical Research", "prereq_codes": []},
                    "ELEC 2000": {"credits": 3, "prereq_codes": []},
                },
                "majors": {},
                "minors": {},
                "foundation_courses": [],
                "gen_ed": {
                    "categories": {"Historical Research": ["GEN 1000"]},
                    "rules": {"Historical Research": 1},
                },
                "excel_catalog": excel_catalog,
            }
            plan = generate_plan(
                catalog=catalog,
                majors=[],
                minors=[],
                completed_courses=set(),
                max_credits_per_semester=16,
                start_term_season="Fall",
                start_term_year=2025,
            )
            scheduled_codes = {c["code"] for term in plan["semester_plan"] for c in term["courses"]}
            self.assertNotIn("ELEC 2000", scheduled_codes)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

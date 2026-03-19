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

from excel_course_catalog import load_course_catalog, load_course_catalog_from_data, get_course  # noqa: E402


def _write_xlsx(headers: list[str], rows: list[list[object]]) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()
    wb.save(tmp.name)
    return Path(tmp.name)


class ExcelCourseCatalogTests(unittest.TestCase):
    def test_workbook_normalizes_excel_escape_sequences(self):
        path = _write_xlsx(
            headers=["Department", "Course", "Label", "Area of Study", "Course Notes", "term"],
            rows=[
                [
                    "BUS",
                    "1001",
                    "Management in a Global Economy",
                    "BUS Major Required_x000D_\nWriting Intensive Course",
                    "Credits: 3 CR / 6 ECTS.",
                    "Fall 2026_x000D_\nSpring 2027",
                ]
            ],
        )
        try:
            load_course_catalog(path)
            course = get_course("BUS1001")
            self.assertIsNotNone(course)
            assert course is not None
            self.assertIn("BUS Major Required", course["tags"])
            self.assertNotIn("BUS Major Required_x000D_", course["tags"])
            self.assertIn("Fall 2026", course["semester_availability"])
            self.assertNotIn("Fall 2026_x000D_", course["semester_availability"])
        finally:
            path.unlink(missing_ok=True)

    def test_artifact_payload_normalizes_excel_escape_sequences(self):
        load_course_catalog_from_data(
            {
                "courses": [
                    {
                        "code": "BUS 1001",
                        "title": "Management in a Global Economy",
                        "department": "BUS",
                        "prefix": "BUS",
                        "level": "Undergraduate Lower Level",
                        "credits": 3,
                        "area_of_study_tags": [
                            "BUS Major Required_x000D_",
                            "Writing Intensive Course",
                        ],
                        "tags": [
                            "BUS Major Required_x000D_",
                            "Writing Intensive Course",
                        ],
                        "gen_ed_tags": [],
                        "wic": True,
                        "semester_availability": [
                            "Fall 2026_x000D_",
                            "Spring 2027",
                        ],
                        "availability_fields": {
                            "term": ["Fall 2026_x000D_", "Spring 2027"],
                        },
                    }
                ]
            },
            source_label="test-artifact",
        )

        course = get_course("BUS1001")
        self.assertIsNotNone(course)
        assert course is not None
        self.assertIn("BUS Major Required", course["tags"])
        self.assertNotIn("BUS Major Required_x000D_", course["tags"])
        self.assertIn("Fall 2026", course["semester_availability"])
        self.assertNotIn("Fall 2026_x000D_", course["semester_availability"])


if __name__ == "__main__":
    unittest.main()

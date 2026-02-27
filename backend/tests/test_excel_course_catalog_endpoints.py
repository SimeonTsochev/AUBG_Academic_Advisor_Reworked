import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from excel_course_catalog import load_course_catalog, get_course  # noqa: E402
from main import app  # noqa: E402


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


class ExcelCourseCatalogEndpointsTests(unittest.TestCase):
    def test_module_normalizes_codes_and_splits_area_tags(self):
        path = _write_xlsx(
            headers=["Department", "Course", "Label", "Area of Study", "Course Notes", "term"],
            rows=[
                [
                    "bus",
                    "1001",
                    "Management in a Global Economy",
                    "BUS Major Required; Moral and Philosophical Reasoning\nWriting Intensive Course",
                    "Credits: 3 CR / 6 ECTS.",
                    "Fall 2025\nSpring 2026",
                ]
            ],
        )
        try:
            load_course_catalog(path)
            course = get_course("bus1001")
            self.assertIsNotNone(course)
            assert course is not None
            self.assertEqual(course["code"], "BUS 1001")
            self.assertEqual(course["credits"], 3)
            self.assertIn("BUS Major Required", course["area_of_study_tags"])
            self.assertIn("Moral and Philosophical Reasoning", course["gen_ed_tags"])
            self.assertTrue(course["wic"])
            self.assertIn("Fall 2025", course["semester_availability"])
        finally:
            path.unlink(missing_ok=True)

    def test_courses_lookup_endpoint_normalizes_code(self):
        client = TestClient(app)
        response = client.get("/courses/BUS1001")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], "BUS 1001")
        self.assertIn("title", payload)
        self.assertIn("credits", payload)
        self.assertIn("is_excel_only", payload)

    def test_courses_search_finds_excel_only_codes_when_present(self):
        client = TestClient(app)
        default_resp = client.post("/catalog/load-default")
        self.assertEqual(default_resp.status_code, 200)
        catalog_id = default_resp.json()["catalog_id"]
        default_payload = default_resp.json()
        self.assertIn("excel_only_codes", default_payload)
        self.assertIsInstance(default_payload.get("excel_only_codes"), list)

        integrity_resp = client.get("/catalog/integrity", params={"catalog_id": catalog_id})
        self.assertEqual(integrity_resp.status_code, 200)
        integrity = integrity_resp.json()
        excel_only = integrity.get("excel_only") or []

        if not excel_only:
            self.skipTest("No excel-only courses in this catalog snapshot.")

        code = excel_only[0]
        search_resp = client.get("/courses/search", params={"q": code.replace(" ", "")})
        self.assertEqual(search_resp.status_code, 200)
        payload = search_resp.json()
        found_codes = [entry.get("code") for entry in payload]
        self.assertIn(code, found_codes)
        matching = next((entry for entry in payload if entry.get("code") == code), None)
        self.assertIsNotNone(matching)
        assert matching is not None
        self.assertTrue(bool(matching.get("is_excel_only")))


if __name__ == "__main__":
    unittest.main()

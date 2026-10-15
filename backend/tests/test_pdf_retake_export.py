import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

from pdf_export import _course_label_for_pdf  # noqa: E402


class PdfRetakeExportTests(IsolatedTestCase):
    def test_retake_course_label_includes_retake_and_effective_credit(self):
        label = _course_label_for_pdf(
            {
                "code": "BUS 2020",
                "name": "Accounting I",
                "credits": 3,
                "is_retake": True,
            }
        )
        self.assertIn("Retake", label)
        self.assertIn("3 cr", label)

    def test_previous_attempt_label_includes_replaced_by_retake_and_zero_credit(self):
        label = _course_label_for_pdf(
            {
                "code": "BUS 2020",
                "name": "Accounting I",
                "credits": 0,
                "is_retake": True,
                "tags": ["Previous Attempt"],
            }
        )
        self.assertIn("Replaced by Retake", label)
        self.assertIn("0 cr", label)


class PdfExportEndpointTests(IsolatedTestCase):
    excel_index = "real"

    def test_pdf_has_the_students_own_semesters_and_readable_rows(self):
        import io

        import pdfplumber
        from fastapi.testclient import TestClient

        import main

        client = TestClient(main.app)
        catalog_id = client.get("/catalog/load-default").json()["catalog_id"]
        body = {
            "catalog_id": catalog_id,
            "majors": ["Computer Science"],
            "minors": [],
            "program_options": {"Computer Science": ["Software Development"]},
            "completed_courses": ["COS 1050", "ENG 1001", "BUS 1001", "COS 2021", "STA 1005", "MAT 1000"],
            "in_progress_courses": ["COS 2021", "STA 1005"],
            "in_progress_terms": {"COS 2021": "Fall 2026", "STA 1005": "Fall 2026"},
            "grades": [{"code": "COS 1050", "grade": "B", "term": "Fall 2025"}],
            "waived_mat1000": True,
            "start_term_season": "Fall",
            "start_term_year": 2025,
            "current_term_label": "Fall 2026",
        }
        response = client.post("/plan/download.pdf", json=body)
        self.assertEqual(response.status_code, 200)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn("Minors: None", text)
        self.assertIn("Fall 2025", text)  # from the transcript grade
        self.assertIn("Fall 2026 (in COS 2021, STA 1005 6", text)  # "(in progress)" wraps in its column
        self.assertIn("Completed ENG 1001, BUS 1001 7", text)  # entered without a term
        self.assertNotIn("MAT 1000", text)  # waived, never taken
        self.assertNotIn("�", text)
        # Long course lists wrap inside their column instead of running into the credits column.
        last_term = [line for line in text.splitlines() if line.startswith("FREE ELECTIVE")][-1]
        self.assertNotRegex(last_term, r"\d\d[A-Z]")


if __name__ == "__main__":
    unittest.main()

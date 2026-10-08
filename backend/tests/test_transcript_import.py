import os
import sys
import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

from main import app  # noqa: E402
from transcript_import import (  # noqa: E402
    ParsedTranscriptCourse,
    TranscriptLine,
    build_transcript_import_response,
    import_transcript_document,
    parse_transcript_lines,
)


def _build_pdf_bytes(lines: list[str]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for index, line in enumerate(lines):
        pdf.drawString(72, 760 - (index * 18), line)
    pdf.save()
    return buffer.getvalue()


class TranscriptImportTests(IsolatedTestCase):
    excel_index = "real"

    def test_parse_transcript_lines_classifies_sections_and_strips_noise(self):
        parsed = parse_transcript_lines(
            [
                TranscriptLine(page_number=1, text="Spring 2025"),
                TranscriptLine(
                    page_number=1,
                    text="BUS-1001 Management in a Global Environment Professor Jane Doe A",
                ),
                TranscriptLine(page_number=1, text="Good Standing"),
                TranscriptLine(page_number=1, text="Current Term Spring 2026"),
                TranscriptLine(page_number=1, text="ENG-1002 Academic Writing II IP"),
            ]
        )

        self.assertEqual([course.normalized_code for course in parsed], ["BUS 1001", "ENG 1002"])
        self.assertEqual(parsed[0].status, "completed")
        self.assertEqual(parsed[0].term, "Spring 2025")
        self.assertEqual(parsed[0].raw_title, "Management in a Global Environment")
        self.assertEqual(parsed[1].status, "in_progress")
        self.assertEqual(parsed[1].term, "Spring 2026")
        self.assertEqual(parsed[1].raw_title, "Academic Writing II")

    def test_failing_grades_mark_the_course_failed_so_it_is_not_completed(self):
        parsed = parse_transcript_lines(
            [
                TranscriptLine(page_number=1, text="Fall 2025"),
                TranscriptLine(page_number=1, text="MAT-1003 Calculus I 3.00 F"),
                TranscriptLine(page_number=1, text="ECO-1001 Principles of Microeconomics 3.00 B+"),
                TranscriptLine(page_number=1, text="BUS-1001 Management in a Global Environment 0.00 W"),
                TranscriptLine(page_number=1, text="ENG-1001 Academic Writing I"),
                TranscriptLine(page_number=1, text="WF"),
                TranscriptLine(page_number=1, text="COS-1020 C++ Programming 3.00 I"),
                # The term-totals line re-stamps the term on every course above; the grades must survive it.
                TranscriptLine(page_number=1, text="Term Fall 2025 Totals"),
            ]
        )
        by_code = {course.normalized_code: course for course in parsed}
        self.assertEqual((by_code["MAT 1003"].status, by_code["MAT 1003"].grade), ("failed", "F"))
        self.assertEqual((by_code["ECO 1001"].status, by_code["ECO 1001"].grade), ("completed", "B+"))
        self.assertEqual((by_code["BUS 1001"].status, by_code["BUS 1001"].grade), ("failed", "W"))
        self.assertEqual((by_code["ENG 1001"].status, by_code["ENG 1001"].grade), ("failed", "WF"))
        self.assertEqual((by_code["COS 1020"].status, by_code["COS 1020"].grade), ("failed", "I"))
        self.assertEqual(by_code["MAT 1003"].raw_title, "Calculus I")

    def test_a_roman_numeral_title_is_not_read_as_an_incomplete_grade(self):
        parsed = parse_transcript_lines(
            [
                TranscriptLine(page_number=1, text="Fall 2025"),
                TranscriptLine(page_number=1, text="MAT-1003 Calculus I"),
            ]
        )
        self.assertEqual((parsed[0].status, parsed[0].grade), ("completed", None))

    def test_a_passed_retake_replaces_the_failed_attempt(self):
        parsed = parse_transcript_lines(
            [
                TranscriptLine(page_number=1, text="Fall 2025"),
                TranscriptLine(page_number=1, text="MAT-1003 Calculus I 3.00 F"),
                TranscriptLine(page_number=1, text="Term Fall 2025 Totals"),
                TranscriptLine(page_number=1, text="Spring 2026"),
                TranscriptLine(page_number=1, text="MAT-1003 Calculus I 3.00 B"),
            ]
        )
        self.assertEqual(len(parsed), 1)
        self.assertEqual((parsed[0].status, parsed[0].grade, parsed[0].term), ("completed", "B", "Spring 2026"))

    def test_failed_courses_are_returned_separately(self):
        response = build_transcript_import_response(
            [
                ParsedTranscriptCourse(
                    raw_code="MAT-1003",
                    normalized_code="MAT 1003",
                    raw_title="Calculus I",
                    status="failed",
                    term="Fall 2025",
                    page_number=1,
                    text_confidence=1.0,
                    grade="F",
                )
            ]
        )
        self.assertEqual(response["completed"], [])
        self.assertEqual(response["failed"][0]["matched_code"], "MAT 1003")
        self.assertEqual(response["failed"][0]["grade"], "F")

    def test_build_transcript_import_response_keeps_unmatched_rows_for_review(self):
        response = build_transcript_import_response(
            [
                ParsedTranscriptCourse(
                    raw_code="ZZZ-9999",
                    normalized_code="ZZZ 9999",
                    raw_title="Imaginary Seminar",
                    status="completed",
                    term="Spring 2025",
                    page_number=1,
                    text_confidence=1.0,
                )
            ]
        )

        self.assertEqual(len(response["completed"]), 1)
        self.assertEqual(len(response["unmatched"]), 1)
        self.assertFalse(response["completed"][0]["matched_confidently"])
        self.assertIn("need review", response["warnings"][0].lower())

    def test_parse_transcript_lines_handles_ocr_split_status_and_trailing_term_totals(self):
        parsed = parse_transcript_lines(
            [
                TranscriptLine(page_number=1, text="Course"),
                TranscriptLine(page_number=1, text="Title"),
                TranscriptLine(page_number=1, text="BUS-1001"),
                TranscriptLine(page_number=1, text="Management in a Global Environment"),
                TranscriptLine(page_number=1, text="In Progress"),
                TranscriptLine(page_number=1, text="BUS-2001"),
                TranscriptLine(page_number=1, text="Management Information Systems"),
                TranscriptLine(page_number=1, text="In Progress"),
                TranscriptLine(page_number=1, text="Term Spring 2026 Totals"),
                TranscriptLine(page_number=1, text="Course"),
                TranscriptLine(page_number=1, text="Title"),
                TranscriptLine(page_number=1, text="AUB-1000"),
                TranscriptLine(page_number=1, text="Introduction to Liberal Arts Learning"),
                TranscriptLine(page_number=1, text="P"),
                TranscriptLine(page_number=1, text="ECO-1001"),
                TranscriptLine(page_number=1, text="Principles of Microeconomics"),
                TranscriptLine(page_number=1, text="B+"),
                TranscriptLine(page_number=1, text="TermFall2025 Totals"),
            ]
        )

        by_code = {course.normalized_code: course for course in parsed}
        self.assertEqual(by_code["BUS 1001"].status, "in_progress")
        self.assertEqual(by_code["BUS 1001"].term, "Spring 2026")
        self.assertEqual(by_code["BUS 2001"].status, "in_progress")
        self.assertEqual(by_code["BUS 2001"].raw_title, "Management Information Systems")
        self.assertEqual(by_code["AUB 1000"].status, "completed")
        self.assertEqual(by_code["AUB 1000"].term, "Fall 2025")
        self.assertEqual(by_code["ECO 1001"].term, "Fall 2025")

    def test_transcript_import_endpoint_accepts_pdf(self):
        client = TestClient(app)
        pdf_bytes = _build_pdf_bytes(
            [
                "Spring 2025",
                "BUS-1001 Management in a Global Environment 3.00 A",
                "ECO-1001 Principles of Microeconomics 3.00 B+",
                "Current Term Spring 2026",
                "ENG-1002 Academic Writing II IP",
            ]
        )

        response = client.post(
            "/transcript/import",
            files={"file": ("transcript.pdf", pdf_bytes, "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        completed_codes = [course["matched_code"] for course in payload["completed"]]
        in_progress_codes = [course["matched_code"] for course in payload["in_progress"]]
        self.assertIn("BUS 1001", completed_codes)
        self.assertIn("ECO 1001", completed_codes)
        self.assertIn("ENG 1002", in_progress_codes)
        self.assertEqual(payload["unmatched"], [])

    def test_import_transcript_document_supports_image_uploads_via_ocr(self):
        mock_lines = [
            TranscriptLine(page_number=1, text="Current Term Spring 2026"),
            TranscriptLine(page_number=1, text="BUS-1001 Management in a Global Environment IP"),
        ]

        with patch("transcript_import._extract_ocr_lines_from_image_bytes", return_value=mock_lines):
            response = import_transcript_document(b"fake-image-bytes", "transcript.png")

        self.assertEqual(len(response["in_progress"]), 1)
        self.assertEqual(response["in_progress"][0]["matched_code"], "BUS 1001")
        self.assertTrue(any("ocr" in warning.lower() for warning in response["warnings"]))

    def test_transcript_import_text_endpoint_accepts_ocr_lines(self):
        client = TestClient(app)

        response = client.post(
            "/transcript/import-text",
            json={
                "used_ocr": True,
                "lines": [
                    {"text": "Current Term Spring 2026", "page_number": 1, "confidence": 0.99},
                    {"text": "BUS-1001 Management in a Global Environment", "page_number": 1, "confidence": 0.96},
                    {"text": "In Progress", "page_number": 1, "confidence": 0.94},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["completed"], [])
        self.assertEqual(payload["in_progress"][0]["matched_code"], "BUS 1001")
        self.assertTrue(any("ocr" in warning.lower() for warning in payload["warnings"]))

    def test_transcript_import_endpoint_rejects_unsupported_files(self):
        client = TestClient(app)
        response = client.post(
            "/transcript/import",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file type", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()

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
    _extract_pdf_text_lines,
    _page_may_have_text,
    find_unread_course_lines,
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


def _lines(texts: list[str]) -> list[TranscriptLine]:
    return [TranscriptLine(page_number=1, text=text, confidence=0.9) for text in texts]


# The student portal's "Primary Unofficial Transcript" printed to PDF, as OCR reads it line by line: the
# term name comes on the "Term ... Totals" line after its block, current courses say "In Progress", and
# wrapped instructor names and titles land on lines of their own. Names, ID and grades are invented.
PORTAL_TRANSCRIPT_LINES = [
    "American University in Bulgaria Thursday, October 08, 2026",
    "Primary Unofficial Transcript",
    "Student ID: 123456789",
    "Student Name: Test Student",
    "Major Minor Specialize1 Specialize2 Track",
    "Undeclared",
    "(Undergraduate Classes)",
    "Course Title Instructor Final Grade Course Credits Credits Earned",
    "BUS-2020 Financial Accounting Prof. Ana Petrova In Progress",
    "HTY-1008 Introduction to Archaeology Prof. Ivan Ivanov In Progress",
    "Prof. Maria",
    "JMC-2118 International Disinformation & Propaganda In Progress",
    "Georgieva",
    "Elementary Linear Algebra and Analytical Prof. Elena",
    "MAT-1005 In Progress",
    "Geometry Dimitrova",
    "PHY-1010 Mechanics and Thermodynamics Prof. Petar Kolev In Progress",
    "PHY-1011 Mechanics and Thermodynamics Georgi Stoev In Progress",
    "Term Fall 2026 Totals",
    "Course Title Instructor Final Grade Course Credits Credits Earned",
    "BUS-1001 Management in a Global Environment Prof. Jane Doe A- 3 3",
    "BUS-2001 Management Information Systems Prof. John Roe B+ 3 3",
    "ENG-1002 Writing Academic Research Papers Prof. Ann Lee F 4 0",
    "JMC-2000 Visual Communication Prof. Mark Fox C 3 3",
    "Term Spring 2026 Totals 13 9 GPA: 2.615",
    "Good Standing",
    "Course Title Instructor Final Grade Course Credits Credits Earned",
    "AUB-1000 Introduction to Liberal Arts Learning Prof. Eva Stone P 0 0",
    "ECO-1001 Principles of Microeconomics Prof. Tom Hill A 3 3",
    "ENG-1001 Exposition Prof. Kate Moss C+ 4 4",
    "STA-1005 Statistics Prof. Sam Park B- 3 3",
    "Term Fall 2025 Totals 10 10 GPA: 2.900",
    "Undergraduate Institutional Totals Credits Attempted Credits Earned GPA",
    "23 19 2.750",
    "Overall Undergraduate Totals Credits Attempted Credits Earned GPA",
    "23 19 2.750",
    "Need help? Please contact the Registrar's Office",
]


class PortalTranscriptLayoutTests(IsolatedTestCase):
    excel_index = "real"

    def test_portal_transcript_rows_get_the_term_printed_after_their_block(self):
        parsed = {course.normalized_code: course for course in parse_transcript_lines(_lines(PORTAL_TRANSCRIPT_LINES))}

        self.assertEqual(
            sorted(parsed),
            sorted([
                "BUS 2020", "HTY 1008", "JMC 2118", "MAT 1005", "PHY 1010", "PHY 1011",
                "BUS 1001", "BUS 2001", "ENG 1002", "JMC 2000",
                "AUB 1000", "ECO 1001", "ENG 1001", "STA 1005",
            ]),
        )
        for code in ("BUS 2020", "HTY 1008", "JMC 2118", "MAT 1005", "PHY 1010", "PHY 1011"):
            self.assertEqual((parsed[code].status, parsed[code].term, parsed[code].grade), ("in_progress", "Fall 2026", None))
        self.assertEqual((parsed["BUS 1001"].status, parsed["BUS 1001"].term, parsed["BUS 1001"].grade), ("completed", "Spring 2026", "A-"))
        self.assertEqual((parsed["ENG 1002"].status, parsed["ENG 1002"].term, parsed["ENG 1002"].grade), ("failed", "Spring 2026", "F"))
        self.assertEqual((parsed["AUB 1000"].status, parsed["AUB 1000"].term, parsed["AUB 1000"].grade), ("completed", "Fall 2025", "P"))
        self.assertEqual((parsed["ENG 1001"].status, parsed["ENG 1001"].term, parsed["ENG 1001"].grade), ("completed", "Fall 2025", "C+"))
        self.assertEqual(find_unread_course_lines(_lines(PORTAL_TRANSCRIPT_LINES)), [])

    def test_rows_whose_code_ocr_garbled_are_reported_as_unread(self):
        # Lines as low-resolution OCR read the portal PDF: codes "HTY-1008" and "PHY-1010" came out mangled,
        # and one row lost its code entirely.
        lines = _lines([
            "Course Title Instructor Final Grade Course Credits Credits Earned",
            "irv1008 Induction to Achacolgy pre. option InProgrss",
            "MAT-1005 Elementary Linear Algebra and Analytical Prof. Elena In Progress.",
            "prvt010 a — FE In Progress",
            "Georgieva",
            "Term Fall 2028 Totals",
            "BUS-1001 Management in a Global Environment Prof. Jane B- 3 3",
            "Visual Communication lleva C+ 3 3",
            "Term Spring 2026 Totals 6 6 GPA: 2.500",
            "Undergraduate nsitulonal Totals po— oon",
        ])

        self.assertEqual(
            sorted(course.normalized_code for course in parse_transcript_lines(lines)),
            ["BUS 1001", "MAT 1005"],
        )
        self.assertEqual(
            [line.text for line in find_unread_course_lines(lines)],
            [
                "irv1008 Induction to Achacolgy pre. option InProgrss",
                "prvt010 a - FE In Progress",
                "Visual Communication lleva C+ 3 3",
            ],
        )

    def test_import_text_endpoint_returns_the_unread_lines(self):
        response = TestClient(app).post(
            "/transcript/import-text",
            json={
                "used_ocr": True,
                "lines": [
                    {"text": "BUS-1001 Management in a Global Environment Prof. Jane B- 3 3", "page_number": 1},
                    {"text": "prvt010 a - FE In Progress", "page_number": 2},
                    {"text": "Term Spring 2026 Totals 3 3 GPA: 2.670", "page_number": 2},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_lines"], [{"text": "prvt010 a - FE In Progress", "page_number": 2}])


def _pdf_without_fonts(path_ops: str) -> bytes:
    """A one-page PDF whose content is only vector paths, with no /Font resource (reportlab always adds one)."""
    content = path_ops.encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)
    return bytes(out)


def _stub_page(resources: dict):
    from types import SimpleNamespace
    return SimpleNamespace(page_obj=SimpleNamespace(resources=resources))


class PdfTextLayerTests(IsolatedTestCase):
    def test_a_page_without_fonts_is_skipped_before_the_slow_layout(self):
        # The portal's printed transcript draws every glyph as a path; laying those out took 5-9 s for nothing.
        paths = "".join(f"72 {700 - row * 12} m 540 {700 - row * 12} l S\n" for row in range(40))
        with patch("pdfplumber.page.Page.extract_words", side_effect=AssertionError("layout should be skipped")):
            self.assertEqual(_extract_pdf_text_lines(_pdf_without_fonts(paths)), [])

    def test_pages_with_fonts_or_form_xobjects_may_hold_text(self):
        from pdfminer.psparser import LIT

        self.assertTrue(_page_may_have_text(_stub_page({"Font": {"F1": {}}})))
        self.assertTrue(_page_may_have_text(_stub_page({"XObject": {"Fm0": {"Subtype": LIT("Form")}}})))
        self.assertFalse(_page_may_have_text(_stub_page({"XObject": {"Im0": {"Subtype": LIT("Image")}}})))
        self.assertFalse(_page_may_have_text(_stub_page({})))

    def test_a_text_pdf_is_still_read(self):
        lines = _extract_pdf_text_lines(_build_pdf_bytes(["Fall 2025", "BUS-1001 Management in a Global Environment B+ 3 3"]))
        self.assertIn("BUS-1001 Management in a Global Environment B+ 3 3", [line.text for line in lines])


if __name__ == "__main__":
    unittest.main()


class TranscriptMergeTests(IsolatedTestCase):
    def _course(self, status, term, grade):
        from transcript_import import ParsedTranscriptCourse

        return ParsedTranscriptCourse(
            raw_code="BUS 1001", normalized_code="BUS 1001", raw_title=None, status=status,
            term=term, page_number=1, text_confidence=1.0, grade=grade,
        )

    def test_a_duplicate_row_without_a_grade_keeps_the_grade(self):
        from transcript_import import _merge_parsed_courses

        graded = self._course("completed", "Spring 2026", "B+")
        bare = self._course("completed", "Spring 2026", None)
        self.assertEqual(_merge_parsed_courses(graded, bare).grade, "B+")
        self.assertEqual(_merge_parsed_courses(bare, graded).grade, "B+")

    def test_a_retake_never_inherits_the_earlier_grade(self):
        from transcript_import import _merge_parsed_courses

        failed = self._course("failed", "Fall 2025", "F")
        current = self._course("in_progress", "Fall 2026", None)
        self.assertIsNone(_merge_parsed_courses(failed, current).grade)

import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pdf_export import _course_label_for_pdf  # noqa: E402


class PdfRetakeExportTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

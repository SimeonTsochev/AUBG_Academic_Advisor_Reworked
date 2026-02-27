import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import _infer_allowed_prefixes_for_minor_electives, compute_minor_proximity_smart_details  # noqa: E402


class MinorPrefixInferenceTests(unittest.TestCase):
    def test_extracts_prefixes_for_any_other_course_phrases(self):
        self.assertIn(
            "POLS",
            _infer_allowed_prefixes_for_minor_electives("Test Minor", "Any other POLS courses"),
        )
        self.assertIn(
            "HIST",
            _infer_allowed_prefixes_for_minor_electives("Test Minor", "Any other HIST courses"),
        )
        self.assertIn(
            "ECO",
            _infer_allowed_prefixes_for_minor_electives("Test Minor", "Any other ECO courses"),
        )
        self.assertIn(
            "POLS",
            _infer_allowed_prefixes_for_minor_electives("Test Minor", "Any POLS courses"),
        )
        self.assertIn(
            "POLS",
            _infer_allowed_prefixes_for_minor_electives("Test Minor", "Any other POLS course"),
        )

    def test_no_regression_for_three_letter_subjects(self):
        prefixes = _infer_allowed_prefixes_for_minor_electives("Test Minor", "Any other ECO courses")
        self.assertIn("ECO", prefixes)

    def test_inferred_pols_prefix_counts_pols_courses_as_allowed(self):
        catalog = {
            "courses": {
                "POLS 1001": {"name": "Intro to Politics", "credits": 3},
                "POLS 2001": {"name": "Comparative Politics", "credits": 3},
                "BUS 1001": {"name": "Intro to Business", "credits": 3},
            },
            "course_meta": {
                "POLS 1001": {"credits": 3, "prereq_codes": []},
                "POLS 2001": {"credits": 3, "prereq_codes": []},
                "BUS 1001": {"credits": 3, "prereq_codes": []},
            },
            "majors": {},
            "minors": {
                "Policy Minor": {
                    "required_courses": [],
                    "elective_requirements": [
                        {
                            "label": "Electives",
                            "credits_required": 6,
                            "courses_required": None,
                            "allowed_courses": [],
                            "rule_text": "Any other POLS courses.",
                            "is_total": True,
                        }
                    ],
                }
            },
            "foundation_courses": [],
            "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
        }

        remaining_count, _remaining_items, _remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name="Policy Minor",
            completed_and_planned_courses={"POLS 1001"},
        )
        self.assertEqual(remaining_count, 1)


if __name__ == "__main__":
    unittest.main()

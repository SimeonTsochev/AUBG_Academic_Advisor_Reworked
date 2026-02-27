import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import compute_minor_suggestions  # noqa: E402


def _catalog_for_swap_identity() -> dict:
    return {
        "courses": {
            "AAA 1001": {"name": "Alpha One", "credits": 3},
            "AAA 1002": {"name": "Alpha Two", "credits": 3},
        },
        "course_meta": {
            "AAA 1001": {"credits": 3, "prereq_codes": []},
            "AAA 1002": {"credits": 3, "prereq_codes": []},
        },
        "majors": {},
        "minors": {
            "Alpha Minor": {
                "required_courses": ["AAA 1001", "AAA 1002"],
                "elective_requirements": [],
            }
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
    }


class MinorSwapSlotIdentityTests(unittest.TestCase):
    def test_duplicate_free_slots_use_deterministic_slot_index_without_instance_id(self):
        catalog = _catalog_for_swap_identity()
        semester_plan = [
            {
                "term": "Fall 2026",
                "courses": [
                    {"code": "FREE ELECTIVE"},
                    {"code": "FREE ELECTIVE"},
                ],
                "credits": 6,
            }
        ]

        suggestions = compute_minor_suggestions(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses=set(),
            in_progress_courses=set(),
            semester_plan=semester_plan,
            top_k=10,
        )
        self.assertEqual(len(suggestions), 1)
        swaps = suggestions[0].get("swap_suggestions") or []
        self.assertEqual(len(swaps), 2)
        self.assertEqual([swaps[0].get("replace_slot_index"), swaps[1].get("replace_slot_index")], [0, 1])
        self.assertIsNone(swaps[0].get("replace_instance_id"))
        self.assertIsNone(swaps[1].get("replace_instance_id"))
        self.assertEqual(swaps[0].get("term"), "Fall 2026")
        self.assertEqual(swaps[1].get("term"), "Fall 2026")

    def test_duplicate_free_slots_preserve_instance_ids_when_available(self):
        catalog = _catalog_for_swap_identity()
        semester_plan = [
            {
                "term": "Fall 2026",
                "courses": [
                    {"code": "FREE ELECTIVE", "instance_id": "slot-a"},
                    {"code": "FREE ELECTIVE", "instance_id": "slot-b"},
                ],
                "credits": 6,
            }
        ]

        suggestions = compute_minor_suggestions(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses=set(),
            in_progress_courses=set(),
            semester_plan=semester_plan,
            top_k=10,
        )
        self.assertEqual(len(suggestions), 1)
        swaps = suggestions[0].get("swap_suggestions") or []
        self.assertEqual(len(swaps), 2)
        self.assertEqual(swaps[0].get("replace_instance_id"), "slot-a")
        self.assertEqual(swaps[1].get("replace_instance_id"), "slot-b")
        self.assertEqual([swaps[0].get("replace_slot_index"), swaps[1].get("replace_slot_index")], [0, 1])


if __name__ == "__main__":
    unittest.main()

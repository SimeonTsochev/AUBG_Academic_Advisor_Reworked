import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import compute_minor_proximity_smart_details  # noqa: E402


def _choice_group_catalog() -> dict:
    courses = {
        "AAA 1000": {"name": "AAA 1000", "credits": 3},
        "BBB 1000": {"name": "BBB 1000", "credits": 3},
        "CCC 1000": {"name": "CCC 1000", "credits": 3},
        "DDD 1000": {"name": "DDD 1000", "credits": 3},
        "EEE 1000": {"name": "EEE 1000", "credits": 3},
    }
    return {
        "courses": courses,
        "course_meta": {code: {"credits": 3, "prereq_codes": []} for code in courses.keys()},
        "majors": {},
        "minors": {
            "Choice Minor": {
                "required_courses": {
                    "required_courses": [],
                    "choices": [
                        {
                            "label": "Group1",
                            "count": 1,
                            "courses": ["AAA 1000", "BBB 1000"],
                        },
                        {
                            "label": "Group2",
                            "count": 1,
                            "courses": ["CCC 1000", "DDD 1000", "EEE 1000"],
                        },
                    ],
                },
                "elective_requirements": [],
            },
            "Choice Minor + Elective": {
                "required_courses": {
                    "required_courses": [],
                    "choices": [
                        {
                            "label": "Group1",
                            "count": 1,
                            "courses": ["AAA 1000", "BBB 1000"],
                        },
                        {
                            "label": "Group2",
                            "count": 1,
                            "courses": ["CCC 1000", "DDD 1000", "EEE 1000"],
                        },
                    ],
                },
                "elective_requirements": [
                    {
                        "label": "Electives",
                        "credits_required": 3,
                        "courses_required": None,
                        "allowed_courses": ["AAA 1000", "BBB 1000", "CCC 1000", "DDD 1000", "EEE 1000"],
                        "rule_text": "Any listed courses",
                        "is_total": True,
                    }
                ],
            },
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
    }


class MinorChoiceGroupProximityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = _choice_group_catalog()

    def _remaining_count(self, minor_name: str, taken: set[str]) -> int:
        remaining_count, _remaining_items, _remaining_credits = compute_minor_proximity_smart_details(
            catalog=self.catalog,
            minor_name=minor_name,
            completed_and_planned_courses=set(taken),
        )
        return int(remaining_count)

    def test_choice_group_remaining_counts(self):
        self.assertEqual(self._remaining_count("Choice Minor", set()), 2)
        self.assertEqual(self._remaining_count("Choice Minor", {"AAA 1000"}), 1)
        self.assertEqual(self._remaining_count("Choice Minor", {"BBB 1000", "DDD 1000"}), 0)

    def test_required_choice_courses_do_not_double_count_for_electives(self):
        # AAA and CCC satisfy the two required groups. They cannot also satisfy elective deficit.
        self.assertEqual(self._remaining_count("Choice Minor + Elective", {"AAA 1000", "CCC 1000"}), 1)


if __name__ == "__main__":
    unittest.main()

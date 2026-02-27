import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import (  # noqa: E402
    _infer_allowed_prefixes_for_minor_electives,
    compute_minor_proximity_smart_details,
    compute_minor_suggestions,
)


def _synthetic_catalog(
    course_codes: list[str],
    minors: dict,
    *,
    credits_by_code: dict[str, int] | None = None,
) -> dict:
    credits_map = credits_by_code or {}
    courses = {
        code: {"name": code, "credits": int(credits_map.get(code, 3))}
        for code in course_codes
    }
    course_meta = {
        code: {"credits": int(credits_map.get(code, 3)), "prereq_codes": []}
        for code in course_codes
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {},
        "minors": minors,
        "foundation_courses": [],
        "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
    }


class SmartMinorDetectionRegressionTests(unittest.TestCase):
    def test_infer_allowed_prefixes_supports_two_to_four_letter_subjects(self):
        phrase_cases = [
            "Any other POLS courses",
            "Any POLS courses",
            "Any other POLS course",
            "Any other HIST courses",
            "Any other ECO courses",
        ]
        for phrase in phrase_cases:
            with self.subTest(phrase=phrase):
                prefixes = _infer_allowed_prefixes_for_minor_electives("Test Minor", phrase)
                if "POLS" in phrase:
                    self.assertIn("POLS", prefixes)
                if "HIST" in phrase:
                    self.assertIn("HIST", prefixes)
                if "ECO" in phrase:
                    self.assertIn("ECO", prefixes)

    def test_prefix_inference_applies_to_proximity_elective_matching(self):
        catalog = _synthetic_catalog(
            ["POLS 1001", "POLS 2001", "BUS 1001"],
            {
                "Political Science Minor": {
                    "required_courses": [],
                    "elective_requirements": [
                        {
                            "label": "Electives",
                            "credits_required": 6,
                            "courses_required": None,
                            "allowed_courses": [],
                            "rule_text": "Any other POLS courses",
                            "is_total": True,
                        }
                    ],
                }
            },
        )
        remaining_count, _items, remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name="Political Science Minor",
            completed_and_planned_courses={"POLS 1001"},
        )
        self.assertEqual(remaining_count, 1)
        self.assertEqual(remaining_credits, 3)

    def test_proximity_parses_float_credits_required(self):
        catalog = _synthetic_catalog(
            ["ECO 1001", "ECO 1002", "ECO 2001"],
            {
                "Float Credits Minor": {
                    "required_courses": [],
                    "elective_requirements": [
                        {
                            "label": "Electives",
                            "credits_required": 9.0,
                            "courses_required": None,
                            "allowed_courses": ["ECO 1001", "ECO 1002", "ECO 2001"],
                            "rule_text": "",
                            "is_total": True,
                        }
                    ],
                }
            },
        )
        remaining_count, _items, remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name="Float Credits Minor",
            completed_and_planned_courses={"ECO 1001"},
        )
        self.assertEqual(remaining_count, 2)
        self.assertEqual(remaining_credits, 6)

    def test_proximity_parses_numeric_string_courses_required(self):
        catalog = _synthetic_catalog(
            ["AAA 1000", "AAA 2000", "AAA 3000"],
            {
                "String Courses Minor": {
                    "required_courses": [],
                    "elective_requirements": [
                        {
                            "label": "Electives",
                            "credits_required": None,
                            "courses_required": "2",
                            "allowed_courses": ["AAA 1000", "AAA 2000", "AAA 3000"],
                            "rule_text": "",
                            "is_total": True,
                        }
                    ],
                }
            },
        )
        remaining_count, _items, remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name="String Courses Minor",
            completed_and_planned_courses={"AAA 1000"},
        )
        self.assertEqual(remaining_count, 1)
        self.assertEqual(remaining_credits, 3)

    def test_proximity_handles_choice_group_requirements(self):
        catalog = _synthetic_catalog(
            ["AAA 1000", "BBB 1000", "CCC 1000", "DDD 1000", "EEE 1000"],
            {
                "Choice Group Minor": {
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
                }
            },
        )
        cases = [
            (set(), 2),
            ({"AAA 1000"}, 1),
            ({"BBB 1000", "DDD 1000"}, 0),
        ]
        for taken, expected_remaining in cases:
            with self.subTest(taken=taken):
                remaining_count, _items, _credits = compute_minor_proximity_smart_details(
                    catalog=catalog,
                    minor_name="Choice Group Minor",
                    completed_and_planned_courses=taken,
                )
                self.assertEqual(remaining_count, expected_remaining)

    def test_imc_program_choice_required_courses_are_counted(self):
        catalog = _synthetic_catalog(
            [
                "BUS 2060",
                "ENT 2061",
                "BUS 3062",
                "JMC 1041",
                "JMC 1050",
                "JMC 2020",
                "JMC 3070",
                "BUS 4401",
            ],
            {
                "Integrated Marketing Communications": {
                    "required_courses": [],
                    "elective_requirements": [
                        {
                            "label": "Program Choice",
                            "credits_required": None,
                            "courses_required": None,
                            "allowed_courses": ["BUS 2060", "BUS 3062", "ENT 2061", "JMC 1041", "JMC 1050"],
                            "rule_text": "BUS 2060 Marketing (or ENT 2061 Marketing for Entrepreneurs) BUS 3062 Marketing Research JMC 1041 Communication, Media, and Society JMC 1050 Writing for Media (WIC)",
                            "is_total": False,
                        },
                        {
                            "label": "Elective Courses",
                            "credits_required": 6,
                            "courses_required": None,
                            "allowed_courses": ["BUS 3061", "JMC 2020", "JMC 3070", "JMC 3089"],
                            "rule_text": "Elective Courses (6 credit hours) BUS 4[4-9]NN Topics in Marketing Practice JMC 4[4-9]NN Topics in JMC",
                            "is_total": True,
                        },
                    ],
                }
            },
        )
        remaining_count, remaining_items, _remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name="Integrated Marketing Communications",
            completed_and_planned_courses={"BUS 2060", "JMC 1041", "JMC 1050", "JMC 2020"},
        )
        self.assertEqual(remaining_count, 2)
        self.assertIn("BUS 3062", remaining_items)

    def test_creative_writing_uses_typical_credit_not_hardcoded_three(self):
        catalog = _synthetic_catalog(
            ["ENG 2005", "ENG 2006", "JMC 1050", "FLM 2021", "ENG 3005", "ENG 3401", "JMC 4045"],
            {
                "Creative Writing": {
                    "required_courses": [],
                    "elective_requirements": [
                        {
                            "label": "Program Choice",
                            "credits_required": None,
                            "courses_required": None,
                            "allowed_courses": ["ENG 2005", "ENG 2006"],
                            "rule_text": "One of the following: ENG 2005 ... ENG 2006 ...",
                            "is_total": False,
                        },
                        {
                            "label": "Elective Courses",
                            "credits_required": 16,
                            "courses_required": 2,
                            "allowed_courses": ["JMC 1050", "FLM 2021", "ENG 3005", "JMC 4045"],
                            "rule_text": "ENG 3[4-9]NN Topics in Creative Writing. At least two courses must be at the 3000- or 4000-level.",
                            "is_total": True,
                        },
                    ],
                }
            },
            credits_by_code={
                "ENG 2005": 4,
                "ENG 2006": 4,
                "JMC 1050": 4,
                "FLM 2021": 4,
                "ENG 3005": 4,
                "ENG 3401": 4,
                "JMC 4045": 4,
            },
        )
        remaining_count, _remaining_items, remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name="Creative Writing",
            completed_and_planned_courses={"ENG 2005", "JMC 1050", "ENG 3005"},
        )
        self.assertEqual(remaining_count, 2)
        self.assertEqual(remaining_credits, 8)

    def test_suggestions_exclude_already_selected_minors_with_name_normalization(self):
        catalog = _synthetic_catalog(
            ["COS 1020", "ECO 1001", "SUG 1001"],
            {
                "Computer Science": {
                    "required_courses": ["COS 1020"],
                    "elective_requirements": [],
                },
                "Economics": {
                    "required_courses": ["ECO 1001"],
                    "elective_requirements": [],
                },
                "Suggestion Minor": {
                    "required_courses": ["SUG 1001"],
                    "elective_requirements": [],
                },
            },
        )
        suggestions = compute_minor_suggestions(
            catalog=catalog,
            majors=["Computer Science (COS)"],
            minors=["ECONOMICS"],
            completed_courses=set(),
            in_progress_courses=set(),
            semester_plan=[],
            top_k=10,
        )
        suggested_names = {entry.get("minor") for entry in suggestions}
        self.assertIn("Suggestion Minor", suggested_names)
        self.assertNotIn("Computer Science", suggested_names)
        self.assertNotIn("Economics", suggested_names)

    def test_suggestions_use_unique_targets_for_duplicate_free_elective_slots(self):
        catalog = _synthetic_catalog(
            ["SUG 1001", "SUG 1002"],
            {
                "Swap Minor": {
                    "required_courses": ["SUG 1001", "SUG 1002"],
                    "elective_requirements": [],
                }
            },
        )
        semester_plan = [
            {
                "term": "Fall 2027",
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
        by_minor = {
            entry.get("minor"): entry
            for entry in suggestions
            if isinstance(entry, dict)
        }
        self.assertIn("Swap Minor", by_minor)
        swap_minor = by_minor["Swap Minor"]
        self.assertEqual(swap_minor.get("remaining_count"), 2)

        swaps = swap_minor.get("swap_suggestions") or []
        self.assertEqual(len(swaps), 2)
        self.assertEqual(swaps[0].get("replace_instance_id"), "slot-a")
        self.assertEqual(swaps[1].get("replace_instance_id"), "slot-b")
        self.assertEqual(swaps[0].get("replace_slot_index"), 0)
        self.assertEqual(swaps[1].get("replace_slot_index"), 1)
        self.assertEqual(swaps[0].get("term"), "Fall 2027")
        self.assertEqual(swaps[1].get("term"), "Fall 2027")


if __name__ == "__main__":
    unittest.main()

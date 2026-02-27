import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import compute_minor_proximity_smart_details, compute_minor_suggestions  # noqa: E402


def _catalog_with_block(
    *,
    credits_required=None,
    courses_required=None,
    allowed_course_credit: int = 3,
) -> dict:
    return {
        "courses": {
            "ECO 1001": {"name": "Intro Economics 1", "credits": allowed_course_credit},
            "ECO 1002": {"name": "Intro Economics 2", "credits": allowed_course_credit},
            "ECO 2001": {"name": "Intermediate Economics", "credits": allowed_course_credit},
            "BUS 1001": {"name": "Intro Business", "credits": 3},
        },
        "course_meta": {
            "ECO 1001": {"credits": allowed_course_credit, "prereq_codes": []},
            "ECO 1002": {"credits": allowed_course_credit, "prereq_codes": []},
            "ECO 2001": {"credits": allowed_course_credit, "prereq_codes": []},
            "BUS 1001": {"credits": 3, "prereq_codes": []},
        },
        "majors": {},
        "minors": {
            "Test Minor": {
                "required_courses": [],
                "elective_requirements": [
                    {
                        "label": "Electives",
                        "credits_required": credits_required,
                        "courses_required": courses_required,
                        "allowed_courses": ["ECO 1001", "ECO 1002", "ECO 2001"],
                        "rule_text": "Elective ECO courses",
                        "is_total": True,
                    }
                ],
            }
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
    }


class MinorNumericRequirementParsingTests(unittest.TestCase):
    def test_credits_required_numeric_formats_are_counted(self):
        for raw_value in (9, 9.0, "9", "9.0"):
            with self.subTest(credits_required=raw_value):
                catalog = _catalog_with_block(credits_required=raw_value, courses_required=None)
                remaining_count, _remaining_items, remaining_credits = compute_minor_proximity_smart_details(
                    catalog=catalog,
                    minor_name="Test Minor",
                    completed_and_planned_courses={"ECO 1001"},
                )
                # 9 required credits, 3 earned -> 6 deficit => 2 course-equivalents.
                self.assertEqual(remaining_count, 2)
                self.assertEqual(remaining_credits, 6)
                self.assertGreater(remaining_count, 0)

    def test_courses_required_numeric_formats_are_counted(self):
        for raw_value in (2, 2.0, "2"):
            with self.subTest(courses_required=raw_value):
                catalog = _catalog_with_block(credits_required=None, courses_required=raw_value)
                remaining_count, _remaining_items, remaining_credits = compute_minor_proximity_smart_details(
                    catalog=catalog,
                    minor_name="Test Minor",
                    completed_and_planned_courses={"ECO 1001"},
                )
                # 2 courses required, 1 earned -> 1 remaining.
                self.assertEqual(remaining_count, 1)
                self.assertEqual(remaining_credits, 3)
                self.assertGreater(remaining_count, 0)

    def test_credit_deficit_course_equiv_uses_typical_allowed_credit(self):
        # 4-credit allowed courses: 8 required, 4 earned => 4 deficit => 1 course-equivalent
        catalog_4 = _catalog_with_block(
            credits_required=8,
            courses_required=None,
            allowed_course_credit=4,
        )
        remaining_count_4, _items_4, remaining_credits_4 = compute_minor_proximity_smart_details(
            catalog=catalog_4,
            minor_name="Test Minor",
            completed_and_planned_courses={"ECO 1001"},
        )
        self.assertEqual(remaining_count_4, 1)
        self.assertEqual(remaining_credits_4, 4)

        # 3-credit allowed courses: 7 required, 3 earned => 4 deficit => 2 course-equivalents
        catalog_3 = _catalog_with_block(
            credits_required=7,
            courses_required=None,
            allowed_course_credit=3,
        )
        remaining_count_3, _items_3, remaining_credits_3 = compute_minor_proximity_smart_details(
            catalog=catalog_3,
            minor_name="Test Minor",
            completed_and_planned_courses={"ECO 1001"},
        )
        self.assertEqual(remaining_count_3, 2)
        self.assertEqual(remaining_credits_3, 4)

    def test_course_count_credit_estimate_uses_typical_allowed_credit(self):
        catalog_4 = _catalog_with_block(
            credits_required=None,
            courses_required=2,
            allowed_course_credit=4,
        )
        remaining_count_4, _items_4, remaining_credits_4 = compute_minor_proximity_smart_details(
            catalog=catalog_4,
            minor_name="Test Minor",
            completed_and_planned_courses={"ECO 1001"},
        )
        self.assertEqual(remaining_count_4, 1)
        self.assertEqual(remaining_credits_4, 4)

        catalog_3 = _catalog_with_block(
            credits_required=None,
            courses_required=2,
            allowed_course_credit=3,
        )
        remaining_count_3, _items_3, remaining_credits_3 = compute_minor_proximity_smart_details(
            catalog=catalog_3,
            minor_name="Test Minor",
            completed_and_planned_courses={"ECO 1001"},
        )
        self.assertEqual(remaining_count_3, 1)
        self.assertEqual(remaining_credits_3, 3)

    def test_completed_minor_is_not_returned_in_smart_suggestions(self):
        catalog = _catalog_with_block(credits_required=6, courses_required=None)
        suggestions = compute_minor_suggestions(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses={"ECO 1001", "ECO 1002"},
            in_progress_courses=set(),
            semester_plan=[],
            top_k=10,
        )
        self.assertFalse(any(entry.get("minor") == "Test Minor" for entry in suggestions))


if __name__ == "__main__":
    unittest.main()

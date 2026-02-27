import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import generate_plan, validate_plan  # noqa: E402


def build_retake_catalog():
    courses = {
        "AAA 1000": {"name": "Alpha Foundations", "credits": 3, "gen_ed": []},
    }
    course_meta = {
        "AAA 1000": {"credits": 3, "prereq_codes": []},
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Alpha": {"required_courses": ["AAA 1000"], "elective_requirements": []},
        },
        "minors": {},
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }


def _planned_codes(plan: dict) -> list[str]:
    return [
        course.get("code")
        for term in plan.get("semester_plan", [])
        for course in term.get("courses", [])
        if isinstance(course, dict)
    ]


class CourseRetakeTests(unittest.TestCase):
    def test_validate_plan_allows_duplicate_course_codes(self):
        catalog = build_retake_catalog()
        semester_plan = [
            {
                "term": "Fall 2026",
                "courses": [
                    {"code": "AAA 1000", "name": "Alpha Foundations", "credits": 3, "instance_id": "retake-a"}
                ],
                "credits": 3,
            },
            {
                "term": "Spring 2027",
                "courses": [
                    {"code": "AAA 1000", "name": "Alpha Foundations", "credits": 3, "instance_id": "retake-b"}
                ],
                "credits": 3,
            },
        ]
        errors = validate_plan(
            catalog=catalog,
            semester_plan=semester_plan,
            completed_courses=set(),
            start_term=("Fall", 2026),
            min_credits=0,
            max_credits=16,
            strict_prereqs=False,
            remaining_slots=set(),
        )
        self.assertFalse(any("Duplicate course in plan" in e for e in errors), errors)

    def test_validate_plan_requires_unique_instance_ids(self):
        catalog = build_retake_catalog()
        semester_plan = [
            {
                "term": "Fall 2026",
                "courses": [
                    {"code": "AAA 1000", "name": "Alpha Foundations", "credits": 3, "instance_id": "same-id"}
                ],
                "credits": 3,
            },
            {
                "term": "Spring 2027",
                "courses": [
                    {"code": "AAA 1000", "name": "Alpha Foundations", "credits": 3, "instance_id": "same-id"}
                ],
                "credits": 3,
            },
        ]
        errors = validate_plan(
            catalog=catalog,
            semester_plan=semester_plan,
            completed_courses=set(),
            start_term=("Fall", 2026),
            min_credits=0,
            max_credits=16,
            strict_prereqs=False,
            remaining_slots=set(),
        )
        self.assertTrue(any("Duplicate course instance_id in plan" in e for e in errors), errors)

    def test_planner_does_not_schedule_completed_course_without_retake_request(self):
        catalog = build_retake_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
        )
        self.assertNotIn("AAA 1000", _planned_codes(plan))

    def test_requested_retake_can_be_scheduled_twice_and_counts_once(self):
        catalog = build_retake_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            retake_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides={
                "add": [{"term": "Spring 2027", "code": "AAA 1000"}],
                "remove": [],
                "move": [],
            },
        )

        occurrences = [
            course
            for term in plan.get("semester_plan", [])
            for course in term.get("courses", [])
            if isinstance(course, dict) and course.get("code") == "AAA 1000"
        ]
        self.assertEqual(len(occurrences), 2)

        instance_ids = [course.get("instance_id") for course in occurrences if course.get("instance_id")]
        self.assertEqual(len(instance_ids), len(set(instance_ids)))

        major_progress = plan.get("category_progress", {}).get("majors", {}).get("Alpha", {})
        self.assertEqual(major_progress.get("required"), 3)
        self.assertEqual(major_progress.get("completed"), 0)
        self.assertEqual(plan.get("summary", {}).get("total_required_credits"), 3)
        self.assertEqual(plan.get("summary", {}).get("completed_credits"), 0)


if __name__ == "__main__":
    unittest.main()

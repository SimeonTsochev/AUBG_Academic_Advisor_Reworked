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
        "BBB 2000": {"name": "Beta Advanced", "credits": 3, "gen_ed": []},
    }
    course_meta = {
        "AAA 1000": {"credits": 3, "prereq_codes": []},
        "BBB 2000": {"credits": 3, "prereq_codes": ["AAA 1000"]},
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Alpha": {"required_courses": ["AAA 1000", "BBB 2000"], "elective_requirements": []},
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

    def test_validate_plan_accepts_zero_credit_retake_entry(self):
        catalog = build_retake_catalog()
        semester_plan = [
            {
                "term": "Fall 2026",
                "courses": [
                    {
                        "code": "AAA 1000",
                        "name": "Alpha Foundations",
                        "credits": 0,
                        "instance_id": "retake-zero",
                        "is_retake": True,
                    }
                ],
                "credits": 0,
            },
        ]
        errors = validate_plan(
            catalog=catalog,
            semester_plan=semester_plan,
            completed_courses={"AAA 1000"},
            start_term=("Fall", 2026),
            min_credits=0,
            max_credits=16,
            strict_prereqs=False,
            remaining_slots=set(),
        )
        self.assertFalse(any("credits mismatch" in e for e in errors), errors)

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

    def test_manual_retake_override_makes_latest_attempt_credit_bearing(self):
        catalog = build_retake_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides={
                "add": [{
                    "term": "Spring 2027",
                    "code": "AAA 1000",
                    "instance_id": "manual-retake-1",
                    "is_retake": True,
                }],
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
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].get("credits"), 3)
        self.assertTrue(occurrences[0].get("is_retake"))

        instance_ids = [course.get("instance_id") for course in occurrences if course.get("instance_id")]
        self.assertEqual(len(instance_ids), len(set(instance_ids)))

        major_progress = plan.get("category_progress", {}).get("majors", {}).get("Alpha", {})
        self.assertEqual(major_progress.get("required"), 6)
        self.assertEqual(major_progress.get("completed"), 0)
        self.assertEqual(plan.get("summary", {}).get("total_required_credits"), 6)
        self.assertEqual(plan.get("summary", {}).get("completed_credits"), 0)

    def test_manual_multiple_retakes_only_latest_attempt_counts(self):
        catalog = build_retake_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides={
                "add": [
                    {
                        "term": "Fall 2026",
                        "code": "AAA 1000",
                        "instance_id": "manual-retake-a",
                        "is_retake": True,
                    },
                    {
                        "term": "Spring 2027",
                        "code": "AAA 1000",
                        "instance_id": "manual-retake-b",
                        "is_retake": True,
                    },
                ],
                "remove": [],
                "move": [],
            },
        )

        by_instance = {}
        for term in plan.get("semester_plan", []):
            for course in term.get("courses", []):
                if isinstance(course, dict) and course.get("code") == "AAA 1000":
                    by_instance[course.get("instance_id")] = int(course.get("credits") or 0)

        self.assertEqual(by_instance.get("manual-retake-a"), 0)
        self.assertEqual(by_instance.get("manual-retake-b"), 3)

    def test_same_term_tie_break_uses_latest_override_order(self):
        catalog = build_retake_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides={
                "add": [
                    {
                        "term": "Fall 2026",
                        "code": "AAA 1000",
                        "instance_id": "same-term-a",
                        "is_retake": True,
                    },
                    {
                        "term": "Fall 2026",
                        "code": "AAA 1000",
                        "instance_id": "same-term-b",
                        "is_retake": True,
                    },
                ],
                "remove": [],
                "move": [],
            },
        )

        by_instance = {}
        for term in plan.get("semester_plan", []):
            for course in term.get("courses", []):
                if isinstance(course, dict) and course.get("code") == "AAA 1000":
                    by_instance[course.get("instance_id")] = int(course.get("credits") or 0)
        self.assertEqual(by_instance.get("same-term-a"), 0)
        self.assertEqual(by_instance.get("same-term-b"), 3)

    def test_retake_does_not_break_prereq_satisfaction(self):
        catalog = build_retake_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides={
                "add": [
                    {
                        "term": "Spring 2027",
                        "code": "AAA 1000",
                        "instance_id": "manual-retake-prereq",
                        "is_retake": True,
                    }
                ],
                "remove": [],
                "move": [],
            },
        )
        warnings = plan.get("warnings", [])
        prereq_unmet_for_bbb = [
            w for w in warnings
            if isinstance(w, dict)
            and w.get("type") == "PREREQ_UNMET"
            and w.get("course") == "BBB 2000"
        ]
        self.assertEqual(prereq_unmet_for_bbb, [])

    def test_manual_retake_override_bypasses_excel_only_term_availability(self):
        catalog = build_retake_catalog()
        catalog["excel_integrity"] = {"excel_only": ["AAA 1000"], "pdf_only": []}
        catalog["course_meta"]["AAA 1000"]["semester_availability"] = ["Spring 2027"]

        plan = generate_plan(
            catalog=catalog,
            majors=["Alpha"],
            minors=[],
            completed_courses={"AAA 1000"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides={
                "add": [
                    {
                        "term": "Fall 2026",
                        "code": "AAA 1000",
                        "instance_id": "retake-fall-2026",
                        "is_retake": True,
                    }
                ],
                "remove": [],
                "move": [],
            },
        )

        found = [
            course
            for term in plan.get("semester_plan", [])
            if term.get("term") == "Fall 2026"
            for course in term.get("courses", [])
            if isinstance(course, dict) and course.get("instance_id") == "retake-fall-2026"
        ]
        self.assertEqual(len(found), 1)
        self.assertEqual(int(found[0].get("credits") or 0), 3)
        availability_warnings = [
            warning for warning in (plan.get("warnings") or [])
            if isinstance(warning, dict)
            and warning.get("type") == "OVERRIDE_ADD_TERM_UNAVAILABLE"
            and warning.get("course") == "AAA 1000"
        ]
        self.assertEqual(availability_warnings, [])


if __name__ == "__main__":
    unittest.main()

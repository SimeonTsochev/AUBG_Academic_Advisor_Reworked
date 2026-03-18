import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import generate_plan, validate_plan  # noqa: E402


def build_sample_catalog():
    courses = {
        "ENG 1000": {"name": "English Composition", "credits": 3, "gen_ed": ["First-Year Writing"]},
        "MAT 1000": {"name": "College Algebra", "credits": 3, "gen_ed": ["Quantitative Reasoning"]},
        "HIS 1000": {"name": "Historical Sources", "credits": 3, "gen_ed": ["Historical Sources"]},
        "HIS 2000": {"name": "Historical Research", "credits": 3, "gen_ed": ["Historical Research"]},
        "ART 1000": {"name": "Introduction to Art", "credits": 3, "gen_ed": ["Arts"]},
        "SOC 1000": {"name": "Intro to Sociology", "credits": 3, "gen_ed": ["Social Science"]},
        "CS 1100": {"name": "Intro to CS", "credits": 4, "gen_ed": []},
        "CS 1200": {"name": "Data Structures", "credits": 4, "gen_ed": []},
    }

    course_meta = {
        "ENG 1000": {"credits": 3, "gen_ed": "First-Year Writing", "prereq_codes": []},
        "MAT 1000": {"credits": 3, "gen_ed": "Quantitative Reasoning", "prereq_codes": []},
        "HIS 1000": {"credits": 3, "gen_ed": "Historical Sources", "prereq_codes": []},
        "HIS 2000": {"credits": 3, "gen_ed": "Historical Research", "prereq_codes": ["HIS 1000"]},
        "ART 1000": {"credits": 3, "gen_ed": "Arts", "prereq_codes": []},
        "SOC 1000": {"credits": 3, "gen_ed": "Social Science", "prereq_codes": []},
        "CS 1100": {"credits": 4, "gen_ed": None, "prereq_codes": []},
        "CS 1200": {"credits": 4, "gen_ed": None, "prereq_codes": ["CS 1100"]},
    }

    gen_ed_categories = {
        "First-Year Writing": ["ENG 1000"],
        "Quantitative Reasoning": ["MAT 1000"],
        "Historical Sources": ["HIS 1000"],
        "Historical Research": ["HIS 2000"],
        "Arts": ["ART 1000"],
        "Social Science": ["SOC 1000"],
    }

    gen_ed_rules = {category: 1 for category in gen_ed_categories.keys()}

    catalog = {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            "Computer Science": {"required_courses": ["CS 1100", "CS 1200"], "elective_requirements": []}
        },
        "minors": {},
        "foundation_courses": ["ENG 1000", "MAT 1000"],
        "gen_ed": {
            "categories": gen_ed_categories,
            "rules": gen_ed_rules,
        },
    }
    return catalog


def plan_course(catalog, code, course_type="PROGRAM", satisfies=None):
    meta = catalog["course_meta"][code]
    return {
        "code": code,
        "name": catalog["courses"][code]["name"],
        "credits": meta["credits"],
        "tags": ["Planned"],
        "satisfies": satisfies or [],
        "type": course_type,
    }


class PlanValidationTests(unittest.TestCase):
    def test_generate_plan_is_valid(self):
        catalog = build_sample_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        self.assertGreater(len(plan["semester_plan"]), 0)
        self.assertEqual(plan.get("warnings", []), [])

    def test_manual_transfer_credits_adjust_credit_progress_without_affecting_prereqs(self):
        catalog = build_sample_catalog()
        baseline = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        plan = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            manual_credits=[
                {
                    "code": "OTH 0001",
                    "instance_id": "manual-major-1",
                    "term": "Spring 2025",
                    "credits": 3,
                    "credit_type": "MAJOR_ELECTIVE",
                    "program": "Computer Science",
                },
                {
                    "code": "OTH 0001",
                    "instance_id": "manual-gened-1",
                    "term": "Spring 2025",
                    "credits": 3,
                    "credit_type": "GENED",
                    "gened_category": "Arts",
                },
            ],
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )

        self.assertEqual(
            plan["summary"]["completed_credits"],
            baseline["summary"]["completed_credits"] + 6,
        )
        self.assertEqual(
            plan["category_progress"]["majors"]["Computer Science"]["completed"],
            baseline["category_progress"]["majors"]["Computer Science"]["completed"] + 3,
        )
        self.assertEqual(
            plan["category_progress"]["gen_ed"]["completed"],
            baseline["category_progress"]["gen_ed"]["completed"] + 3,
        )
        self.assertNotIn(
            "OTH 0001",
            {
                rec.get("code")
                for rec in plan.get("elective_recommendations", [])
                if isinstance(rec, dict)
            },
        )
        self.assertEqual(
            [w for w in plan.get("warnings", []) if w.get("type") == "PREREQ_UNMET"],
            [w for w in baseline.get("warnings", []) if w.get("type") == "PREREQ_UNMET"],
        )

    def test_manual_gened_transfer_credit_prevents_redundant_gened_course_scheduling(self):
        catalog = build_sample_catalog()
        plan = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            manual_credits=[
                {
                    "code": "OTH 0001",
                    "instance_id": "manual-gened-arts",
                    "term": "Spring 2025",
                    "credits": 3,
                    "credit_type": "GENED",
                    "gened_category": "Arts",
                }
            ],
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )

        planned_codes = {
            course.get("code")
            for term in plan.get("semester_plan", [])
            for course in term.get("courses", [])
            if isinstance(course, dict)
        }
        self.assertNotIn("ART 1000", planned_codes)

    def test_aesthetic_expression_prefers_highest_credit_course(self):
        catalog = build_sample_catalog()
        catalog["courses"]["ART 1001"] = {
            "name": "Studio Basics",
            "credits": 2,
            "gen_ed": ["Aesthetic Expression"],
        }
        catalog["courses"]["THR 1001"] = {
            "name": "Intro to Theater",
            "credits": 3,
            "gen_ed": ["Aesthetic Expression"],
        }
        catalog["course_meta"]["ART 1001"] = {
            "credits": 2,
            "gen_ed": "Aesthetic Expression",
            "prereq_codes": [],
        }
        catalog["course_meta"]["THR 1001"] = {
            "credits": 3,
            "gen_ed": "Aesthetic Expression",
            "prereq_codes": [],
        }
        catalog["gen_ed"]["categories"]["Aesthetic Expression"] = ["ART 1001", "THR 1001"]
        catalog["gen_ed"]["rules"]["Aesthetic Expression"] = 1

        plan = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )

        planned_codes = {
            course.get("code")
            for term in plan.get("semester_plan", [])
            for course in term.get("courses", [])
            if isinstance(course, dict)
        }
        self.assertIn("THR 1001", planned_codes)
        self.assertNotIn("ART 1001", planned_codes)

    def test_validate_plan_catches_prereq_violation(self):
        catalog = build_sample_catalog()
        semester_plan = [
            {
                "term": "Fall 2025",
                "courses": [plan_course(catalog, "CS 1200")],
                "credits": 4,
            },
            {
                "term": "Spring 2026",
                "courses": [plan_course(catalog, "CS 1100")],
                "credits": 4,
            },
        ]
        errors = validate_plan(
            catalog=catalog,
            semester_plan=semester_plan,
            completed_courses=set(),
            start_term=("Fall", 2025),
            min_credits=0,
            max_credits=16,
            remaining_slots=set(),
            strict_prereqs=True,
        )
        self.assertTrue(any("prerequisite" in e.lower() for e in errors))

    def test_choice_group_with_insufficient_courses_is_clamped(self):
        catalog = build_sample_catalog()
        catalog["majors"] = {
            "Computer Science": {
                "required_courses": [],
                "elective_requirements": [
                    {
                        "id": "computer-science-elective-1",
                        "label": "Elective Courses",
                        "credits_required": 6,
                        "courses_required": None,
                        "allowed_courses": ["CS 1100"],
                        "rule_text": "Choose electives.",
                    }
                ],
            }
        }
        plan = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        self.assertGreater(len(plan["semester_plan"]), 0)

    def test_excel_only_override_add_unavailable_term_emits_warning_and_skips_add(self):
        catalog = build_sample_catalog()
        catalog["courses"]["SCI 1010"] = {
            "name": "Integrated Science",
            "credits": 3,
            "gen_ed": ["Scientific Investigation"],
        }
        catalog["course_meta"]["SCI 1010"] = {
            "credits": 3,
            "gen_ed": "Scientific Investigation",
            "semester_availability": ["Fall 2025"],
            "prereq_codes": [],
        }
        catalog["excel_integrity"] = {"excel_only": ["SCI 1010"]}

        plan = generate_plan(
            catalog=catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
            overrides={
                "add": [
                    {
                        "term": "Spring 2026",
                        "code": "SCI 1010",
                        "instance_id": "test-sci-1010",
                    }
                ],
                "remove": [],
                "move": [],
            },
        )

        warnings = plan.get("warnings", [])
        self.assertTrue(
            any(
                warning.get("type") == "OVERRIDE_ADD_TERM_UNAVAILABLE"
                and warning.get("course") == "SCI 1010"
                and warning.get("term") == "Spring 2026"
                for warning in warnings
                if isinstance(warning, dict)
            )
        )

        planned_codes = {
            course.get("code")
            for term in plan.get("semester_plan", [])
            for course in term.get("courses", [])
            if isinstance(course, dict)
        }
        self.assertNotIn("SCI 1010", planned_codes)

    def test_textual_analysis_case_studies_requires_principles_and_eng1002(self):
        catalog = {
            "courses": {
                "ENG 1002": {"name": "Academic Writing", "credits": 3, "gen_ed": []},
                "ENG 2005": {
                    "name": "Introduction to Creative Writing",
                    "credits": 3,
                    "gen_ed": ["Principles of Textual Analysis"],
                },
                "ENG 3005": {
                    "name": "Advanced Fiction Workshop",
                    "credits": 3,
                    "gen_ed": ["Case Studies in Textual Analysis"],
                },
            },
            "course_meta": {
                "ENG 1002": {"credits": 3, "gen_ed": None, "prereq_codes": []},
                "ENG 2005": {
                    "credits": 3,
                    "gen_ed": "Principles of Textual Analysis",
                    "prereq_codes": [],
                },
                "ENG 3005": {
                    "credits": 3,
                    "gen_ed": "Case Studies in Textual Analysis",
                    "prereq_codes": [],
                },
            },
            "majors": {},
            "minors": {},
            "foundation_courses": [],
            "gen_ed": {
                "categories": {
                    "Principles of Textual Analysis": ["ENG 2005"],
                    "Case Studies in Textual Analysis": ["ENG 3005"],
                },
                "rules": {
                    "Principles of Textual Analysis": 1,
                    "Case Studies in Textual Analysis": 1,
                },
            },
        }

        plan = generate_plan(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses={"ENG 1002"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )

        term_index_by_code = {}
        for idx, term in enumerate(plan.get("semester_plan", [])):
            for course in term.get("courses", []):
                code = course.get("code")
                if isinstance(code, str) and code not in term_index_by_code:
                    term_index_by_code[code] = idx

        self.assertIn("ENG 2005", term_index_by_code)
        self.assertIn("ENG 3005", term_index_by_code)
        self.assertLess(term_index_by_code["ENG 2005"], term_index_by_code["ENG 3005"])

    def test_move_override_rejects_case_studies_before_principles(self):
        catalog = {
            "courses": {
                "ENG 1002": {"name": "Academic Writing", "credits": 3, "gen_ed": []},
                "ENG 2005": {
                    "name": "Introduction to Creative Writing",
                    "credits": 3,
                    "gen_ed": ["Principles of Textual Analysis"],
                },
                "ENG 3005": {
                    "name": "Advanced Fiction Workshop",
                    "credits": 3,
                    "gen_ed": ["Case Studies in Textual Analysis"],
                },
            },
            "course_meta": {
                "ENG 1002": {"credits": 3, "gen_ed": None, "prereq_codes": []},
                "ENG 2005": {
                    "credits": 3,
                    "gen_ed": "Principles of Textual Analysis",
                    "prereq_codes": [],
                },
                "ENG 3005": {
                    "credits": 3,
                    "gen_ed": "Case Studies in Textual Analysis",
                    "prereq_codes": [],
                },
            },
            "majors": {},
            "minors": {},
            "foundation_courses": [],
            "gen_ed": {
                "categories": {
                    "Principles of Textual Analysis": ["ENG 2005"],
                    "Case Studies in Textual Analysis": ["ENG 3005"],
                },
                "rules": {
                    "Principles of Textual Analysis": 1,
                    "Case Studies in Textual Analysis": 1,
                },
            },
        }

        base = generate_plan(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses={"ENG 1002"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )
        term_by_code = {}
        for term in base.get("semester_plan", []):
            for course in term.get("courses", []):
                code = course.get("code")
                if isinstance(code, str):
                    term_by_code[code] = term.get("term")

        case_term = term_by_code.get("ENG 3005")
        principles_term = term_by_code.get("ENG 2005")
        self.assertIsNotNone(case_term)
        self.assertIsNotNone(principles_term)

        moved = generate_plan(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses={"ENG 1002"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
            overrides={
                "add": [],
                "remove": [],
                "move": [
                    {
                        "from_term": case_term,
                        "to_term": principles_term,
                        "code": "ENG 3005",
                    }
                ],
            },
        )

        warnings = moved.get("warnings", [])
        self.assertTrue(
            any(
                isinstance(warning, dict)
                and warning.get("type") == "OVERRIDE_MOVE_INELIGIBLE"
                and warning.get("course") == "ENG 3005"
                for warning in warnings
            )
        )

        moved_term_by_code = {}
        for term in moved.get("semester_plan", []):
            for course in term.get("courses", []):
                code = course.get("code")
                if isinstance(code, str):
                    moved_term_by_code[code] = term.get("term")
        self.assertEqual(moved_term_by_code.get("ENG 3005"), case_term)


if __name__ == "__main__":
    unittest.main()

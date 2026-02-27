import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import (  # noqa: E402
    _compute_minor_alerts,
    _is_selected_program_minor,
    compute_minor_suggestions,
)


def _catalog_for_name_matching() -> dict:
    return {
        "courses": {
            "COS 1020": {"name": "Intro to Programming", "credits": 3},
            "COS 1050": {"name": "Discrete Structures", "credits": 3},
            "COS 2021": {"name": "Data Structures", "credits": 3},
            "COS 2031": {"name": "UNIX", "credits": 3},
            "ECO 1001": {"name": "Principles of Economics I", "credits": 3},
            "ECO 1002": {"name": "Principles of Economics II", "credits": 3},
            "ECO 3001": {"name": "Intermediate Macro", "credits": 3},
            "ECO 3002": {"name": "Intermediate Micro", "credits": 3},
        },
        "course_meta": {
            "COS 1020": {"credits": 3, "prereq_codes": []},
            "COS 1050": {"credits": 3, "prereq_codes": []},
            "COS 2021": {"credits": 3, "prereq_codes": []},
            "COS 2031": {"credits": 3, "prereq_codes": []},
            "ECO 1001": {"credits": 3, "prereq_codes": []},
            "ECO 1002": {"credits": 3, "prereq_codes": []},
            "ECO 3001": {"credits": 3, "prereq_codes": []},
            "ECO 3002": {"credits": 3, "prereq_codes": []},
        },
        "majors": {},
        "minors": {
            "Computer Science": {
                "required_courses": [],
                "elective_requirements": [
                    {
                        "label": "Electives",
                        "credits_required": None,
                        "courses_required": 1,
                        "allowed_courses": ["COS 1050", "COS 2021", "COS 2031"],
                        "rule_text": "",
                        "is_total": True,
                    }
                ],
            },
            "Economics": {
                "required_courses": [],
                "elective_requirements": [],
            },
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
    }


class MinorNameNormalizationTests(unittest.TestCase):
    def test_normalized_name_matching_for_selected_programs(self):
        self.assertTrue(
            _is_selected_program_minor(
                "Computer Science",
                majors=["Computer Science (COS)"],
                minors=[],
            )
        )
        self.assertTrue(
            _is_selected_program_minor(
                "Economics",
                majors=[],
                minors=["ECONOMICS"],
            )
        )

    def test_compute_minor_suggestions_excludes_selected_by_normalized_name(self):
        catalog = _catalog_for_name_matching()
        taken = {"COS 1020", "COS 1050", "COS 2021", "COS 2031", "ECO 1001", "ECO 1002"}

        unselected = compute_minor_suggestions(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses=set(taken),
            in_progress_courses=set(),
            semester_plan=[],
            top_k=10,
        )
        self.assertIn("Computer Science", [item.get("minor") for item in unselected])
        self.assertIn("Economics", [item.get("minor") for item in unselected])

        selected = compute_minor_suggestions(
            catalog=catalog,
            majors=["Computer Science (COS)"],
            minors=["ECONOMICS"],
            completed_courses=set(taken),
            in_progress_courses=set(),
            semester_plan=[],
            top_k=10,
        )
        self.assertNotIn("Computer Science", [item.get("minor") for item in selected])
        self.assertNotIn("Economics", [item.get("minor") for item in selected])

    def test_compute_minor_alerts_excludes_selected_by_normalized_name(self):
        catalog = _catalog_for_name_matching()
        taken = {"COS 1020", "COS 1050", "COS 2021", "COS 2031", "ECO 1001", "ECO 1002"}

        unselected = _compute_minor_alerts(
            catalog=catalog,
            majors=[],
            minors=[],
            completed_courses=set(taken),
            in_progress_courses=set(),
            semester_plan=[],
        )
        self.assertIn("Computer Science", [item.get("minor") for item in unselected])
        self.assertIn("Economics", [item.get("minor") for item in unselected])

        selected = _compute_minor_alerts(
            catalog=catalog,
            majors=["Computer Science (COS)"],
            minors=["ECONOMICS"],
            completed_courses=set(taken),
            in_progress_courses=set(),
            semester_plan=[],
        )
        self.assertNotIn("Computer Science", [item.get("minor") for item in selected])
        self.assertNotIn("Economics", [item.get("minor") for item in selected])


if __name__ == "__main__":
    unittest.main()

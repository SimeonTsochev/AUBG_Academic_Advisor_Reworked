import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import compute_minor_proximity_smart_details, _compute_minor_alerts  # noqa: E402


def build_catalog(minor_key: str = "Computer Science") -> dict:
    courses = {
        "COS 1020": {"name": "Intro to Programming", "credits": 3, "gen_ed": []},
        "COS 1050": {"name": "Discrete Structures", "credits": 3, "gen_ed": []},
        "COS 2021": {"name": "Data Structures", "credits": 3, "gen_ed": []},
        "COS 2031": {"name": "UNIX", "credits": 3, "gen_ed": []},
        "COS 2035": {"name": "Computer Architecture", "credits": 3, "gen_ed": []},
        "COS 3015": {"name": "Software Engineering", "credits": 3, "gen_ed": []},
        "COS 3031": {"name": "Operating Systems", "credits": 3, "gen_ed": []},
        "COS 4040": {"name": "Computer Networks", "credits": 3, "gen_ed": []},
        "COS 4060": {"name": "Algorithms", "credits": 3, "gen_ed": []},
        "COS 4070": {"name": "AI", "credits": 3, "gen_ed": []},
        "MAT 2050": {"name": "Theory of Automata", "credits": 3, "gen_ed": []},
    }
    course_meta = {code: {"credits": 3, "prereq_codes": []} for code in courses}
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {"Business": {"required_courses": []}},
        "minors": {
            minor_key: {
                "required_courses": [],
                "elective_requirements": [
                    {
                        "id": "computer-science-elective-1",
                        "label": "Electives",
                        "credits_required": None,
                        "courses_required": 1,
                        "allowed_courses": [
                            "COS 1050",
                            "COS 2021",
                            "COS 2031",
                            "COS 2035",
                            "COS 3015",
                            "COS 3031",
                            "COS 4040",
                            "COS 4060",
                            "COS 4070",
                            "MAT 2050",
                        ],
                        "rule_text": "Fifteen credit hours with at least one course from Foundations, Software Development, and Advanced Topics.",
                        "is_total": True,
                    }
                ],
            }
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {}, "rules": {"Dummy": 0}},
    }


class ComputerScienceMinorProximityTests(unittest.TestCase):
    def test_cs_minor_requires_core_groups_and_credits(self):
        catalog = build_catalog()
        remaining_count, remaining_items, remaining_credits = compute_minor_proximity_smart_details(
            catalog,
            "Computer Science",
            set(),
        )
        self.assertEqual(remaining_count, 9)
        self.assertEqual(remaining_credits, 27)
        self.assertIn("COS 1020", remaining_items)
        self.assertIn("CS elective (Foundations)", remaining_items)
        self.assertIn("CS elective (Software Development)", remaining_items)
        self.assertIn("CS elective (Advanced Topics)", remaining_items)
        self.assertGreaterEqual(len(remaining_items), remaining_count)

    def test_cs_minor_group_requirement_not_bypassed_by_credits(self):
        catalog = build_catalog()
        taken = {
            "COS 1020",
            "COS 1050",
            "COS 2035",
            "COS 3015",
            "COS 4060",
            "MAT 2050",
        }  # 15 credits but no Advanced Topics course
        remaining_count, remaining_items, remaining_credits = compute_minor_proximity_smart_details(
            catalog,
            "Computer Science",
            taken,
        )
        self.assertEqual(remaining_count, 1)
        self.assertEqual(remaining_credits, 3)
        self.assertIn("CS elective (Advanced Topics)", remaining_items)

    def test_cs_minor_alert_only_when_truly_close(self):
        catalog = build_catalog()

        # Case 1: no CS progress -> should not alert.
        far_alerts = _compute_minor_alerts(
            catalog=catalog,
            majors=["Business"],
            minors=[],
            completed_courses=set(),
            in_progress_courses=set(),
            semester_plan=[],
        )
        self.assertIsNone(next((a for a in far_alerts if a.get("minor") == "Computer Science"), None))

        # Case 2: credits almost met but missing a required group -> should not alert.
        almost_taken_missing_group = {
            "COS 1020",
            "COS 1050",
            "COS 2035",
            "COS 3015",
            "COS 4060",
            "MAT 2050",
        }  # 15 elective credits, but no Advanced Topics group.
        blocked_alerts = _compute_minor_alerts(
            catalog=catalog,
            majors=["Business"],
            minors=[],
            completed_courses=almost_taken_missing_group,
            in_progress_courses=set(),
            semester_plan=[],
        )
        self.assertIsNone(next((a for a in blocked_alerts if a.get("minor") == "Computer Science"), None))

        # Case 3: truly close (1-2 remaining and structural constraints satisfied) -> alert present.
        near_taken = {"COS 1020", "COS 1050", "COS 2021", "COS 2031"}  # groups covered, 9 elective credits -> 6 credits short
        near_alerts = _compute_minor_alerts(
            catalog=catalog,
            majors=["Business"],
            minors=[],
            completed_courses=near_taken,
            in_progress_courses=set(),
            semester_plan=[],
        )
        cs_alert = next((a for a in near_alerts if a.get("minor") == "Computer Science"), None)
        self.assertIsNotNone(cs_alert)
        self.assertEqual(cs_alert.get("remaining_count"), 2)

    def test_cs_alias_key_triggers_cs_branch(self):
        catalog = build_catalog(minor_key="Computer Science (COS)")
        remaining_count, remaining_items, remaining_credits = compute_minor_proximity_smart_details(
            catalog,
            "Computer Science (COS)",
            set(),
        )
        self.assertEqual(remaining_count, 9)
        self.assertEqual(remaining_credits, 27)
        self.assertIn("COS 1020", remaining_items)
        self.assertIn("CS elective (Foundations)", remaining_items)
        self.assertNotIn("Computer Science (COS) elective (Electives)", remaining_items)

    def test_default_catalog_cs_key_triggers_cs_branch(self):
        try:
            from main import _load_default_catalog
        except Exception as e:  # pragma: no cover - defensive fallback in constrained envs
            self.skipTest(f"Cannot import default catalog loader: {e}")

        try:
            catalog = _load_default_catalog()
        except Exception as e:  # pragma: no cover - defensive fallback in constrained envs
            self.skipTest(f"Cannot load default catalog: {e}")

        cs_key = next(
            (
                key
                for key in catalog.get("minors", {}).keys()
                if isinstance(key, str)
                and (
                    "computer science" in key.lower()
                    or key.lower().startswith("cos")
                    or "(cos" in key.lower()
                )
            ),
            None,
        )
        self.assertIsNotNone(cs_key)
        remaining_count, remaining_items, _remaining_credits = compute_minor_proximity_smart_details(
            catalog,
            cs_key,  # exact key from /catalog/load-default minor list
            set(),
        )
        self.assertGreater(remaining_count, 2)
        self.assertIn("COS 1020", remaining_items)
        self.assertTrue(any(item.startswith("CS elective (") for item in remaining_items))
        self.assertNotIn(f"{cs_key} elective (Electives)", remaining_items)


if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import generate_plan  # noqa: E402


def build_tiny_catalog() -> dict:
    courses = {
        "AAA 1000": {"name": "Alpha", "credits": 3, "gen_ed": []},
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


class InstanceIdOverrideTests(unittest.TestCase):
    def _generate(self, overrides=None):
        return generate_plan(
            catalog=build_tiny_catalog(),
            majors=["Alpha"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
            overrides=overrides,
        )

    def test_instance_ids_present(self):
        plan = self._generate()
        for term in plan["semester_plan"]:
            for course in term["courses"]:
                self.assertTrue(course.get("instance_id"))

    def test_remove_free_elective_by_instance_id(self):
        plan = self._generate()
        term = plan["semester_plan"][0]
        free_courses = [c for c in term["courses"] if c.get("type") == "FREE_ELECTIVE"]
        self.assertTrue(free_courses)
        target = free_courses[0]
        overrides = {
            "add": [],
            "remove": [{
                "term": term["term"],
                "code": target["code"],
                "instance_id": target["instance_id"],
            }],
            "move": [],
        }
        updated = self._generate(overrides=overrides)
        updated_term = next(t for t in updated["semester_plan"] if t["term"] == term["term"])
        updated_ids = [c.get("instance_id") for c in updated_term["courses"]]
        self.assertNotIn(target["instance_id"], updated_ids)
        if len(free_courses) > 1:
            self.assertIn(free_courses[1]["instance_id"], updated_ids)
        updated_free = [c for c in updated_term["courses"] if c.get("type") == "FREE_ELECTIVE"]
        self.assertEqual(len(updated_free), max(0, len(free_courses) - 1))

    def test_remove_required_course_by_instance_id(self):
        plan = self._generate()
        term = plan["semester_plan"][0]
        required = next(c for c in term["courses"] if c.get("code") == "AAA 1000")
        overrides = {
            "add": [],
            "remove": [{
                "term": term["term"],
                "code": required["code"],
                "instance_id": required["instance_id"],
            }],
            "move": [],
        }
        updated = self._generate(overrides=overrides)
        scheduled_codes = {c["code"] for t in updated["semester_plan"] for c in t["courses"]}
        self.assertNotIn("AAA 1000", scheduled_codes)


if __name__ == "__main__":
    unittest.main()

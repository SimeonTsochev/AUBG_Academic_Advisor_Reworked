import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import build_requirement_slots, generate_plan  # noqa: E402


class MajorProgramChoiceRegressionTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        cls.catalog = getCatalogCache().default_catalog

    def test_computer_science_program_choice_block_creates_required_major_slots(self):
        slots = build_requirement_slots(self.catalog, majors=["Computer Science"], minors=[])
        program_slots = [
            slot
            for slot in slots.get("slots", [])
            if slot.get("owner") == "program" and slot.get("program") == "Computer Science"
        ]
        fixed_courses = {
            slot.get("course")
            for slot in program_slots
            if slot.get("type") == "fixed"
        }
        self.assertTrue(
            {"COS 1020", "COS 1050", "COS 2021", "COS 2030", "COS 2035", "COS 3015", "COS 4091"}.issubset(
                fixed_courses
            )
        )
        choice_sets = [
            set(slot.get("courses") or [])
            for slot in program_slots
            if slot.get("type") == "choice"
        ]
        self.assertNotIn({"COS 1020", "COS 1050"}, choice_sets)

    def test_computer_science_program_choice_block_is_not_left_as_elective_placeholder(self):
        plan = generate_plan(
            catalog=self.catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
        )
        major_progress = (plan.get("category_progress", {}).get("majors", {}) or {}).get("Computer Science")
        self.assertIsNotNone(major_progress)
        self.assertGreater(int((major_progress or {}).get("required", 0) or 0), 0)

        placeholder_labels = [
            item.get("label")
            for item in plan.get("elective_placeholders", [])
            if item.get("program") == "Computer Science"
        ]
        self.assertIn("Elective Courses", placeholder_labels)
        self.assertNotIn("Program Choice", placeholder_labels)

    def test_political_science_major_requires_pos2002_and_a_comparative_politics_choice(self):
        # AY 2026-27 catalog p.108: POS 1001, POS 1002, "POS 2013 ... or EUR 2013 Comparative Politics", POS 2002.
        slots = build_requirement_slots(
            self.catalog,
            majors=["Political Science and International Relations"],
            minors=[],
        )
        program_slots = [
            slot
            for slot in slots.get("slots", [])
            if slot.get("owner") == "program"
            and slot.get("program") == "Political Science and International Relations"
        ]
        fixed_courses = {
            slot.get("course")
            for slot in program_slots
            if slot.get("type") == "fixed"
        }
        self.assertEqual(fixed_courses, {"POS 1001", "POS 1002", "POS 2002"})

        choice_sets = [
            set(slot.get("courses") or [])
            for slot in program_slots
            if slot.get("type") == "choice"
        ]
        self.assertEqual(choice_sets, [{"EUR 2013", "POS 2013"}])


if __name__ == "__main__":
    unittest.main()

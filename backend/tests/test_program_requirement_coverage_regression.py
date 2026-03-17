import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import build_requirement_slots, generate_plan  # noqa: E402


class ProgramRequirementCoverageRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = getCatalogCache().default_catalog

    def _program_slots(self, program_name: str, program_type: str):
        slots = build_requirement_slots(
            self.catalog,
            [program_name] if program_type == "major" else [],
            [program_name] if program_type == "minor" else [],
        )
        return [
            slot
            for slot in slots.get("slots", [])
            if slot.get("owner") == "program"
            and slot.get("program") == program_name
            and slot.get("program_type") == program_type
        ]

    def test_literature_major_keeps_required_courses_that_also_appear_in_elective_pools(self):
        slots = self._program_slots("Literature", "major")
        fixed_courses = {
            slot.get("course")
            for slot in slots
            if slot.get("type") == "fixed"
        }
        self.assertTrue(
            {"ENG 2010", "ENG 2031", "ENG 2032", "ENG 2041", "ENG 2042", "ENG 2051", "ENG 2052", "ENG 3088"}.issubset(
                fixed_courses
            )
        )

    def test_information_systems_minor_program_choice_courses_are_scheduled_as_requirements(self):
        slots = self._program_slots("Information Systems", "minor")
        fixed_courses = {
            slot.get("course")
            for slot in slots
            if slot.get("type") == "fixed"
        }
        self.assertTrue({"INF 1030", "INF 2070", "INF 2080"}.issubset(fixed_courses))

        plan = generate_plan(
            catalog=self.catalog,
            majors=[],
            minors=["Information Systems"],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
        )
        progress = ((plan.get("category_progress") or {}).get("minors") or {}).get("Information Systems")
        self.assertIsNotNone(progress)
        self.assertGreater(int((progress or {}).get("required", 0) or 0), 0)

    def test_integrated_marketing_communications_minor_keeps_or_choice_and_fixed_courses(self):
        slots = self._program_slots("Integrated Marketing Communications", "minor")
        fixed_courses = {
            slot.get("course")
            for slot in slots
            if slot.get("type") == "fixed"
        }
        self.assertTrue({"BUS 3062", "JMC 1041", "JMC 1050"}.issubset(fixed_courses))

        choice_sets = {
            tuple(sorted(slot.get("courses") or []))
            for slot in slots
            if slot.get("type") == "choice"
        }
        self.assertIn(("BUS 2060", "ENT 2061"), choice_sets)

    def test_mathematics_minor_keeps_required_mat2001_and_program_choice(self):
        slots = self._program_slots("Mathematics", "minor")
        fixed_courses = {
            slot.get("course")
            for slot in slots
            if slot.get("type") == "fixed"
        }
        self.assertIn("MAT 2001", fixed_courses)

        choice_sets = {
            tuple(sorted(slot.get("courses") or []))
            for slot in slots
            if slot.get("type") == "choice"
        }
        self.assertIn(("MAT 2012", "MAT 2013"), choice_sets)

    def test_political_science_minor_keeps_program_choice(self):
        slots = self._program_slots("Political Science and International Relations", "minor")
        choice_sets = {
            tuple(sorted(slot.get("courses") or []))
            for slot in slots
            if slot.get("type") == "choice"
        }
        self.assertIn(("EUR 2013", "POS 2002"), choice_sets)

    def test_creative_writing_minor_program_choice_is_not_only_a_placeholder(self):
        slots = self._program_slots("Creative Writing", "minor")
        choice_sets = {
            tuple(sorted(slot.get("courses") or []))
            for slot in slots
            if slot.get("type") == "choice"
        }
        self.assertIn(("ENG 2005", "ENG 2006"), choice_sets)

        plan = generate_plan(
            catalog=self.catalog,
            majors=[],
            minors=["Creative Writing"],
            completed_courses=set(),
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2026,
        )
        placeholder_labels = [
            item.get("label")
            for item in plan.get("elective_placeholders", [])
            if item.get("program") == "Creative Writing"
        ]
        self.assertNotIn("Program Choice", placeholder_labels)

    def test_computer_science_minor_includes_core_course_and_group_requirements(self):
        slots = self._program_slots("Computer Science", "minor")
        fixed_courses = {
            slot.get("course")
            for slot in slots
            if slot.get("type") == "fixed"
        }
        self.assertIn("COS 1020", fixed_courses)

        choice_labels = {
            str(slot.get("label") or "")
            for slot in slots
            if slot.get("type") == "choice"
        }
        self.assertIn("Computer Science group (Foundations)", choice_labels)
        self.assertIn("Computer Science group (Software Development)", choice_labels)
        self.assertIn("Computer Science group (Advanced Topics)", choice_labels)

    def test_fine_arts_minor_includes_group_requirements(self):
        slots = self._program_slots("Fine Arts", "minor")
        choice_labels = [
            str(slot.get("label") or "")
            for slot in slots
            if slot.get("type") == "choice"
        ]
        self.assertIn("Fine Arts group A", choice_labels)
        self.assertIn("Fine Arts group B", choice_labels)
        self.assertIn("Fine Arts group C", choice_labels)


if __name__ == "__main__":
    unittest.main()

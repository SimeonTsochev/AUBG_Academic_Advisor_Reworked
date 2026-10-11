"""Options a major offers (catalog `majors.<name>.options`): CS concentrations and the European Studies language."""
import os
import sys
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

import degree_engine  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import generate_plan  # noqa: E402

FOUNDATIONS = {"COS 3031", "COS 4040", "COS 4070", "COS 4081", "INF 2080", "MAT 2014", "MAT 2050"}
SOFTWARE_DEVELOPMENT = {"COS 2031", "COS 3040", "COS 4081", "INF 1030", "INF 2080", "INF 3035", "INF 3075"}


class ProgramOptionTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = getCatalogCache().default_catalog

    def _plan(self, major, options=None):
        with patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026)):
            return generate_plan(
                catalog=self.catalog,
                majors=[major],
                minors=[],
                completed_courses=set(),
                start_term_season="Fall",
                start_term_year=2026,
                program_options={major: options} if options is not None else None,
            )

    @staticmethod
    def _labelled(plan, text):
        return {
            course["code"]
            for term in plan["semester_plan"]
            for course in term["courses"]
            if any(text in (r.get("label") or "") for r in course.get("requirements") or [])
        }

    def _elective(self, plan, program):
        return next(e for e in plan["elective_progress"] if e["program"] == program and e["program_type"] == "major")

    def test_european_studies_needs_a_language(self):
        plan = self._plan("European Studies")
        self.assertTrue(any("B1 proficiency" in e for e in plan["validation_errors"]))
        self.assertEqual(plan["graduation_checks"]["program_options"], {"European Studies": []})

    def test_french_plans_the_french_track_outside_the_major_credits(self):
        plan = self._plan("European Studies", ["French"])
        self.assertFalse(any("B1 proficiency" in e for e in plan["validation_errors"]))
        french = self._labelled(plan, "French language proficiency (B1)")
        self.assertTrue({"MLL 1015", "MLL 1016", "MLL 2015"} <= french)
        self.assertEqual(len(french & {"MLL 2016", "MLL 2017"}), 1)
        # The language is collateral: the major's own 28 credits are the required courses plus electives.
        required = sum(
            course["credits"]
            for term in plan["semester_plan"]
            for course in term["courses"]
            if any(r.get("kind") == "required" and r.get("program") == "European Studies" for r in course.get("requirements") or [])
        )
        self.assertEqual(required + self._elective(plan, "European Studies")["credits_required"], 28)

    def test_language_progress_is_its_own_row_not_the_majors_credits(self):
        progress = self._plan("European Studies", ["French"])["category_progress"]
        self.assertEqual(progress["majors"]["European Studies"]["required"], 9)
        language = progress["options"]["European Studies: French language proficiency (B1)"]
        self.assertEqual((language["program"], language["required"]), ("European Studies", 12))

    def test_a_b1_certificate_waives_the_language_courses(self):
        plan = self._plan("European Studies", ["Waived (B1 certificate)"])
        self.assertFalse(any("B1 proficiency" in e for e in plan["validation_errors"]))
        self.assertEqual(self._labelled(plan, "language proficiency"), set())

    def test_language_courses_are_not_european_studies_electives(self):
        blocks = self.catalog["majors"]["European Studies"]["elective_requirements"]
        allowed = {code for block in blocks for code in block.get("allowed_courses") or []}
        self.assertNotIn("MLL 1015", allowed)
        self.assertNotIn("EUR 4092", allowed)
        self.assertIn("MLL 3001", allowed)

    def test_foundations_of_computing_fills_the_cs_electives(self):
        plan = self._plan("Computer Science", ["Foundations of Computing"])
        self.assertEqual(plan["validation_errors"], [])
        chosen = self._labelled(plan, "Foundations of Computing concentration")
        self.assertEqual(len(chosen), 4)
        self.assertTrue(chosen <= FOUNDATIONS)
        self.assertEqual(self._elective(plan, "Computer Science")["remaining"], 0)

    def test_software_development_adds_marketing_or_entrepreneurship(self):
        plan = self._plan("Computer Science", ["Software Development"])
        self.assertEqual(plan["validation_errors"], [])
        chosen = self._labelled(plan, "Software Development concentration (counts as a major elective)")
        self.assertEqual(len(chosen), 3)
        self.assertTrue(chosen <= SOFTWARE_DEVELOPMENT)
        extra = self._labelled(plan, "Computer Science major: Software Development concentration") - chosen
        self.assertEqual(len(extra & {"BUS 2060", "ENT 3000"}), 1)

    def test_concentrations_are_optional_and_can_be_combined(self):
        self.assertEqual(self._plan("Computer Science")["validation_errors"], [])
        plan = self._plan("Computer Science", ["Foundations of Computing", "Software Development"])
        self.assertEqual(plan["validation_errors"], [])
        self.assertEqual(len(self._labelled(plan, "Foundations of Computing concentration")), 4)

    def test_unknown_options_are_ignored(self):
        plan = self._plan("Computer Science", ["Quantum Basket Weaving"])
        self.assertEqual(plan["validation_errors"], [])
        self.assertEqual(plan["graduation_checks"]["program_options"], {"Computer Science": []})

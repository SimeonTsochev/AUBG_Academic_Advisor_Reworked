"""Corrections in data/policy_overrides.json, checked against the AY 2025-26 catalog PDF."""
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
from degree_engine import (  # noqa: E402
    _course_prereq_expr,
    _min_credits_for_course,
    build_requirement_slots,
    generate_plan,
)

# "Total: N credit hours" printed under each program in the catalog.
CATALOG_TOTALS = {
    ("major", "Business Administration"): 37,
    ("major", "Computer Science"): 36,
    ("major", "Economics"): 37,
    ("major", "European Studies"): 28,
    ("major", "Film and Creative Media"): 36,
    ("major", "History and Civilizations"): 36,
    ("major", "Information Systems"): 36,
    ("major", "Journalism and Mass Communication"): 37,
    ("major", "Mathematics"): 36,
    ("major", "Modern Languages and Cultures"): 36,
    ("major", "Physics"): 38,
    ("major", "Political Science and International Relations"): 32,
    ("major", "Psychology"): 36,
    ("minor", "Computer Science"): 18,
    ("minor", "Creative Writing"): 20,
    ("minor", "Economics"): 18,
    ("minor", "Entrepreneurship"): 18,
    ("minor", "European Studies"): 18,
    ("minor", "Finance"): 18,
    ("minor", "Fine Arts"): 18,
    ("minor", "History"): 18,
    ("minor", "Information Systems"): 18,
    ("minor", "Integrated Marketing Communications"): 19,
    ("minor", "Journalism and Mass Communication"): 19,
    ("minor", "Literature"): 18,
    ("minor", "Mathematics"): 18,
    ("minor", "Modern Languages and Cultures"): 18,
    ("minor", "Philosophy"): 18,
    ("minor", "Physics"): 20,
    ("minor", "Political Science and International Relations"): 19,
    ("minor", "Psychology"): 18,
    ("minor", "Public Policy"): 18,
    ("minor", "Southeast European Studies"): 18,
    ("minor", "Sustainability Studies"): 18,
}


class CatalogCorrectionTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        cls.catalog = getCatalogCache().default_catalog

    def _plan(self, kind: str, name: str):
        with patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2027)):
            return generate_plan(
                catalog=self.catalog,
                majors=[name] if kind == "major" else ["Psychology"],
                minors=[name] if kind == "minor" else [],
                completed_courses=set(),
                start_term_season="Fall",
                start_term_year=2027,
            )

    def _slots(self, kind: str, name: str):
        slots = build_requirement_slots(
            self.catalog,
            [name] if kind == "major" else [],
            [name] if kind == "minor" else [],
        )["slots"]
        own = [s for s in slots if s.get("program") == name and s.get("program_type") == kind]
        fixed = {s["course"] for s in own if s["type"] == "fixed"}
        choices = {(tuple(sorted(s["courses"])), s["count"]) for s in own if s["type"] == "choice"}
        return fixed, choices

    def test_required_courses_plus_elective_credits_match_the_catalog_total(self):
        for (kind, name), total in CATALOG_TOTALS.items():
            with self.subTest(program=f"{name} {kind}"):
                plan = self._plan(kind, name)
                planned = sum(
                    course["credits"]
                    for term in plan["semester_plan"]
                    for course in term["courses"]
                    if any(
                        req.get("program") == name and req.get("program_type") == kind
                        for req in course.get("requirements") or []
                    )
                )
                electives = [
                    entry["credits_required"]
                    for entry in plan["elective_progress"]
                    if entry["program"] == name and entry["program_type"] == kind
                ]
                self.assertEqual(planned + sum(e or 0 for e in electives), total)

    def test_southeast_european_studies_minor_is_two_history_courses_plus_twelve_credits(self):
        fixed, choices = self._slots("minor", "Southeast European Studies")
        self.assertEqual(fixed, set())
        self.assertEqual(
            choices,
            {(("HTY 2021", "HTY 2022", "HTY 2023", "HTY 2024", "HTY 2025"), 2)},
        )

    def test_modern_languages_major_requires_mll1075(self):
        fixed, _ = self._slots("major", "Modern Languages and Cultures")
        self.assertEqual(fixed, {"MLL 1075"})

    def test_prerequisites_missed_by_the_pdf_parser(self):
        self.assertEqual(_course_prereq_expr(self.catalog, "COS 4060"), {"and": ["COS 2021"]})
        self.assertEqual(_course_prereq_expr(self.catalog, "PHI 3004"), {"and": ["ENG 1002"]})
        self.assertEqual(
            _course_prereq_expr(self.catalog, "MAT 4051"),
            {"and": [{"or": ["MAT 2001", "ECO 3010"]}]},
        )
        # Standing rules come from the prerequisite text.
        self.assertEqual(_min_credits_for_course(self.catalog, "INF 4040")[0], 90)
        self.assertIn("sophomore standing", _min_credits_for_course(self.catalog, "JMC 3056")[1])

    def test_planned_courses_follow_their_restored_prerequisites(self):
        plan = self._plan("major", "Information Systems")
        term_of = {
            course["code"]: index
            for index, term in enumerate(plan["semester_plan"])
            for course in term["courses"]
        }
        self.assertLess(term_of["INF 3035"], term_of["INF 4040"])

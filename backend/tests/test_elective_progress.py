"""Elective credit progress per program: the numbers behind the "Elective Requirements" panel."""
import os
import sys
import unittest
from typing import Dict, List
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase, load_real_excel_index  # noqa: E402

import degree_engine  # noqa: E402
import excel_course_catalog  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import _is_free_elective, generate_plan  # noqa: E402

MAJORS = ["Business Administration", "Journalism and Mass Communication"]
MINORS = ["Economics"]


def _by_program(result: Dict) -> Dict[str, Dict]:
    return {entry["program"]: entry for entry in result["elective_progress"]}


class ElectiveProgressTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        clock = patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026))
        clock.start()
        cls.addClassCleanup(clock.stop)
        cls.addClassCleanup(
            excel_course_catalog.restore_course_catalog_state,
            excel_course_catalog.snapshot_course_catalog_state(),
        )
        load_real_excel_index()
        cls.catalog = getCatalogCache().default_catalog
        cls.fresh = cls._plan()

    @classmethod
    def _plan(cls, **kwargs) -> Dict:
        return generate_plan(
            cls.catalog, MAJORS, MINORS, set(), start_term_season="Fall", start_term_year=2026, **kwargs
        )

    def _with_electives(self, codes: List[str]) -> Dict:
        """Put `codes` into the plan's FREE ELECTIVE slots, the way the app's "add course" flow does."""
        slots = [
            (term["term"], course)
            for term in self.fresh["semester_plan"]
            for course in term["courses"]
            if _is_free_elective(course["code"])
        ]
        overrides = {"add": [], "remove": []}
        for (term, slot), code in zip(slots, codes):
            overrides["remove"].append({"term": term, "code": slot["code"], "instance_id": slot["instance_id"]})
            overrides["add"].append({"term": term, "code": code, "instance_id": f"added-{code}"})
        return self._plan(overrides=overrides)

    def test_every_selected_program_reports_its_elective_total(self):
        progress = _by_program(self.fresh)
        self.assertEqual(progress["Business Administration"]["credits_required"], 9)
        self.assertEqual(progress["Journalism and Mass Communication"]["credits_required"], 21)
        self.assertEqual(progress["Economics"]["credits_required"], 9)
        for entry in progress.values():
            self.assertEqual(entry["remaining"], entry["credits_required"] - entry["credits_counted"])

    def test_adding_electives_lowers_the_credits_left(self):
        before = _by_program(self.fresh)
        after = _by_program(self._with_electives(["ECO 3011", "BUS 3498"]))
        # "Any other ECO courses" counts ECO 3011 for the minor, although Excel tags it only as a major elective.
        self.assertEqual(after["Economics"]["remaining"], before["Economics"]["remaining"] - 3)
        # BUS 3498 has no Excel elective tag, but BA electives are "BUS/ENT 3000-4000 level courses".
        self.assertEqual(
            after["Business Administration"]["remaining"], before["Business Administration"]["remaining"] - 3
        )

    def test_a_programs_own_required_courses_are_not_its_electives(self):
        progress = _by_program(self.fresh)
        ba_courses = {c["code"] for c in progress["Business Administration"]["courses"]}
        jmc_courses = {c["code"] for c in progress["Journalism and Mass Communication"]["courses"]}
        econ_courses = {c["code"] for c in progress["Economics"]["courses"]}
        self.assertNotIn("BUS 2060", ba_courses)  # BA required
        self.assertNotIn("JMC 2020", jmc_courses)  # JMC required
        self.assertFalse(econ_courses & {"ECO 1001", "ECO 1002", "ECO 3001"})
        # Required by the other major still counts (students may double count across programs).
        self.assertIn("BUS 2060", jmc_courses)

    def test_non_bus_electives_are_capped_at_three_credits_for_business(self):
        result = self._with_electives(["EUR 3003", "SUS 3001"])
        ba = _by_program(result)["Business Administration"]
        non_bus = {"EUR 3003", "EUR 3020", "JMC 2020", "JMC 3070", "JMC 3089", "SUS 3001", "SUS 4500"}
        counted_non_bus = [c for c in ba["courses"] if c["code"] in non_bus]
        self.assertGreaterEqual(len(counted_non_bus), 2)
        bus_credits = sum(c["credits"] for c in ba["courses"] if c["code"] not in non_bus)
        self.assertEqual(ba["credits_counted"], bus_credits + 3)

    def test_completed_electives_are_marked_completed(self):
        result = generate_plan(
            self.catalog, MAJORS, MINORS, {"ECO 3011"}, start_term_season="Fall", start_term_year=2026
        )
        econ = _by_program(result)["Economics"]
        self.assertIn({"code": "ECO 3011", "credits": 3, "completed": True}, econ["courses"])


if __name__ == "__main__":
    unittest.main()

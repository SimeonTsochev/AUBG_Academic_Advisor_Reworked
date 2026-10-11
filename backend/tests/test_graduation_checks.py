"""Graduation rules from the AY 2026-27 catalog that sit outside the requirement slots."""
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
from degree_engine import _course_is_wic, build_requirement_slots, generate_plan  # noqa: E402
from graduation_checks import double_counting_check, residency_check, retake_check, wic_check  # noqa: E402


class GraduationCheckTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = getCatalogCache().default_catalog

    def _plan(self, majors, minors=(), **kwargs):
        with patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026)):
            return generate_plan(
                catalog=self.catalog,
                majors=list(majors),
                minors=list(minors),
                completed_courses=kwargs.pop("completed_courses", set()),
                start_term_season="Fall",
                start_term_year=2026,
                **kwargs,
            )

    def test_two_single_diploma_majors_cannot_graduate(self):
        plan = self._plan(["Psychology", "Journalism and Mass Communication"])
        self.assertFalse(plan["graduation_checks"]["dual_diploma"]["ok"])
        self.assertTrue(any("at least one dual-diploma major" in e for e in plan["validation_errors"]))

    def test_a_dual_diploma_major_satisfies_the_rule(self):
        plan = self._plan(["Psychology", "Economics"])
        self.assertTrue(plan["graduation_checks"]["dual_diploma"]["ok"])
        self.assertFalse(any("dual-diploma" in e for e in plan["validation_errors"]))

    def test_wics_exclude_the_foundation_writing_courses(self):
        errors, details = wic_check(self.catalog, {"ENG 1001", "ENG 1002", "BUS 3000"})
        self.assertEqual(details["courses"], ["BUS 3000"])
        self.assertEqual(len(errors), 1)
        errors, details = wic_check(self.catalog, {"BUS 3000", "ECO 3010", "HTY 2091"})
        self.assertEqual((errors, details["counted"]), ([], 3))

    def test_removing_the_planned_wics_is_reported(self):
        baseline = self._plan(["Economics"])
        wics = [
            {"term": term["term"], "code": course["code"], "instance_id": course["instance_id"]}
            for term in baseline["semester_plan"]
            for course in term["courses"]
            if _course_is_wic(self.catalog, course["code"]) and course["code"] not in ("ENG 1001", "ENG 1002")
        ]
        self.assertGreaterEqual(len(wics), 3)
        plan = self._plan(["Economics"], overrides={"remove": wics})
        self.assertEqual(plan["graduation_checks"]["wic"]["counted"], 0)
        self.assertTrue(any("writing-intensive" in e for e in plan["validation_errors"]))

    def test_residency_needs_sixty_aubg_credits(self):
        self.assertEqual(len(residency_check(self.catalog, 59)[0]), 1)
        self.assertEqual(residency_check(self.catalog, 60)[0], [])

    def test_transfer_credits_do_not_count_as_residence(self):
        transfer = [
            {"code": "OTH 0001", "instance_id": f"gened-{i}", "term": "Spring 2026", "credits": 6,
             "credit_type": "GENED", "gened_category": category}
            for i, category in enumerate(self.catalog["gen_ed"]["categories"])
        ] + [{"code": "OTH 0001", "instance_id": "major", "term": "Spring 2026", "credits": 18,
              "credit_type": "MAJOR_ELECTIVE", "program": "Economics"}]
        plan = self._plan(["Economics"], manual_credits=transfer)
        transferred = sum(entry["credits"] for entry in transfer)
        self.assertEqual(
            plan["graduation_checks"]["residency"]["aubg_credits"],
            plan["summary"]["projected_credits"] - transferred,
        )
        # Transferred courses never count as WICs (catalog p.80), so the GenEd WICs are gone too.
        self.assertTrue(any("writing-intensive" in e for e in plan["validation_errors"]))

    def test_more_than_three_retakes(self):
        self.assertEqual(retake_check({"A", "B", "C"})[0], [])
        self.assertEqual(len(retake_check({"A", "B", "C", "D"})[0]), 1)

    def test_a_major_and_a_minor_share_at_most_two_courses(self):
        # The Computer Science major and minor both require COS 1020, COS 1050 and COS 2021.
        plan = self._plan(["Computer Science"], ["Computer Science"])
        shared = [e for e in plan["validation_errors"] if "can count toward both" in e]
        self.assertEqual(len(shared), 1)
        self.assertIn("at most 2", shared[0])

    def test_two_majors_may_share_three_courses(self):
        slots = build_requirement_slots(self.catalog, ["Computer Science", "Information Systems"], [])
        courses = {"COS 1020", "COS 1050", "COS 2021", "INF 1030", "INF 2080"}
        errors, details = double_counting_check(self.catalog, slots, courses)
        for entry in details:
            self.assertEqual(entry["limit"], 3)
        self.assertEqual(errors, [e for e in errors if "at most 3" in e])

import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from degree_engine import compute_minor_proximity_smart_details, compute_minor_suggestions  # noqa: E402
from main import _load_default_catalog  # noqa: E402


class StructuredMinorProximityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = _load_default_catalog()
        cls.creative_minor = next(
            (
                key
                for key in cls.catalog.get("minors", {}).keys()
                if isinstance(key, str) and "creative writing" in key.lower()
            ),
            None,
        )
        cls.fine_arts_minor = next(
            (
                key
                for key in cls.catalog.get("minors", {}).keys()
                if isinstance(key, str) and "fine arts" in key.lower()
            ),
            None,
        )
        if not cls.creative_minor or not cls.fine_arts_minor:
            raise unittest.SkipTest("Structured minors were not found in default catalog.")

    def _remaining_count(self, minor_key: str, taken: set[str]) -> int:
        count, _items, _credits = compute_minor_proximity_smart_details(
            catalog=self.catalog,
            minor_name=minor_key,
            completed_and_planned_courses=set(taken),
        )
        return int(count)

    def test_unrelated_bus_jmc_progress_does_not_complete_structured_minors(self):
        taken = {"BUS 1001", "BUS 2001", "BUS 3020", "JMC 1041", "JMC 2000"}
        cw_remaining = self._remaining_count(self.creative_minor, taken)
        fa_remaining = self._remaining_count(self.fine_arts_minor, taken)

        self.assertGreater(cw_remaining, 0)
        self.assertGreater(fa_remaining, 0)

    def test_unrelated_courses_and_free_placeholders_do_not_reduce_remaining(self):
        base_taken = {"BUS 1001", "BUS 2001", "JMC 1041"}
        noisy_taken = set(base_taken) | {"FREE ELECTIVE 1", "FREE ELECTIVE 2", "ECO 1001", "BUS 3020"}

        cw_base = self._remaining_count(self.creative_minor, base_taken)
        cw_noisy = self._remaining_count(self.creative_minor, noisy_taken)
        fa_base = self._remaining_count(self.fine_arts_minor, base_taken)
        fa_noisy = self._remaining_count(self.fine_arts_minor, noisy_taken)

        self.assertEqual(cw_base, cw_noisy)
        self.assertEqual(fa_base, fa_noisy)

    def test_adding_required_structured_courses_reduces_remaining(self):
        base_taken = {"BUS 1001", "BUS 2001", "JMC 1041"}

        cw_base = self._remaining_count(self.creative_minor, base_taken)
        cw_with_required = self._remaining_count(self.creative_minor, set(base_taken) | {"ENG 2005"})
        self.assertLess(cw_with_required, cw_base)

        fa_base = self._remaining_count(self.fine_arts_minor, base_taken)
        fa_with_required_groups = self._remaining_count(
            self.fine_arts_minor,
            set(base_taken) | {"THR 2011", "FAR 3007"},
        )
        self.assertLess(fa_with_required_groups, fa_base)

    def test_suggestions_only_include_minors_that_are_three_or_less_away(self):
        semester_plan = [
            {
                "term": "Fall 2026",
                "courses": [
                    {"code": "FREE ELECTIVE 1"},
                    {"code": "FREE ELECTIVE 2"},
                    {"code": "BUS 1001"},
                    {"code": "JMC 1041"},
                ],
                "credits": 14,
            }
        ]

        suggestions = compute_minor_suggestions(
            catalog=self.catalog,
            majors=["Business Administration", "Journalism and Mass Communication"],
            minors=[],
            completed_courses=set(),
            in_progress_courses=set(),
            semester_plan=semester_plan,
            top_k=50,
        )
        by_minor = {entry.get("minor"): entry for entry in suggestions if isinstance(entry, dict)}

        self.assertNotIn(self.creative_minor, by_minor)
        self.assertNotIn(self.fine_arts_minor, by_minor)
        for entry in suggestions:
            self.assertLessEqual(int(entry.get("remaining_count") or 0), 3)
            self.assertGreaterEqual(int(entry.get("remaining_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()

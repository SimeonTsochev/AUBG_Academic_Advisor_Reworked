import os
import sys
import unittest

from fastapi.testclient import TestClient

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

import main  # noqa: E402


class PlanApiTests(IsolatedTestCase):
    excel_index = "real"

    def setUp(self):
        super().setUp()
        self.client = TestClient(main.app)
        self.catalog_id = self.client.get("/catalog/load-default").json()["catalog_id"]

    def _generate(self, **fields):
        body = {
            "catalog_id": self.catalog_id,
            "majors": ["Computer Science"],
            "minors": [],
            "completed_courses": [],
            "start_term_season": "Spring",
            "start_term_year": 2027,
        }
        body.update(fields)
        return self.client.post("/plan/generate", json=body)

    def test_generates_a_valid_plan_that_reaches_the_degree_total(self):
        response = self._generate()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["is_valid"], payload["validation_errors"])
        self.assertEqual(payload["summary"]["degree_total_credits"], 120)
        self.assertGreaterEqual(payload["summary"]["projected_credits"], 120)

    def test_rejects_out_of_range_inputs(self):
        self.assertEqual(self._generate(start_term_season="Summer").status_code, 422)

    def test_plans_follow_the_catalog_course_load_whatever_the_client_asks(self):
        # Older clients still send a max load; the catalog's 17-credit standard maximum applies (p.65).
        for asked in (25, 20, 10):
            response = self._generate(max_credits_per_semester=asked)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(all(term["credits"] <= 17 for term in response.json()["semester_plan"]))

    def test_identical_requests_are_served_from_the_cache(self):
        first = self._generate()
        cache_size = len(main.PLAN_CACHE)
        second = self._generate()
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(main.PLAN_CACHE), cache_size)


if __name__ == "__main__":
    unittest.main()

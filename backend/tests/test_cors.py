import os
import sys
import unittest

from fastapi.testclient import TestClient

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app  # noqa: E402


class CorsTests(unittest.TestCase):
    def test_cors_headers_present(self):
        client = TestClient(app)
        origin = "http://localhost:3000"
        response = client.post(
            "/plan/generate",
            headers={"Origin": origin},
            json={},
        )
        self.assertIn("access-control-allow-origin", response.headers)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)


if __name__ == "__main__":
    unittest.main()

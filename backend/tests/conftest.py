import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import excel_course_catalog  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_excel_course_index():
    # Safety net for tests that don't use tests/_isolation.IsolatedTestCase.
    state = excel_course_catalog.snapshot_course_catalog_state()
    yield
    excel_course_catalog.restore_course_catalog_state(state)

import copy
import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import excel_course_catalog  # noqa: E402

_REAL_EXCEL_STATE = None


def load_real_excel_index() -> None:
    """Point the module-global Excel index at the shipped catalog, as the API does at startup."""
    global _REAL_EXCEL_STATE
    if _REAL_EXCEL_STATE is None:
        from catalog_cache import getCatalogCache

        cache = getCatalogCache()
        # Deep copy: loading normalizes the payload in place, and the cache must stay untouched.
        excel_course_catalog.load_course_catalog_from_data(
            copy.deepcopy(cache.excel_catalog),
            source_label="excel_catalog.json",
        )
        _REAL_EXCEL_STATE = excel_course_catalog.snapshot_course_catalog_state()
    excel_course_catalog.restore_course_catalog_state(_REAL_EXCEL_STATE)


class IsolatedTestCase(unittest.TestCase):
    """Runs every test against a known module-global Excel course index and restores it afterwards.

    excel_index = "empty": synthetic catalogs only (no leaked real or temp-workbook courses).
    excel_index = "real":  tests that use the shipped catalog or the API endpoints.
    """

    excel_index = "empty"

    def setUp(self) -> None:
        super().setUp()
        self.addCleanup(
            excel_course_catalog.restore_course_catalog_state,
            excel_course_catalog.snapshot_course_catalog_state(),
        )
        if self.excel_index == "real":
            load_real_excel_index()
        else:
            excel_course_catalog.reset_course_catalog()

    def use_real_excel_index(self) -> None:
        load_real_excel_index()

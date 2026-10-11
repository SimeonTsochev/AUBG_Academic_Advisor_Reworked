"""Write frontend/seo/programs.json, the data behind the static program requirement pages.

Run it after the catalog artifacts, policy overrides or the engine's requirement rules change:
    python scripts/build_program_pages_artifact.py
`tests/test_program_pages.py` fails when the committed file is out of date.
"""
from __future__ import annotations

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, BACKEND_DIR.as_posix())

from catalog_artifacts import write_json_artifact  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from program_pages import PROGRAM_PAGES_ARTIFACT_PATH, build_program_pages_payload  # noqa: E402


def main() -> None:
    payload = build_program_pages_payload(getCatalogCache().default_catalog)
    PROGRAM_PAGES_ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json_artifact(PROGRAM_PAGES_ARTIFACT_PATH, payload)
    print(f"Built {PROGRAM_PAGES_ARTIFACT_PATH.name}: {len(payload['programs'])} program pages.")


if __name__ == "__main__":
    main()

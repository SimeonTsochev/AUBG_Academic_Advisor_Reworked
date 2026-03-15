from __future__ import annotations

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from catalog_artifacts import (  # noqa: E402
    DEFAULT_PDF_SOURCE_PATH,
    PDF_ARTIFACT_PATH,
    build_pdf_requirements_artifact,
    write_json_artifact,
)


def main() -> None:
    payload = build_pdf_requirements_artifact(DEFAULT_PDF_SOURCE_PATH)
    write_json_artifact(PDF_ARTIFACT_PATH, payload)
    print(
        f"Wrote {PDF_ARTIFACT_PATH} from {DEFAULT_PDF_SOURCE_PATH.name} "
        f"({payload.get('course_count', 0)} PDF course entries)."
    )


if __name__ == "__main__":
    main()

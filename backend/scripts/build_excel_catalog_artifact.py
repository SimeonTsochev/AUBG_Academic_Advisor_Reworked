from __future__ import annotations

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from catalog_artifacts import (  # noqa: E402
    EXCEL_ARTIFACT_PATH,
    build_excel_catalog_artifact,
    resolve_default_excel_source,
    write_json_artifact,
)


def main() -> None:
    source = resolve_default_excel_source()
    payload = build_excel_catalog_artifact(source)
    write_json_artifact(EXCEL_ARTIFACT_PATH, payload)
    print(
        f"Wrote {EXCEL_ARTIFACT_PATH} from {source.name} "
        f"({payload.get('course_count', 0)} courses)."
    )


if __name__ == "__main__":
    main()

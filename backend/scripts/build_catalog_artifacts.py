from __future__ import annotations

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from catalog_artifacts import (  # noqa: E402
    EXCEL_ARTIFACT_PATH,
    PDF_ARTIFACT_PATH,
    build_excel_catalog_artifact,
    build_pdf_requirements_artifact,
    ensure_policy_overrides_file,
    resolve_default_excel_source,
    write_json_artifact,
)


def main() -> None:
    excel_source = resolve_default_excel_source()
    excel_payload = build_excel_catalog_artifact(excel_source)
    write_json_artifact(EXCEL_ARTIFACT_PATH, excel_payload)

    pdf_payload = build_pdf_requirements_artifact()
    write_json_artifact(PDF_ARTIFACT_PATH, pdf_payload)

    ensure_policy_overrides_file()

    print(
        "Built compact backend artifacts: "
        f"{EXCEL_ARTIFACT_PATH.name} ({excel_payload.get('course_count', 0)} courses), "
        f"{PDF_ARTIFACT_PATH.name} ({pdf_payload.get('course_count', 0)} PDF course entries)."
    )


if __name__ == "__main__":
    main()

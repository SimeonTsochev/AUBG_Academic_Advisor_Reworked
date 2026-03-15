from __future__ import annotations

from pathlib import Path
import argparse
import sys
import time

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from catalog_artifacts import (  # noqa: E402
    EXCEL_ARTIFACT_PATH,
    MISMATCH_ARTIFACT_PATH,
    PDF_ARTIFACT_PATH,
    read_json_artifact,
    write_json_artifact,
)
from excel_catalog import compute_catalog_integrity, get_excel_course_codes  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline/debug mismatch comparison for Excel vs PDF catalog artifacts.",
    )
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Print the mismatch snapshot without writing catalog_mismatch.json.",
    )
    args = parser.parse_args()

    excel_catalog = read_json_artifact(EXCEL_ARTIFACT_PATH)
    pdf_requirements = read_json_artifact(PDF_ARTIFACT_PATH)

    pdf_codes = {
        code
        for code in (pdf_requirements.get("courses") or {}).keys()
        if isinstance(code, str)
    }
    excel_codes = get_excel_course_codes(excel_catalog)
    mismatch = compute_catalog_integrity(pdf_codes=pdf_codes, excel_codes=excel_codes)
    mismatch["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    print(
        "Catalog mismatch snapshot: "
        f"excel_only={len(mismatch.get('excel_only', []))}, "
        f"pdf_only={len(mismatch.get('pdf_only', []))}"
    )

    if args.stdout_only:
        return

    write_json_artifact(MISMATCH_ARTIFACT_PATH, mismatch)
    print(f"Wrote {MISMATCH_ARTIFACT_PATH}.")


if __name__ == "__main__":
    main()

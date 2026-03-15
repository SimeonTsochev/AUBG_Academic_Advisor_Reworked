from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional
import logging
import time
import uuid

from catalog_artifacts import (
    EXCEL_ARTIFACT_PATH,
    MISMATCH_ARTIFACT_PATH,
    PDF_ARTIFACT_PATH,
    POLICY_OVERRIDES_PATH,
    apply_policy_overrides,
    ensure_policy_overrides_file,
    normalize_mismatch_snapshot,
    normalize_policy_overrides,
    read_json_artifact,
)
from excel_course_catalog import load_course_catalog_from_data


@dataclass(frozen=True)
class CatalogCache:
    excel_catalog: Dict[str, Any]
    pdf_requirements: Dict[str, Any]
    policy_overrides: Dict[str, Any]
    mismatch_snapshot: Dict[str, Any]
    default_catalog: Dict[str, Any]
    default_catalog_id: str
    catalog_year: str
    preload_ms: float


_CACHE_LOCK = Lock()
_CATALOG_CACHE: Optional[CatalogCache] = None


def _artifact_size_kb(path: Path) -> float:
    return round(path.stat().st_size / 1024.0, 1)


def _load_required_artifact(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(
            f"{label} artifact is missing at {path}. "
            f"Run the backend preprocessing scripts before starting the API."
        )
    logging.info("Catalog preload: reading %s (%s KB).", path.name, _artifact_size_kb(path))
    return read_json_artifact(path)


def _load_optional_mismatch_snapshot() -> Dict[str, Any]:
    if not MISMATCH_ARTIFACT_PATH.exists():
        logging.info(
            "Catalog preload: mismatch snapshot not found at %s; runtime comparison stays disabled.",
            MISMATCH_ARTIFACT_PATH,
        )
        return normalize_mismatch_snapshot(None)

    logging.info(
        "Catalog preload: reading %s (%s KB).",
        MISMATCH_ARTIFACT_PATH.name,
        _artifact_size_kb(MISMATCH_ARTIFACT_PATH),
    )
    return normalize_mismatch_snapshot(read_json_artifact(MISMATCH_ARTIFACT_PATH))


def getCatalogCache() -> CatalogCache:
    global _CATALOG_CACHE

    with _CACHE_LOCK:
        if _CATALOG_CACHE is not None:
            logging.info(
                "Catalog cache hit: reusing preloaded artifacts for catalog_year=%s.",
                _CATALOG_CACHE.catalog_year,
            )
            return _CATALOG_CACHE

        logging.info(
            "Catalog cache miss: loading compact JSON artifacts only; raw Excel/PDF parsing is disabled at runtime."
        )
        start = time.perf_counter()

        excel_catalog = _load_required_artifact(EXCEL_ARTIFACT_PATH, "Excel catalog")
        load_course_catalog_from_data(excel_catalog, source_label=EXCEL_ARTIFACT_PATH.name)
        logging.info(
            "Catalog preload: in-memory Excel search index primed from %s (%s courses).",
            EXCEL_ARTIFACT_PATH.name,
            len(excel_catalog.get("courses") or []),
        )

        pdf_requirements = _load_required_artifact(PDF_ARTIFACT_PATH, "PDF requirements")

        policy_payload = ensure_policy_overrides_file(POLICY_OVERRIDES_PATH)
        policy_overrides = normalize_policy_overrides(policy_payload)
        logging.info("Catalog preload: policy overrides active from %s.", POLICY_OVERRIDES_PATH.name)

        mismatch_snapshot = _load_optional_mismatch_snapshot()

        default_catalog = apply_policy_overrides(pdf_requirements, policy_overrides)
        default_catalog["excel_catalog"] = excel_catalog
        default_catalog["excel_course_catalog"] = excel_catalog
        default_catalog["policy_overrides"] = policy_overrides
        default_catalog["excel_integrity"] = mismatch_snapshot

        catalog_year = str(default_catalog.get("catalog_year") or pdf_requirements.get("catalog_year") or "")
        default_catalog["catalog_year"] = catalog_year
        default_catalog_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"aubg-advisor:{catalog_year}:{EXCEL_ARTIFACT_PATH.name}:{PDF_ARTIFACT_PATH.name}",
            )
        )

        preload_ms = (time.perf_counter() - start) * 1000.0
        logging.info(
            "Catalog preload complete in %.2f ms (excel_courses=%s, pdf_courses=%s, majors=%s, minors=%s).",
            preload_ms,
            len(excel_catalog.get("courses") or []),
            len((default_catalog.get("courses") or {}).keys()),
            len((default_catalog.get("majors") or {}).keys()),
            len((default_catalog.get("minors") or {}).keys()),
        )

        _CATALOG_CACHE = CatalogCache(
            excel_catalog=excel_catalog,
            pdf_requirements=pdf_requirements,
            policy_overrides=policy_overrides,
            mismatch_snapshot=mismatch_snapshot,
            default_catalog=default_catalog,
            default_catalog_id=default_catalog_id,
            catalog_year=catalog_year,
            preload_ms=preload_ms,
        )
        return _CATALOG_CACHE

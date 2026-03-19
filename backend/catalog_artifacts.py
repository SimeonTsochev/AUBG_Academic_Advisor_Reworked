from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
import json
import logging
import time

from catalog_parser import parse_catalog
from excel_course_catalog import build_course_catalog_data

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"

DEFAULT_PDF_SOURCE_PATH = BACKEND_DIR / "AY-2025-26-3rd-ed.pdf"
DEFAULT_EXCEL_SOURCE_BASENAME = "course_catalog 031926"
DEFAULT_EXCEL_SOURCE_PATHS = [
    BACKEND_DIR / f"{DEFAULT_EXCEL_SOURCE_BASENAME}.xlsx",
    BACKEND_DIR / f"{DEFAULT_EXCEL_SOURCE_BASENAME}.xls",
]

EXCEL_ARTIFACT_PATH = DATA_DIR / "excel_catalog.json"
PDF_ARTIFACT_PATH = DATA_DIR / "pdf_requirements.json"
POLICY_OVERRIDES_PATH = DATA_DIR / "policy_overrides.json"
MISMATCH_ARTIFACT_PATH = DATA_DIR / "catalog_mismatch.json"

DEFAULT_POLICY_OVERRIDES: Dict[str, Any] = {
    "catalog_year": None,
    "courses": {},
    "course_meta": {},
    "majors": {},
    "minors": {},
    "foundation_courses_add": [],
    "foundation_courses_remove": [],
    "gen_ed": {
        "rules": {},
        "categories": {},
        "categories_add": {},
        "categories_remove": {},
    },
}

DEFAULT_MISMATCH_SNAPSHOT: Dict[str, Any] = {
    "excel_only": [],
    "pdf_only": [],
}


def resolve_default_excel_source() -> Path:
    for candidate in DEFAULT_EXCEL_SOURCE_PATHS:
        if candidate.exists():
            return candidate
    checked = ", ".join(str(path) for path in DEFAULT_EXCEL_SOURCE_PATHS)
    raise FileNotFoundError(f"Excel course catalog was not found. Checked: {checked}")


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def read_json_artifact(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Artifact {path} must contain a JSON object.")
    return payload


def write_json_artifact(path: Path, payload: Dict[str, Any]) -> None:
    _write_json(path, payload)


def build_excel_catalog_artifact(excel_path: Path | None = None) -> Dict[str, Any]:
    source = excel_path or resolve_default_excel_source()
    payload = build_course_catalog_data(source)
    payload.pop("source_path", None)
    payload.pop("source_mtime", None)
    payload["artifact_type"] = "excel_catalog"
    payload["generated_at"] = _timestamp()
    payload["source_filename"] = source.name
    payload["course_count"] = len(payload.get("courses") or [])
    return payload


def build_pdf_requirements_artifact(pdf_path: Path | None = None) -> Dict[str, Any]:
    source = pdf_path or DEFAULT_PDF_SOURCE_PATH
    if not source.exists():
        raise FileNotFoundError(f"Catalog PDF was not found: {source}")

    with source.open("rb") as handle:
        payload = parse_catalog(handle)

    payload["artifact_type"] = "pdf_requirements"
    payload["generated_at"] = _timestamp()
    payload["source_filename"] = source.name
    payload["course_count"] = len(payload.get("courses") or {})
    payload["major_count"] = len(payload.get("majors") or {})
    payload["minor_count"] = len(payload.get("minors") or {})
    return payload


def ensure_policy_overrides_file(path: Path = POLICY_OVERRIDES_PATH) -> Dict[str, Any]:
    if path.exists():
        payload = read_json_artifact(path)
        return normalize_policy_overrides(payload)

    payload = deepcopy(DEFAULT_POLICY_OVERRIDES)
    write_json_artifact(path, payload)
    logging.info("Created default policy overrides file at %s.", path)
    return deepcopy(payload)


def normalize_policy_overrides(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    normalized = deepcopy(DEFAULT_POLICY_OVERRIDES)
    if not isinstance(payload, dict):
        return normalized

    if payload.get("catalog_year") is not None:
        normalized["catalog_year"] = payload.get("catalog_year")

    for key in ("courses", "course_meta", "majors", "minors"):
        value = payload.get(key)
        if isinstance(value, dict):
            normalized[key] = deepcopy(value)

    for key in ("foundation_courses_add", "foundation_courses_remove"):
        value = payload.get(key)
        if isinstance(value, list):
            normalized[key] = [item for item in value if isinstance(item, str)]

    gen_ed = payload.get("gen_ed")
    if isinstance(gen_ed, dict):
        for key in ("rules", "categories", "categories_add", "categories_remove"):
            value = gen_ed.get(key)
            if isinstance(value, dict):
                normalized["gen_ed"][key] = deepcopy(value)

    return normalized


def normalize_mismatch_snapshot(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    snapshot = deepcopy(DEFAULT_MISMATCH_SNAPSHOT)
    if not isinstance(payload, dict):
        return snapshot
    for key in ("excel_only", "pdf_only"):
        value = payload.get(key)
        if isinstance(value, list):
            snapshot[key] = [item for item in value if isinstance(item, str)]
    if payload.get("generated_at") is not None:
        snapshot["generated_at"] = payload.get("generated_at")
    return snapshot


def _unique_ordered(values: List[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value.strip()))


def _apply_program_policy(programs: Dict[str, Any], overrides: Dict[str, Any]) -> None:
    for name, override in overrides.items():
        if not isinstance(name, str) or not isinstance(override, dict):
            continue

        target = programs.setdefault(name, {
            "required_courses": [],
            "elective_requirements": [],
        })
        if not isinstance(target, dict):
            target = {
                "required_courses": [],
                "elective_requirements": [],
            }
            programs[name] = target

        if isinstance(override.get("required_courses"), list):
            target["required_courses"] = _unique_ordered(
                [course for course in override.get("required_courses", []) if isinstance(course, str)]
            )
        else:
            existing_required = [
                course
                for course in (target.get("required_courses") or [])
                if isinstance(course, str)
            ]
            existing_required.extend(
                course
                for course in (override.get("required_courses_add") or [])
                if isinstance(course, str)
            )
            remove_required = {
                course
                for course in (override.get("required_courses_remove") or [])
                if isinstance(course, str)
            }
            target["required_courses"] = [
                course for course in _unique_ordered(existing_required)
                if course not in remove_required
            ]

        if isinstance(override.get("elective_requirements"), list):
            target["elective_requirements"] = [
                block for block in override.get("elective_requirements", [])
                if isinstance(block, dict)
            ]
        else:
            existing_blocks = [
                block
                for block in (target.get("elective_requirements") or [])
                if isinstance(block, dict)
            ]
            existing_blocks.extend(
                block
                for block in (override.get("elective_requirements_add") or [])
                if isinstance(block, dict)
            )
            target["elective_requirements"] = existing_blocks


def apply_policy_overrides(
    pdf_requirements: Dict[str, Any],
    policy_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    runtime_catalog = deepcopy(pdf_requirements)
    policy = normalize_policy_overrides(policy_overrides)

    if policy.get("catalog_year"):
        runtime_catalog["catalog_year"] = policy.get("catalog_year")

    for key in ("courses", "course_meta"):
        target = runtime_catalog.setdefault(key, {})
        overrides = policy.get(key) or {}
        if not isinstance(target, dict) or not isinstance(overrides, dict):
            continue
        for code, patch in overrides.items():
            if not isinstance(code, str) or not isinstance(patch, dict):
                continue
            current = target.get(code)
            if not isinstance(current, dict):
                current = {}
            merged = dict(current)
            merged.update(patch)
            target[code] = merged

    majors = runtime_catalog.setdefault("majors", {})
    if isinstance(majors, dict):
        _apply_program_policy(majors, policy.get("majors") or {})

    minors = runtime_catalog.setdefault("minors", {})
    if isinstance(minors, dict):
        _apply_program_policy(minors, policy.get("minors") or {})

    foundation = [
        course
        for course in (runtime_catalog.get("foundation_courses") or [])
        if isinstance(course, str)
    ]
    foundation.extend(
        course
        for course in (policy.get("foundation_courses_add") or [])
        if isinstance(course, str)
    )
    foundation_remove = {
        course
        for course in (policy.get("foundation_courses_remove") or [])
        if isinstance(course, str)
    }
    runtime_catalog["foundation_courses"] = [
        course for course in _unique_ordered(foundation)
        if course not in foundation_remove
    ]

    gen_ed = runtime_catalog.setdefault("gen_ed", {})
    if not isinstance(gen_ed, dict):
        gen_ed = {}
        runtime_catalog["gen_ed"] = gen_ed

    gen_ed_rules = gen_ed.setdefault("rules", {})
    if not isinstance(gen_ed_rules, dict):
        gen_ed_rules = {}
        gen_ed["rules"] = gen_ed_rules
    for category, count in (policy.get("gen_ed", {}).get("rules") or {}).items():
        if isinstance(category, str):
            gen_ed_rules[category] = count

    gen_ed_categories = gen_ed.setdefault("categories", {})
    if not isinstance(gen_ed_categories, dict):
        gen_ed_categories = {}
        gen_ed["categories"] = gen_ed_categories

    for category, codes in (policy.get("gen_ed", {}).get("categories") or {}).items():
        if isinstance(category, str) and isinstance(codes, list):
            gen_ed_categories[category] = _unique_ordered([code for code in codes if isinstance(code, str)])

    for category, codes in (policy.get("gen_ed", {}).get("categories_add") or {}).items():
        if not isinstance(category, str) or not isinstance(codes, list):
            continue
        existing = [
            code
            for code in (gen_ed_categories.get(category) or [])
            if isinstance(code, str)
        ]
        existing.extend(code for code in codes if isinstance(code, str))
        gen_ed_categories[category] = _unique_ordered(existing)

    for category, codes in (policy.get("gen_ed", {}).get("categories_remove") or {}).items():
        if not isinstance(category, str) or not isinstance(codes, list):
            continue
        remove_set = {code for code in codes if isinstance(code, str)}
        existing = [
            code
            for code in (gen_ed_categories.get(category) or [])
            if isinstance(code, str)
        ]
        gen_ed_categories[category] = [code for code in existing if code not in remove_set]

    return runtime_catalog

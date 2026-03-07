from __future__ import annotations

from fastapi import FastAPI, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from typing import Any, Dict, Optional
import uuid
import json
import inspect
from pathlib import Path
import logging

from catalog_parser import parse_catalog
from degree_engine import generate_plan
from pdf_export import plan_to_pdf_bytes
from models import (
    UploadCatalogResponse,
    GeneratePlanRequest,
    GeneratePlanResponse,
    CreateSnapshotRequest,
    CreateSnapshotResponse,
    GetSnapshotResponse,
)
from excel_catalog import (
    load_excel_catalog,
    compute_catalog_integrity,
    get_excel_course_codes,
)
from excel_course_catalog import (
    load_course_catalog as load_excel_course_universe,
    get_course as get_excel_course_record,
    search_courses as search_excel_courses,
    list_courses as list_excel_courses,
)
from snapshots_db import SnapshotExpiredError, create_snapshot, get_snapshot, init_db

app = FastAPI(title="AUBG Academic Advisor API", version="0.1.0")

# Dev CORS: allow local frontend dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CATALOGS: Dict[str, Dict] = {}
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "AY-2025-26-3rd-ed.pdf"
DEFAULT_CATALOG: Optional[Dict] = None
DEFAULT_CATALOG_ID: Optional[str] = None
DEFAULT_CATALOG_MTIME: Optional[float] = None
DEFAULT_CATALOG_VERSION: Optional[str] = None
DEFAULT_CATALOG_YEAR = "2025-26"
PARSER_VERSION = "2026-02-17-prereq-expr-v3"
EXCEL_CATALOG_BASENAME = "course_catalog_012526"
EXCEL_CATALOG_PATHS = [
    Path(__file__).resolve().parent / f"{EXCEL_CATALOG_BASENAME}.xlsx",
    Path(__file__).resolve().parent / f"{EXCEL_CATALOG_BASENAME}.xls",
]
EXCEL_COURSE_UNIVERSE_PATH: Optional[Path] = None
FORCE_OPTIMIZE_PLAN = True
FORCE_OPTIMIZATION_PASSES = 25
INTERACTIVE_OPTIMIZATION_PASSES = 8
PLAN_CACHE_MAX_SIZE = 64
PLAN_CACHE: Dict[str, Dict[str, Any]] = {}


def _compact_plan_cache() -> None:
    if len(PLAN_CACHE) <= PLAN_CACHE_MAX_SIZE:
        return
    # Drop oldest entries first (insertion-ordered dict in modern Python).
    while len(PLAN_CACHE) > PLAN_CACHE_MAX_SIZE:
        PLAN_CACHE.pop(next(iter(PLAN_CACHE)))


def _plan_request_key(req: GeneratePlanRequest) -> str:
    payload = req.dict()
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _has_interactive_overrides(req: GeneratePlanRequest) -> bool:
    if req.overrides is None:
        return False
    payload = req.overrides.dict()
    return any(payload.get(key) for key in ("add", "remove", "move", "locks"))


def _optimization_passes_for_request(req: GeneratePlanRequest) -> int:
    if _has_interactive_overrides(req):
        return min(FORCE_OPTIMIZATION_PASSES, INTERACTIVE_OPTIMIZATION_PASSES)
    return FORCE_OPTIMIZATION_PASSES


def _generate_plan_with_compatible_kwargs(catalog: Dict[str, Any], req: GeneratePlanRequest) -> Dict[str, Any]:
    optimization_passes = _optimization_passes_for_request(req)
    kwargs: Dict[str, Any] = {
        "catalog": catalog,
        "majors": req.majors,
        "minors": req.minors,
        "completed_courses": set(req.completed_courses),
        "manual_credits": [entry.dict() for entry in req.manual_credits],
        "retake_courses": set(req.retake_courses or []),
        "max_credits_per_semester": req.max_credits_per_semester,
        "start_term_season": req.start_term_season,
        "start_term_year": req.start_term_year,
        "waived_mat1000": req.waived_mat1000,
        "waived_eng1000": req.waived_eng1000,
        "strict_prereqs": req.strict_prereqs,
        "overrides": req.overrides.dict() if req.overrides is not None else None,
        "in_progress_courses": set(req.in_progress_courses or []),
        "in_progress_terms": req.in_progress_terms or {},
        "current_term_label": req.current_term_label,
    }

    # Compatibility: some degree_engine versions do not support optimization args.
    params = inspect.signature(generate_plan).parameters
    if "optimize" in params:
        kwargs["optimize"] = FORCE_OPTIMIZE_PLAN
    if "optimization_passes" in params:
        kwargs["optimization_passes"] = optimization_passes

    return generate_plan(**kwargs)


def _resolve_excel_catalog_path() -> Optional[Path]:
    for path in EXCEL_CATALOG_PATHS:
        if path.exists():
            return path
    return None


def _ensure_excel_course_universe_loaded() -> Path:
    global EXCEL_COURSE_UNIVERSE_PATH
    excel_path = _resolve_excel_catalog_path()
    if excel_path is None:
        candidates = ", ".join(str(path) for path in EXCEL_CATALOG_PATHS)
        raise RuntimeError(
            f"Excel course catalog was not found. Checked: {candidates}"
        )
    try:
        load_excel_course_universe(excel_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load Excel course catalog from '{excel_path}': {exc}"
        ) from exc
    EXCEL_COURSE_UNIVERSE_PATH = excel_path
    return excel_path


@app.on_event("startup")
def _startup_preload_excel_course_universe() -> None:
    excel_path = _ensure_excel_course_universe_loaded()
    logging.info("Excel course universe preloaded from %s.", excel_path)


@app.on_event("startup")
def _startup_init_snapshot_db() -> None:
    init_db()
    logging.info("Program snapshot database initialized.")

def _load_default_catalog() -> Dict:
    global DEFAULT_CATALOG, DEFAULT_CATALOG_ID, DEFAULT_CATALOG_MTIME, DEFAULT_CATALOG_VERSION
    try:
        excel_path = _ensure_excel_course_universe_loaded()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not DEFAULT_CATALOG_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Default catalog not found: {DEFAULT_CATALOG_PATH}")
    mtime = DEFAULT_CATALOG_PATH.stat().st_mtime
    if (
        DEFAULT_CATALOG is not None
        and DEFAULT_CATALOG_MTIME == mtime
        and DEFAULT_CATALOG_VERSION == PARSER_VERSION
    ):
        return DEFAULT_CATALOG
    try:
        with open(DEFAULT_CATALOG_PATH, "rb") as f:
            catalog = parse_catalog(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Catalog parsing failed: {e}")
    excel_catalog = load_excel_catalog(excel_path)
    catalog["excel_catalog"] = excel_catalog
    pdf_codes = set(catalog.get("courses", {}).keys())
    excel_codes = get_excel_course_codes(excel_catalog)
    if excel_codes:
        integrity = compute_catalog_integrity(pdf_codes, excel_codes)
        catalog["excel_integrity"] = integrity
        if integrity["excel_only"] or integrity["pdf_only"]:
            logging.warning(
                "Excel/PDF catalog mismatch (excel_only=%s, pdf_only=%s)",
                len(integrity["excel_only"]),
                len(integrity["pdf_only"]),
            )
    else:
        catalog["excel_integrity"] = {"excel_only": [], "pdf_only": []}
    catalog["catalog_year"] = DEFAULT_CATALOG_YEAR
    DEFAULT_CATALOG = catalog
    DEFAULT_CATALOG_MTIME = mtime
    DEFAULT_CATALOG_VERSION = PARSER_VERSION
    PLAN_CACHE.clear()
    if DEFAULT_CATALOG_ID is None:
        DEFAULT_CATALOG_ID = str(uuid.uuid4())
    return catalog

def _ensure_catalog(catalog_id: str) -> Dict:
    catalog = CATALOGS.get(catalog_id)
    if catalog is not None:
        return catalog
    # Auto-load built-in catalog and bind it to the requested id.
    catalog = _load_default_catalog()
    CATALOGS[catalog_id] = catalog
    return catalog


def _excel_only_code_set(catalog: Dict[str, Any] | None = None) -> set[str]:
    source = catalog if isinstance(catalog, dict) else _load_default_catalog()
    integrity = source.get("excel_integrity") if isinstance(source, dict) else {}
    excel_only = integrity.get("excel_only") if isinstance(integrity, dict) else []
    if not isinstance(excel_only, list):
        return set()
    return {code for code in excel_only if isinstance(code, str)}


def _with_excel_only_flag(record: Dict[str, Any], excel_only_codes: set[str]) -> Dict[str, Any]:
    payload = dict(record) if isinstance(record, dict) else {}
    code = payload.get("code")
    payload["is_excel_only"] = isinstance(code, str) and code in excel_only_codes
    return payload


def _catalog_courses_for_response(catalog: Dict[str, Any]) -> Dict[str, str]:
    courses: Dict[str, str] = {
        code: data.get("name", code)
        for code, data in catalog.get("courses", {}).items()
        if isinstance(code, str)
    }
    for record in list_excel_courses():
        code = record.get("code")
        if not isinstance(code, str):
            continue
        title = record.get("title")
        courses[code] = title if isinstance(title, str) and title else courses.get(code, code)
    return courses


def _catalog_course_meta_for_response(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    base_meta = catalog.get("course_meta", {}) or {}
    excel_only_codes = _excel_only_code_set(catalog)
    merged: Dict[str, Dict[str, Any]] = {
        code: dict(meta) if isinstance(meta, dict) else {}
        for code, meta in base_meta.items()
        if isinstance(code, str)
    }
    for record in list_excel_courses():
        code = record.get("code")
        if not isinstance(code, str):
            continue
        entry = merged.setdefault(code, {})

        title = record.get("title")
        if isinstance(title, str) and title:
            entry["title"] = title

        credits = record.get("credits")
        if isinstance(credits, (int, float)) and credits > 0:
            entry["credits"] = int(credits)

        gen_ed_tags = record.get("gen_ed_tags")
        if isinstance(gen_ed_tags, list):
            cleaned_tags = [tag for tag in gen_ed_tags if isinstance(tag, str)]
            if cleaned_tags:
                entry["gen_ed_tags"] = cleaned_tags

        wic = record.get("wic")
        if isinstance(wic, bool):
            entry["wic"] = wic

        semester_availability = record.get("semester_availability")
        if isinstance(semester_availability, list):
            cleaned_terms = [term for term in semester_availability if isinstance(term, str)]
            if cleaned_terms:
                entry["semester_availability"] = cleaned_terms
    for code, entry in merged.items():
        entry["is_excel_only"] = code in excel_only_codes
    return merged

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/program-snapshots", response_model=CreateSnapshotResponse)
def program_snapshots_create(req: CreateSnapshotRequest):
    payload_json = json.dumps(req.payload, separators=(",", ":"), ensure_ascii=False)
    if len(payload_json.encode("utf-8")) > 1_000_000:
        raise HTTPException(status_code=413, detail="Snapshot payload is too large.")
    try:
        snapshot = create_snapshot(req.payload, req.catalog_year)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return CreateSnapshotResponse(
        token=str(snapshot["token"]),
        expires_at=int(snapshot["expires_at"]),
    )


@app.get("/program-snapshots/{token}", response_model=GetSnapshotResponse)
def program_snapshots_get(token: str):
    try:
        snapshot = get_snapshot(token)
    except SnapshotExpiredError:
        raise HTTPException(status_code=410, detail="Snapshot has expired.")
    except KeyError:
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    return GetSnapshotResponse(
        token=str(snapshot["token"]),
        expires_at=int(snapshot["expires_at"]),
        catalog_year=str(snapshot["catalog_year"]),
        payload=dict(snapshot["payload"]),
    )


@app.get("/courses/search")
def courses_search(
    q: str = Query(..., min_length=1),
    term: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    try:
        _ensure_excel_course_universe_loaded()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    excel_only_codes = _excel_only_code_set()
    results = search_excel_courses(query=q, term=term, limit=limit)
    return [_with_excel_only_flag(record, excel_only_codes) for record in results]


@app.get("/courses")
def courses_list(term: Optional[str] = None):
    try:
        _ensure_excel_course_universe_loaded()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    excel_only_codes = _excel_only_code_set()
    results = list_excel_courses(term=term)
    return [_with_excel_only_flag(record, excel_only_codes) for record in results]


@app.get("/courses/{code}")
def courses_get(code: str):
    try:
        _ensure_excel_course_universe_loaded()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    course = get_excel_course_record(code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course not found in Excel catalog: {code}")
    excel_only_codes = _excel_only_code_set()
    return _with_excel_only_flag(course, excel_only_codes)


@app.get("/catalog/load-default", response_model=UploadCatalogResponse)
def load_default_catalog():
    catalog = _load_default_catalog()
    catalog_id = DEFAULT_CATALOG_ID or str(uuid.uuid4())
    CATALOGS[catalog_id] = catalog
    excel_only_codes = sorted(_excel_only_code_set(catalog))

    return UploadCatalogResponse(
        catalog_id=catalog_id,
        catalog_year=DEFAULT_CATALOG_YEAR,
        majors=list(catalog.get("majors", {}).keys()),
        minors=list(catalog.get("minors", {}).keys()),
        courses=_catalog_courses_for_response(catalog),
        course_meta=_catalog_course_meta_for_response(catalog),
        gen_ed=catalog.get("gen_ed", {}),
        excel_only_codes=excel_only_codes,
    )


@app.get("/catalog/integrity")
def catalog_integrity(catalog_id: str):
    catalog = _ensure_catalog(catalog_id)
    integrity = catalog.get("excel_integrity")
    if not isinstance(integrity, dict):
        pdf_codes = set(catalog.get("courses", {}).keys())
        excel_catalog = catalog.get("excel_catalog") or {}
        excel_codes = get_excel_course_codes(excel_catalog)
        if excel_codes:
            integrity = compute_catalog_integrity(pdf_codes, excel_codes)
        else:
            integrity = {"excel_only": [], "pdf_only": []}
        catalog["excel_integrity"] = integrity
    return integrity

# Legacy upload endpoint (kept for future multi-university support)
"""
@app.post("/catalog/upload", response_model=UploadCatalogResponse)
async def upload_catalog(file: UploadFile):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    try:
        catalog = parse_catalog(file.file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Catalog parsing failed: {e}")

    catalog_id = str(uuid.uuid4())
    CATALOGS[catalog_id] = catalog

    return UploadCatalogResponse(
        catalog_id=catalog_id,
        catalog_year=catalog.get("catalog_year"),
        majors=list(catalog.get("majors", {}).keys()),
        minors=list(catalog.get("minors", {}).keys()),
        courses=catalog.get("courses", {}),
    )
"""

@app.post("/plan/generate", response_model=GeneratePlanResponse)
async def plan_generate(req: GeneratePlanRequest):
    catalog = _ensure_catalog(req.catalog_id)
    request_key = _plan_request_key(req)
    cached = PLAN_CACHE.get(request_key)
    if cached is not None:
        return GeneratePlanResponse(**cached)
    try:
        plan = _generate_plan_with_compatible_kwargs(catalog, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    response_payload = GeneratePlanResponse(
        catalog_id=req.catalog_id,
        catalog_year=catalog.get("catalog_year"),
        **plan,
    )
    PLAN_CACHE[request_key] = response_payload.dict()
    _compact_plan_cache()
    return response_payload

@app.post("/plan/download.pdf")
async def plan_download_pdf(req: GeneratePlanRequest):
    catalog = _ensure_catalog(req.catalog_id)
    try:
        plan = _generate_plan_with_compatible_kwargs(catalog, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    pdf_bytes = plan_to_pdf_bytes({
        "majors": req.majors,
        "minors": req.minors,
        "manual_credits": [entry.dict() for entry in req.manual_credits],
        **plan,
    })
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=degree-plan.pdf"},
    )

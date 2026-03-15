from __future__ import annotations

from fastapi import FastAPI, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from typing import Any, Dict, Optional
import json
import inspect
import logging
import os

from catalog_cache import getCatalogCache
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
from excel_course_catalog import (
    get_course as get_excel_course_record,
    search_courses as search_excel_courses,
    list_courses as list_excel_courses,
)
from snapshots_db import SnapshotExpiredError, create_snapshot, get_snapshot, init_db, snapshot_storage_enabled

app = FastAPI(title="AUBG Academic Advisor API", version="0.1.0")

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_env_cors_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]
_allow_all_cors = os.getenv("CORS_ALLOW_ALL", "").strip().lower() in {"1", "true", "yes"}

_configured_cors_origins = list(dict.fromkeys([*DEFAULT_CORS_ORIGINS, *_env_cors_origins]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all_cors else _configured_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=not _allow_all_cors,
    allow_methods=["*"],
    allow_headers=["*"],
)

CATALOGS: Dict[str, Dict] = {}
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


def _require_catalog_cache():
    try:
        return getCatalogCache()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.on_event("startup")
def _startup_preload_catalog_cache() -> None:
    cache = getCatalogCache()
    logging.info(
        "Backend startup preload complete for catalog_year=%s in %.2f ms.",
        cache.catalog_year,
        cache.preload_ms,
    )


@app.on_event("startup")
def _startup_init_snapshot_db() -> None:
    if not snapshot_storage_enabled():
        logging.warning("Program snapshot storage disabled: Supabase environment variables are not configured.")
        return
    init_db()
    logging.info("Program snapshot database initialized.")


def _load_default_catalog() -> Dict:
    return _require_catalog_cache().default_catalog


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

def _ensure_snapshot_storage_available() -> None:
    if snapshot_storage_enabled():
        return
    raise HTTPException(
        status_code=503,
        detail="Program snapshot storage is disabled because Supabase is not configured.",
    )


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/program-snapshots", response_model=CreateSnapshotResponse)
def program_snapshots_create(req: CreateSnapshotRequest):
    _ensure_snapshot_storage_available()
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
    _ensure_snapshot_storage_available()
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
    _require_catalog_cache()
    excel_only_codes = _excel_only_code_set()
    results = search_excel_courses(query=q, term=term, limit=limit)
    return [_with_excel_only_flag(record, excel_only_codes) for record in results]


@app.get("/courses")
def courses_list(term: Optional[str] = None):
    _require_catalog_cache()
    excel_only_codes = _excel_only_code_set()
    results = list_excel_courses(term=term)
    return [_with_excel_only_flag(record, excel_only_codes) for record in results]


@app.get("/courses/{code}")
def courses_get(code: str):
    _require_catalog_cache()

    course = get_excel_course_record(code)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course not found in Excel catalog: {code}")
    excel_only_codes = _excel_only_code_set()
    return _with_excel_only_flag(course, excel_only_codes)


@app.get("/catalog/load-default", response_model=UploadCatalogResponse)
@app.post("/catalog/load-default", response_model=UploadCatalogResponse, include_in_schema=False)
def load_default_catalog():
    cache = _require_catalog_cache()
    catalog = _load_default_catalog()
    catalog_id = cache.default_catalog_id
    CATALOGS[catalog_id] = catalog
    excel_only_codes = sorted(_excel_only_code_set(catalog))

    return UploadCatalogResponse(
        catalog_id=catalog_id,
        catalog_year=cache.catalog_year,
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
    if isinstance(integrity, dict):
        return integrity
    return {"excel_only": [], "pdf_only": []}

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

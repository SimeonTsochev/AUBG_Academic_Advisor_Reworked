# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

AUBG Academic Advisor: a FastAPI backend (`backend/`) that builds a multi-semester degree plan from the AUBG catalog, and a Vite + React + TypeScript frontend (`frontend/`, originally exported from Figma) that lets a student pick majors/minors, import a transcript, and edit the plan.

## Commands

Backend (run from `backend/`). Use Python 3.12: the pinned `pydantic==2.11.7` has no wheel for 3.14 and fails to build without a Rust/MSVC toolchain.

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Tests are `unittest` classes in `backend/tests/` (each file adds `backend/` to `sys.path` itself). pytest is not in requirements but runs them fine.

```bash
python -m unittest discover tests                                   # all
python -m unittest tests.test_plan_validation                       # one file
python -m unittest tests.test_plan_validation.PlanValidationTests.test_validate_plan_catches_prereq_violation
python -m pytest tests -k prereq                                    # if pytest is installed
```

Rebuild the catalog JSON artifacts after changing the source PDF/Excel or the parsers (runtime never parses the PDF/Excel):

```bash
python scripts/build_catalog_artifacts.py      # writes data/excel_catalog.json + data/pdf_requirements.json
python scripts/compare_catalog_mismatch.py     # writes data/catalog_mismatch.json (--stdout-only to preview)
```

Frontend (run from `frontend/`): `npm install`, `npm run dev` (port 3000, set in `vite.config.ts`), `npm run build` (outputs to `build/`). There is no lint or test script. The API base URL comes from `VITE_API_BASE` in `frontend/.env` (default `http://localhost:8000`).

## Architecture

### Catalog data pipeline (offline → runtime)
- Sources: `backend/AY-2025-26-3rd-ed.pdf` (program requirements, prereqs, GenEd rules) and `backend/course_catalog 031926.xlsx` (course list, credits, GenEd tags, term availability, elective tags).
- `catalog_parser.py` (PDF) and `excel_course_catalog.py` / `excel_catalog.py` (Excel) are used only by the build scripts via `catalog_artifacts.py`.
- At runtime `catalog_cache.getCatalogCache()` loads the JSON artifacts from `backend/data/` once, applies `data/policy_overrides.json` (hand-maintained corrections to courses, majors, minors, GenEd, foundation courses), attaches the Excel catalog and mismatch snapshot, and exposes a single `default_catalog` dict. Fix wrong catalog data in `policy_overrides.json` rather than in engine code when possible.
- The catalog dict shape (`courses`, `course_meta` with `prereq_codes`/`prereq_text`, `majors`/`minors` with `required_courses` + `elective_requirements`, `foundation_courses`, `gen_ed.categories`/`gen_ed.rules`, `excel_catalog`) is what every engine function consumes, and what tests build by hand.

### Degree engine (`degree_engine.py`, ~5.5k lines)
`generate_plan(...)` is the single entry point. Rough flow:
1. `build_requirement_slots` turns selected programs, GenEd rules and foundation courses into requirement slots (`fixed` course or `choice` among courses).
2. `select_courses_for_slots` picks a course per slot, preferring courses that satisfy several slots; prerequisites of chosen courses are added.
3. `_schedule_courses` packs courses into terms (prereqs, level/standing rules via `_min_term_index_for_course`, term availability, credit caps), then `balance_term_credits` tops up terms with `FREE ELECTIVE n` placeholders.
4. `_apply_plan_overrides` applies the user's edits (`overrides`: `add`/`remove`/`move`/`locks`, matched by `instance_id` or code) and emits `OVERRIDE_*` warnings instead of failing.
5. `validate_plan` plus warning builders produce `is_valid`, `validation_errors`, `warnings`, `gen_ed_status`, `category_progress`, minor suggestions/alerts and elective recommendations.

Program-specific rules (Computer Science, Creative Writing, Fine Arts and Economics minors, Business concentrations in `business_concentrations.py`, Textual Analysis GenEd sequencing) are hard-coded special cases inside the engine. Search for the program name before changing generic logic.

Term labels are `"Fall YYYY"` / `"Spring YYYY"`. Anything else (e.g. `Summer`) sorts as `999999` in `_term_label_index`.

### API (`main.py`)
Endpoints: `/catalog/load-default`, `/courses`, `/courses/search`, `/courses/{code}`, `/plan/generate`, `/plan/download.pdf` (`pdf_export.py`, reportlab), `/transcript/import` (PDF via pdfplumber, images via OCR) and `/transcript/import-text` (`transcript_import.py`), `/program-snapshots` (`snapshots_db.py`, Supabase). Request/response models are in `models.py` and mirrored by hand in `frontend/src/api.ts`; change both together.
- `/plan/generate` results are memoized in an in-process `PLAN_CACHE` keyed by the request JSON.
- `catalog_id` is effectively always the default catalog; `_ensure_catalog` binds any id to it. The PDF upload endpoint is commented out.
- Env vars: `CORS_ORIGINS`, `CORS_ALLOW_ALL` (Vercel preview domains are always allowed), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (snapshot endpoints return 503 without them).

### Frontend
`App.tsx` switches between `welcome` → `setup` (`AcademicSetupScreen`) → `advisor` (`MainAdvisorScreen`), and restores shared plans from `/p/<token>` snapshot links. `MainAdvisorScreen.tsx` is very large and holds most client state: plan overrides, retakes, transcript import, and a debounced autosave that creates program snapshots. Every edit re-calls `/plan/generate` with the accumulated overrides; the backend is the source of truth for plan contents. Pure helpers are in `src/utils/`; `src/components/ui/` is generated shadcn/Radix UI. `MainAdvisorScreen.tsx.bak.*` is an old backup, not live code.

## Testing gotchas
- `generate_plan` clamps any start term earlier than today's term to the current term (`_current_start_term` uses `date.today()`). Tests that pass a past `start_term_year` really start from the current term; patch `degree_engine._current_start_term` when term labels matter.
- `excel_course_catalog` keeps a module-global course index, and `degree_engine._excel_course_record` falls back to it. Tests that call `load_course_catalog(...)` with a temp workbook leak that state into later tests (it currently breaks `test_transcript_import.py` when run after `test_gened_excel_tags.py` / `test_excel_course_catalog_endpoints.py`).
- The level rule in `_min_term_index_for_course` only matches 3-letter prefixes (`^[A-Z]{3}`), so synthetic catalogs using codes like `CS 1100` never exercise it.
- Importing `main` imports the Supabase SDK at module load.

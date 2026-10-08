# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

AUBG Academic Advisor: a FastAPI backend (`backend/`) that builds a multi-semester degree plan from the AUBG catalog, and a Vite + React + TypeScript frontend (`frontend/`, originally exported from Figma) that lets a student pick majors/minors, import a transcript, and edit the plan.

## Commands

Backend (run from `backend/`). Use Python 3.12: the pinned `pydantic==2.11.7` has no wheel for 3.14. On Windows `py install 3.12-64` installs it without admin rights.

```bash
py -3.12 -m venv .venv && .venv\Scripts\activate      # Windows; python3.12 -m venv .venv elsewhere
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

Tests are `unittest` classes in `backend/tests/`; pytest (with pytest-randomly, so order is shuffled every run) runs them too.

```bash
python -m pytest tests -q                                             # all, random order
python -m pytest tests -q -p no:randomly                              # fixed order
python -m pytest tests/test_real_catalog_scenarios.py -k corequisite  # one test
python -m unittest discover tests                                     # stdlib runner
python -m ruff check .                                                # lint (F rules, see ruff.toml)
```

Frontend (run from `frontend/`): `npm ci`, `npm run dev` (port 3000), `npm run typecheck` (`tsc --noEmit`), `npm test` (vitest, `src/**/*.test.ts`), `npm run build` (outputs to `build/`). The API base URL comes from `VITE_API_BASE` in `frontend/.env`. The React plugin is `@vitejs/plugin-react`, not the SWC one: Windows Application Control on the dev machine blocks the unsigned `@swc/core` binary.

Everything at once, as CI and the pre-push hook do: `backend/.venv/Scripts/python scripts/check.py` from the repo root (`git config core.hooksPath .githooks` enables the hook).

Rebuild the catalog JSON artifacts after changing the source PDF/Excel or the parsers (runtime never parses the PDF/Excel):

```bash
python scripts/build_catalog_artifacts.py      # writes data/excel_catalog.json + data/pdf_requirements.json
python scripts/compare_catalog_mismatch.py     # writes data/catalog_mismatch.json (--stdout-only to preview)
```

## Architecture

### Catalog data pipeline (offline → runtime)
- Sources: `backend/AY-2025-26-3rd-ed.pdf` (program requirements, prereqs, GenEd rules) and `backend/course_catalog 031926.xlsx` (course list, credits, GenEd tags, elective tags, and the Fall 2026 schedule as `semester_availability`).
- `catalog_parser.py` (PDF) and `excel_course_catalog.py` / `excel_catalog.py` (Excel) are used only by the build scripts via `catalog_artifacts.py`.
- At runtime `catalog_cache.getCatalogCache()` loads the JSON artifacts from `backend/data/` once, applies `data/policy_overrides.json`, attaches the Excel catalog and mismatch snapshot, and exposes a single `default_catalog` dict. Fix wrong catalog data in `policy_overrides.json` rather than in engine code: per-course `course_meta` patches (a shallow `dict.update`; e.g. ENG 1000's `coreq_codes`, 0-credit courses) and `degree_total_credits` (120, AY 2025-26 catalog p.85). Policy credits win over Excel and PDF values.
- The catalog dict shape (`courses`, `course_meta` with `prereq_codes`/`prereq_text`/`coreq_codes`, `majors`/`minors` with `required_courses` + `elective_requirements`, `foundation_courses`, `gen_ed.categories`/`gen_ed.rules`, `excel_catalog`, `degree_total_credits`) is what every engine function consumes, and what tests build by hand.

### Degree engine (`degree_engine.py`)
`generate_plan(...)` is the single entry point. Rough flow:
1. `build_requirement_slots` turns selected programs, GenEd rules and foundation courses into requirement slots (`fixed` course or `choice` among courses).
2. `select_courses_for_slots` picks a course per slot, preferring courses that satisfy several slots; prerequisites of chosen courses are added.
3. `_schedule_courses` packs courses into terms (prereqs, standing, GenEd sequencing via `CATEGORY_PREREQS`, co-requisites together, credit caps); `balance_term_credits` pulls courses forward and tops up under-filled terms with `FREE ELECTIVE n` placeholders; `_rebalance_term_mix` swaps courses for variety but never moves foundation courses or co-requisite pairs; `_top_up_to_degree_total` adds placeholders until the plan reaches `degree_total_credits`.
4. `_apply_plan_overrides` applies the user's edits (`overrides`: `add`/`remove`/`move`, matched by `instance_id` or code) and emits `OVERRIDE_*` warnings instead of failing. An instance id that is both removed and added: the remove wins (`OVERRIDE_CONFLICT`).
5. `validate_plan` audits the final plan (requirement coverage re-matched against completed + planned courses, standing, co-requisites, credit limits, degree total); warning builders add `FOUNDATION_LATE`, `TERM_UNAVAILABLE`, `UNSCHEDULED_COURSE`, `PLAN_EXCEEDS_STANDARD_LENGTH`. Each planned course carries `requirements` (e.g. "Computer Science major: required course") and `unlocks`.

Key rules:
- Standing is measured in earned credits (`_min_credits_for_course`): sophomore/junior/senior 30/60/90, "completion of N credits", declared major 30, 3000/4000-level 30/60. Earned credits include transfer (manual) credits and completed courses outside the planning pool, minus placement waivers.
- Term availability: the Excel data is a single-semester schedule. A course is "not offered" in a term only if that term has published data and the course is missing from it (`_offered_terms_if_unavailable`); other terms are unknown and allowed. The frontend mirrors this in `utils/courseAvailability.ts`.
- Plans are capped at `MAX_PLAN_TERMS` (12) and never silently truncated.
- Program-specific rules (Computer Science, Creative Writing, Fine Arts and Economics minors, Business concentrations in `business_concentrations.py`, Textual Analysis GenEd sequencing) are hard-coded special cases inside the engine. Search for the program name before changing generic logic.
- Term labels are `"Fall YYYY"` / `"Spring YYYY"` (`_canonical_term_label`); overrides to anything else are rejected with `OVERRIDE_INVALID_TERM`.

### API (`main.py`)
Endpoints: `/catalog/load-default`, `/courses`, `/courses/search`, `/courses/{code}`, `/plan/generate`, `/plan/download.pdf` (`pdf_export.py`, reportlab), `/transcript/import` (PDF via pdfplumber, images via OCR) and `/transcript/import-text` (`transcript_import.py`), `/program-snapshots` (`snapshots_db.py`, Supabase). Request/response models are in `models.py` and mirrored by hand in `frontend/src/api.ts`; change both together (the type checker now catches drift on the frontend side).
- Plan endpoints are plain `def` (threadpool) because planning is CPU-bound; `/plan/generate` results are memoized in `PLAN_CACHE` (locked) keyed by the request JSON and the current term.
- `catalog_id` is effectively always the default catalog; `_ensure_catalog` binds any id to it.
- Env vars: `CORS_ORIGINS`, `CORS_ALLOW_ALL` (Vercel preview domains are always allowed), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (snapshot endpoints return 503 without them).

### Frontend
`App.tsx` switches between `welcome` → `setup` (`AcademicSetupScreen`) → `advisor` (`MainAdvisorScreen`), and restores shared plans from `/p/<token>` snapshot links. `MainAdvisorScreen.tsx` is very large and holds most client state: plan overrides, retakes, transcript import, chosen electives (`swappedElectives`, with the "Swap elective" flow), and a debounced autosave that creates program snapshots. Every edit re-calls `/plan/generate` with the accumulated overrides; the backend is the source of truth for plan contents. Pure, unit-tested helpers live in `src/utils/` (override edits in `planOverrides.ts`, availability, reasons, terms, retakes, OCR parsing); put new logic there rather than in the component. `src/components/ui/` is generated shadcn/Radix UI.

## Testing gotchas
- Every test class derives from `tests/_isolation.IsolatedTestCase`. `excel_course_catalog` keeps a module-global course index that the engine and transcript import fall back to; each test starts from an empty index (`excel_index = "empty"`, synthetic catalogs) or the shipped one (`excel_index = "real"`) and gets the previous state restored afterwards. Use it for new test classes.
- `generate_plan` clamps any start term earlier than today's term to the current term (`_current_start_term` uses `date.today()`). Patch `degree_engine._current_start_term` when term labels matter (the scenario tests do).
- `degree_total_credits` only applies when the catalog sets it, so synthetic catalogs are not topped up to 120 credits.
- Importing `main` imports the Supabase SDK at module load.

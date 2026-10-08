# AUBG Academic Advisor

Plans a student's remaining semesters from the AUBG 2025-26 catalog: pick majors and minors, import a
transcript, then edit the plan. The backend is the source of truth for what the plan contains and whether
it lets the student graduate.

- `backend/`: FastAPI API and the planning engine (`degree_engine.py`)
- `frontend/`: Vite + React + TypeScript UI

## Run locally

Backend (Python 3.12; the pinned packages do not build on 3.14):

```bash
cd backend
py -3.12 -m venv .venv              # Windows; python3.12 -m venv .venv elsewhere
.venv\Scripts\activate              # source .venv/bin/activate elsewhere
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

Frontend (Node.js LTS):

```bash
cd frontend
npm ci
npm run dev                         # http://localhost:3000
```

The UI calls the API at `VITE_API_BASE` from `frontend/.env` (default `http://localhost:8000`).

## Checks

One command runs everything CI runs: backend lint, backend tests in random order, frontend type check,
frontend unit tests and the production build.

```bash
backend\.venv\Scripts\python scripts\check.py     # Windows
backend/.venv/bin/python scripts/check.py         # macOS/Linux
```

Run it before pushing; to have git do that automatically, enable the pre-push hook once per clone:
`git config core.hooksPath .githooks`. `.github/workflows/ci.yml` runs the same script on GitHub.

## How plans are checked

- `validate_plan` audits the final plan, after the student's own edits. It reports uncovered requirements,
  prerequisites, standing, co-requisites, credit limits and the 120-credit total in `validation_errors`, which
  the UI shows as "Plan needs attention".
- `backend/tests/test_real_catalog_scenarios.py` generates plans for every major at several stages (new
  student, and after 2 and 5 semesters) and audits each one independently. Add a scenario there whenever
  you fix a planning bug.

## Fixing catalog data

Wrong catalog facts (credits, prerequisites, co-requisites, the degree credit total) belong in
`backend/data/policy_overrides.json`, not in engine code. Rebuild the JSON artifacts only after changing
the source PDF/Excel or the parsers (see `CLAUDE.md`).

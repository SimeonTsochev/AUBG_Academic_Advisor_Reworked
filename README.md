# AUBG Academic Advisor (Prototype → Working App)

This repository contains:

- `frontend/` — Vite + React UI (based on your Figma prototype)
- `backend/` — FastAPI API that parses an uploaded AUBG catalog PDF and generates a deterministic plan

## Run (local)

### 1) Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2) Frontend
```bash
cd frontend
npm install
npm run dev
```

Open the UI at the Vite URL (usually `http://localhost:5173`).

## Notes about accuracy (current stage)

- The catalog is parsed deterministically (no AI interpretation).
- Program names are extracted from the table-of-contents section.
- Program requirements are currently **best-effort** (we collect course codes mentioned near each program’s section).
- Semester planning is currently **naive packing** (no prerequisite graph yet).

Next iteration will:
- Parse requirement blocks precisely (required vs electives vs GenEd)
- Add prerequisite-aware planning
- Add real elective ranking across majors/minors/GenEd

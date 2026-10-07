"""Run every automated check: backend lint and tests (random order), frontend typecheck, tests and build.

Run it with the backend virtualenv's Python from the repository root:
    Windows:      backend\\.venv\\Scripts\\python scripts\\check.py
    macOS/Linux:  backend/.venv/bin/python scripts/check.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(label: str, cmd: list[str], cwd: Path) -> None:
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"\nFAILED: {label}", flush=True)
        sys.exit(result.returncode)


def main() -> None:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("npm was not found on PATH; install Node.js LTS first.")

    run("backend lint (ruff)", [sys.executable, "-m", "ruff", "check", "."], BACKEND)
    # pytest-randomly shuffles test order on every run, so order-dependent tests fail fast.
    run("backend tests", [sys.executable, "-m", "pytest", "tests", "-q"], BACKEND)
    run("frontend typecheck", [npm, "run", "typecheck"], FRONTEND)
    run("frontend tests", [npm, "test"], FRONTEND)
    run("frontend build", [npm, "run", "build"], FRONTEND)
    print("\nAll checks passed.", flush=True)


if __name__ == "__main__":
    main()

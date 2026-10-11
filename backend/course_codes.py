"""Course codes as the planner writes them ("COS 1020"). No dependencies, so any module can use it."""
from __future__ import annotations

import re

_CODE = re.compile(r"^([A-Z]{3})\s?(\d{3,4})$")


def normalize_course_code(code: str) -> str:
    code = code.strip().upper()
    m = _CODE.match(code)
    if not m:
        return code
    return f"{m.group(1)} {m.group(2)}"

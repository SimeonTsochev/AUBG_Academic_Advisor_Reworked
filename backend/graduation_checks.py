"""Graduation rules the requirement slots do not express (AY 2026-27 catalog pp.55, 61, 67, 72).

Each check looks at the whole plan (completed, in-progress and planned courses) and returns a
student-facing error when the plan breaks the rule; `generate_plan` adds the errors to its
validation errors and returns the details as `graduation_checks`.
"""
from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Set, Tuple

from degree_engine import _catalog_courses, _course_is_wic, select_courses_for_slots

WIC_REQUIRED = 3
# The foundation writing courses are WICs but do not count toward the three (p.61).
WIC_NOT_COUNTED = {"ENG 1001", "ENG 1002"}
RESIDENCY_CREDITS = 60
RETAKE_LIMIT = 3
# Two majors may share three required courses; any other pair of programs two (p.55).
SHARED_COURSE_LIMIT_TWO_MAJORS = 3
SHARED_COURSE_LIMIT = 2


def _join(names: List[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def wic_check(catalog: Dict, courses: Iterable[str]) -> Tuple[List[str], Dict]:
    wics = sorted({c for c in courses if c not in WIC_NOT_COUNTED and _course_is_wic(catalog, c)})
    errors = []
    # A catalog without WIC flags (the synthetic test catalogs) cannot be checked.
    has_wic_data = bool(wics) or any(_course_is_wic(catalog, c) for c in _catalog_courses(catalog))
    if has_wic_data and len(wics) < WIC_REQUIRED:
        errors.append(
            f"{len(wics)} writing-intensive course{'' if len(wics) == 1 else 's'} (WIC) in the plan besides "
            f"ENG 1001/1002; graduation needs {WIC_REQUIRED} (catalog p.61)."
        )
    return errors, {"required": WIC_REQUIRED, "counted": len(wics), "courses": wics}


def dual_diploma_check(catalog: Dict, majors: List[str]) -> Tuple[List[str], Dict]:
    diplomas = {m: (catalog.get("majors", {}).get(m) or {}).get("diploma") for m in majors}
    known = {m: d for m, d in diplomas.items() if d in ("dual", "single")}
    ok = not known or len(known) < len(diplomas) or any(d == "dual" for d in known.values())
    errors = []
    if not ok:
        names = sorted(known)
        verb = "is a single-diploma major" if len(names) == 1 else "are single-diploma majors"
        errors.append(
            f"{_join(names)} {verb}; graduating requires at least one dual-diploma major (catalog p.72)."
        )
    return errors, {"ok": ok, "majors": diplomas}


def residency_check(catalog: Dict, aubg_credits: int) -> Tuple[List[str], Dict]:
    errors = []
    # Like the degree total, residency only applies to a catalog that states the degree's size.
    if catalog.get("degree_total_credits") and aubg_credits < RESIDENCY_CREDITS:
        errors.append(
            f"Only {aubg_credits} credits are earned or planned at AUBG; graduation needs at least "
            f"{RESIDENCY_CREDITS} in residence (catalog p.61)."
        )
    return errors, {"aubg_credits": aubg_credits, "required": RESIDENCY_CREDITS}


def retake_check(retakes: Set[str]) -> Tuple[List[str], Dict]:
    errors = []
    if len(retakes) > RETAKE_LIMIT:
        errors.append(
            f"{len(retakes)} courses are planned as retakes; students can normally repeat at most "
            f"{RETAKE_LIMIT} courses, each once (catalog p.67)."
        )
    return errors, {"count": len(retakes), "limit": RETAKE_LIMIT}


def double_counting_check(catalog: Dict, slots: Dict, courses: Set[str]) -> Tuple[List[str], List[Dict]]:
    """Courses that fill requirement slots of two selected programs, matched the way the planner does."""
    assignment = select_courses_for_slots(catalog, slots, courses)["slot_assignment"]
    programs_by_course: Dict[str, Set[Tuple[str, str]]] = {}
    for slot_id, code in assignment.items():
        slot = slots.get("by_id", {}).get(slot_id) or {}
        if code in courses and slot.get("program") and slot.get("program_type") in ("major", "minor"):
            programs_by_course.setdefault(code, set()).add((slot["program"], slot["program_type"]))

    shared: Dict[Tuple[Tuple[str, str], Tuple[str, str]], Set[str]] = {}
    for code, programs in programs_by_course.items():
        for pair in combinations(sorted(programs), 2):
            shared.setdefault(pair, set()).add(code)

    errors: List[str] = []
    details: List[Dict] = []
    for (a, b), codes in sorted(shared.items()):
        two_majors = a[1] == b[1] == "major"
        limit = SHARED_COURSE_LIMIT_TWO_MAJORS if two_majors else SHARED_COURSE_LIMIT
        details.append({"programs": [f"{a[0]} {a[1]}", f"{b[0]} {b[1]}"], "courses": sorted(codes), "limit": limit})
        if len(codes) > limit:
            errors.append(
                f"The {a[0]} {a[1]} and the {b[0]} {b[1]} share {len(codes)} courses ({', '.join(sorted(codes))}); "
                f"at most {limit} can count toward both (catalog p.55)."
            )
    return errors, details


def graduation_checks(
    catalog: Dict,
    majors: List[str],
    slots: Dict,
    courses: Set[str],
    aubg_credits: int,
    retakes: Set[str],
) -> Tuple[List[str], Dict]:
    """`courses`: every completed, in-progress and planned course code (no placeholders)."""
    errors: List[str] = []
    checks: Dict = {}
    for key, (check_errors, details) in (
        ("wic", wic_check(catalog, courses)),
        ("dual_diploma", dual_diploma_check(catalog, majors)),
        ("residency", residency_check(catalog, aubg_credits)),
        ("retakes", retake_check(retakes)),
        ("double_counting", double_counting_check(catalog, slots, courses)),
    ):
        errors.extend(check_errors)
        checks[key] = details
    return errors, checks

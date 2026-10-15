"""Graduation rules the requirement slots do not express (AY 2026-27 catalog pp.55, 61-63, 67, 72, 122).

Each check looks at the whole plan (completed, in-progress and planned courses) and returns a
student-facing error when the plan breaks the rule; plan_audit.py adds the errors to the plan's
validation errors and returns the details as `graduation_checks`.
"""
from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Set, Tuple

from catalog_options import options_offered, selected_programs
from course_kinds import independent_study_check, internship_check
from plan_state import PlanState
from degree_engine import (
    _catalog_courses,
    _course_is_wic,
    _enforces_academic_policies,
    program_sequence_rules,
    select_courses_for_slots,
)

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
    """Every student needs a dual-diploma major (p.72). Only a note, never an error: a student
    planning a single-diploma major often has not added the second major yet."""
    diplomas = {m: (catalog.get("majors", {}).get(m) or {}).get("diploma") for m in majors}
    known = {m: d for m, d in diplomas.items() if d in ("dual", "single")}
    ok = not known or len(known) < len(diplomas) or any(d == "dual" for d in known.values())
    return [], {"ok": ok, "majors": diplomas}


def residency_check(catalog: Dict, aubg_credits: int) -> Tuple[List[str], Dict]:
    errors = []
    if _enforces_academic_policies(catalog) and aubg_credits < RESIDENCY_CREDITS:
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
        # Collateral requirements (e.g. the European Studies language) are not the program's own courses.
        if slot.get("collateral"):
            continue
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


def program_options_check(
    catalog: Dict, majors: List[str], minors: List[str], program_options: Dict[str, List[str]] | None
) -> Tuple[List[str], Dict]:
    """A program whose option is required (the European Studies language p.90, an MLC language
    focus pp.102, 124) needs a choice."""
    errors: List[str] = []
    chosen: Dict[str, List[str]] = {}
    for kind, name in selected_programs(majors, minors):
        options = options_offered(catalog, kind, name)
        if options is None:
            continue
        chosen[name] = [choice.name for choice in options.chosen((program_options or {}).get(name) or [])]
        if options.required and not chosen[name]:
            errors.append(
                options.missing_message
                or f"Choose a {str(options.label or 'option').lower()} for the {name} {kind}."
            )
    return errors, chosen


def sequence_check(
    catalog: Dict, majors: List[str], minors: List[str], semester_plan: List[Dict], completed: Set[str]
) -> Tuple[List[str], List[Dict]]:
    """Program rules that one course must come first: the Literature minor's ENG 2010 before any
    3000-level course (p.122). `sequence_rules`: [{before, prefixes, min_level, label}]."""
    term_of = {c["code"]: i for i, term in enumerate(semester_plan) for c in term.get("courses") or []}
    errors: List[str] = []
    details: List[Dict] = []
    for rule in program_sequence_rules(catalog, majors, minors):
        if rule.first in completed:
            continue
        limit = term_of.get(rule.first, len(semester_plan))
        early = sorted(code for code, index in term_of.items() if index <= limit and rule.applies_to(code))
        if early:
            errors.append(f"{rule.label} Planned too early: {', '.join(early)}.")
            details.append({"program": rule.program, "before": rule.first, "courses": early})
    return errors, details


def graduation_checks(state: PlanState, gpa: float | None) -> Tuple[List[str], Dict]:
    """Every check's errors, and the details per check. `gpa`: the cumulative GPA (academic_record)."""
    catalog, courses = state.catalog, state.courses
    errors: List[str] = []
    checks: Dict = {}
    for key, (check_errors, details) in (
        ("wic", wic_check(catalog, courses)),
        ("dual_diploma", dual_diploma_check(catalog, state.majors)),
        ("residency", residency_check(catalog, state.aubg_credits)),
        ("retakes", retake_check(state.retakes)),
        ("double_counting", double_counting_check(catalog, state.slots, courses)),
        ("program_options", program_options_check(catalog, state.majors, state.minors, state.program_options)),
        ("internships", internship_check(catalog, courses)),
        ("independent_study", independent_study_check(state, gpa)),
        ("sequence", sequence_check(catalog, state.majors, state.minors, state.semester_plan, state.reported_completed)),
    ):
        errors.extend(check_errors)
        checks[key] = details
    return errors, checks

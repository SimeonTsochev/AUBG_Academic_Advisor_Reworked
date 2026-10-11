"""GPA, honors and course-load rules from the AY 2026-27 catalog (pp.59-60, 65-66).

Grades come from the student's transcript import and are never stored on the server: the
frontend keeps them in the browser and sends them with each plan request.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from degree_engine import _course_credits, _current_course_code, _term_label_index, select_courses_for_slots

GRADE_POINTS = {
    "A": 4.0, "A-": 3.67,
    "B+": 3.33, "B": 3.0, "B-": 2.67,
    "C+": 2.33, "C": 2.0, "C-": 1.67,
    "D+": 1.33, "D": 1.0,
    "F": 0.0, "X": 0.0, "U": 0.0,
}
# Withdrawals and incompletes keep a student off the Dean's and President's Lists (pp.59-60).
WITHDRAWN_OR_INCOMPLETE = {"W", "I"}
GOOD_STANDING_GPA = 2.0
MAJOR_GPA_MINIMUM = 2.5
LIST_GPA = 3.8
HONORS = (("Summa Cum Laude", 3.9), ("Magna Cum Laude", 3.75), ("Cum Laude", 3.5))
STANDARD_MAX_LOAD = 17
OVERLOAD_GPA = 3.3
OVERLOAD_MAX_LOAD = 19
FIRST_YEAR_CREDITS = 27  # sophomore standing (p.47)


def _gpa(entries: Iterable[Tuple[int, float]]) -> Tuple[float | None, int, float]:
    credits = 0
    points = 0.0
    for course_credits, grade_points in entries:
        credits += course_credits
        points += course_credits * grade_points
    return (round(points / credits, 3) if credits else None), credits, round(points, 3)


def _term_order(term: str | None) -> int:
    index = _term_label_index(term or "")
    return -1 if index == 999999 else index  # an attempt without a known term is the oldest


def latest_grades(catalog: Dict, grades: Iterable[Dict]) -> Dict[str, Dict]:
    """One grade per course, its latest attempt: a retake replaces the earlier grade in GPA (p.59)."""
    latest: Dict[str, Dict] = {}
    for entry in grades:
        code = entry.get("code")
        grade = str(entry.get("grade") or "").strip().upper()
        if not isinstance(code, str) or not grade:
            continue
        code = _current_course_code(catalog, code)
        term = entry.get("term") if isinstance(entry.get("term"), str) else None
        previous = latest.get(code)
        if previous is None or _term_order(term) >= _term_order(previous.get("term")):
            latest[code] = {"grade": grade, "term": term}
    return latest


def honors_outlook(gpa: float | None, attempted: int, points: float, remaining_credits: int) -> Dict:
    current = next((name for name, minimum in HONORS if gpa is not None and gpa >= minimum), None)
    higher = [(name, minimum) for name, minimum in reversed(HONORS) if gpa is None or gpa < minimum]
    outlook: Dict = {"current": current, "next": None}
    if higher and gpa is not None:
        name, minimum = higher[0]
        needed = None
        if remaining_credits > 0:
            needed = round((minimum * (attempted + remaining_credits) - points) / remaining_credits, 2)
        outlook["next"] = {
            "name": name,
            "min_gpa": minimum,
            "needed_average": needed,
            "reachable": needed is not None and needed <= 4.0,
        }
    return outlook


def _terms_phrase(terms: List[str]) -> str:
    names = terms[0] if len(terms) == 1 else ", ".join(terms[:-1]) + " and " + terms[-1]
    return f"{names} {'has' if len(terms) == 1 else 'have'}"


def _load_errors(
    catalog: Dict, semester_plan: List[Dict], occupied: Dict[str, int], earned: int, gpa: float | None
) -> List[str]:
    """One error per broken course-load rule (pp.65-66), naming the terms that break it."""
    # Like residency, the load rules only apply to a catalog that states the degree's size.
    if not catalog.get("degree_total_credits"):
        return []
    first_year: List[str] = []
    low_gpa: List[str] = []
    above_max: List[str] = []
    for term in semester_plan:
        label = term.get("term") or ""
        load = int(term.get("credits") or 0) + int(occupied.get(label, 0) or 0)
        if load > STANDARD_MAX_LOAD and earned < FIRST_YEAR_CREDITS:
            first_year.append(label)
        elif load > OVERLOAD_MAX_LOAD:
            above_max.append(label)
        elif load > STANDARD_MAX_LOAD and gpa is not None and gpa < OVERLOAD_GPA:
            low_gpa.append(label)
        earned += load
    lower = f"Lower the max credits per semester to {STANDARD_MAX_LOAD}."
    errors = []
    if first_year:
        errors.append(
            f"{_terms_phrase(first_year)} more than {STANDARD_MAX_LOAD} credits; first-year students cannot "
            f"take an overload (catalog p.65). {lower}"
        )
    if low_gpa:
        errors.append(
            f"{_terms_phrase(low_gpa)} more than {STANDARD_MAX_LOAD} credits; that needs a cumulative GPA of "
            f"at least {OVERLOAD_GPA:.3f} (yours is {gpa:.3f}, catalog p.66). {lower}"
        )
    if above_max:
        errors.append(
            f"{_terms_phrase(above_max)} more than {OVERLOAD_MAX_LOAD} credits, which needs the Dean of "
            f"Faculty's permission (catalog p.66)."
        )
    return errors


def academic_record(
    catalog: Dict,
    grades: List[Dict],
    majors: List[str],
    slots: Dict,
    elective_progress: List[Dict],
    semester_plan: List[Dict],
    earned_credits: int,
    occupied_credits_by_term: Dict[str, int] | None = None,
    in_progress_credits: int = 0,
) -> Tuple[List[str], Dict]:
    """Errors and the student's GPA record. `earned_credits`: credits earned before the plan starts."""
    latest = latest_grades(catalog, grades)
    graded = {code: entry for code, entry in latest.items() if entry["grade"] in GRADE_POINTS}
    gpa, attempted, points = _gpa(
        (_course_credits(catalog, code), GRADE_POINTS[entry["grade"]]) for code, entry in graded.items()
    )
    has_w_or_i = any(entry["grade"] in WITHDRAWN_OR_INCOMPLETE for entry in latest.values())

    by_term: Dict[str, List[str]] = {}
    for code, entry in latest.items():
        if entry.get("term"):
            by_term.setdefault(entry["term"], []).append(code)
    terms = []
    for term in sorted(by_term, key=_term_order):
        codes = by_term[term]
        term_gpa, term_credits, _ = _gpa(
            (_course_credits(catalog, c), GRADE_POINTS[latest[c]["grade"]]) for c in codes if c in graded
        )
        clean = not any(latest[c]["grade"] in WITHDRAWN_OR_INCOMPLETE for c in codes)
        terms.append({
            "term": term,
            "gpa": term_gpa,
            "credits": term_credits,
            "deans_list": term_gpa is not None and term_gpa >= LIST_GPA and clean,
        })

    planned_credits = sum(
        int(course.get("credits") or 0) for term in semester_plan for course in term.get("courses") or []
    )
    remaining_credits = planned_credits + in_progress_credits

    errors: List[str] = []
    major_records = []
    if graded:
        assignment = select_courses_for_slots(catalog, slots, set(graded))["slot_assignment"]
        for major in majors:
            # Courses the major itself requires or counts as its electives; collateral requirements
            # (courses outside the major, such as the European Studies language) are left out (p.59).
            in_major: Set[str] = {
                code for slot_id, code in assignment.items()
                if code in graded
                and (slot := slots.get("by_id", {}).get(slot_id) or {}).get("program") == major
                and slot.get("program_type") == "major"
                and not slot.get("collateral")
            }
            for entry in elective_progress:
                if entry.get("program") == major and entry.get("program_type") == "major":
                    in_major |= {c["code"] for c in entry.get("courses") or [] if c.get("code") in graded}
            major_gpa, major_credits, _ = _gpa(
                (_course_credits(catalog, c), GRADE_POINTS[graded[c]["grade"]]) for c in sorted(in_major)
            )
            major_records.append({
                "major": major,
                "gpa": major_gpa,
                "credits": major_credits,
                "courses": sorted(in_major),
            })
            if major_gpa is not None and major_gpa < MAJOR_GPA_MINIMUM:
                errors.append(
                    f"Your GPA in the {major} major is {major_gpa:.3f}; graduating in it needs at least "
                    f"{MAJOR_GPA_MINIMUM:.3f} (catalog p.59)."
                )
        if gpa is not None and gpa < GOOD_STANDING_GPA:
            errors.append(
                f"Your cumulative GPA is {gpa:.3f}; good standing and graduation need at least "
                f"{GOOD_STANDING_GPA:.3f} (catalog pp.47, 61)."
            )

    max_load = OVERLOAD_MAX_LOAD if gpa is not None and gpa >= OVERLOAD_GPA else STANDARD_MAX_LOAD
    errors.extend(_load_errors(catalog, semester_plan, occupied_credits_by_term or {}, earned_credits, gpa))

    record = {
        "has_grades": bool(latest),
        "gpa": gpa,
        "attempted_credits": attempted,
        "quality_points": points,
        "terms": terms,
        "presidents_list": gpa is not None and gpa >= LIST_GPA and not has_w_or_i,
        "honors": honors_outlook(gpa, attempted, points, remaining_credits),
        "majors": major_records,
        "max_load": max_load,
        "remaining_credits": remaining_credits,
    }
    return errors, record

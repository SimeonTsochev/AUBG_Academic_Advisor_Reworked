"""Courses the catalog's policies single out by kind: academic internships and independent studies
(AY 2026-27 catalog pp.61, 63), each with its policy in one function.
"""
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from degree_engine import _course_credits, _course_name, _course_number, _enforces_academic_policies
from plan_state import PlanState

INTERNSHIP_CREDIT_LIMIT = 3  # academic internships (p.63)
INDEPENDENT_STUDY_PER_TERM = 2  # p.61
INDEPENDENT_STUDY_TOTAL = 5
INDEPENDENT_STUDY_CREDITS = 30  # p.61: thirty credit hours and a cumulative GPA of 3.100
INDEPENDENT_STUDY_GPA = 3.1


def is_internship(catalog: Dict, code: str) -> bool:
    return "internship" in _course_name(catalog, code).lower() and _course_credits(catalog, code) > 0


def is_independent_study(catalog: Dict, code: str) -> bool:
    number = _course_number(code)
    return (number is not None and number % 1000 == 98) or "independent study" in _course_name(catalog, code).lower()


def internship_check(catalog: Dict, courses: Set[str]) -> Tuple[List[str], Dict]:
    """At most three academic credits may come from internships (p.63)."""
    internships = sorted(c for c in courses if is_internship(catalog, c))
    credits = sum(_course_credits(catalog, c) for c in internships)
    errors = []
    if credits > INTERNSHIP_CREDIT_LIMIT:
        errors.append(
            f"{credits} credits of internships in the plan ({', '.join(internships)}); at most "
            f"{INTERNSHIP_CREDIT_LIMIT} academic credits may come from internships (catalog p.63)."
        )
    return errors, {"courses": internships, "credits": credits, "limit": INTERNSHIP_CREDIT_LIMIT}


def independent_study_check(state: PlanState, gpa: float | None) -> Tuple[List[str], Dict]:
    """No more than two independent studies in a semester and five in all; each needs thirty earned
    credits first and a cumulative GPA of 3.100 (p.61)."""
    catalog = state.catalog
    planned_by_term = {
        term.get("term") or "": [c["code"] for c in term.get("courses") or [] if is_independent_study(catalog, c["code"])]
        for term in state.semester_plan
    }
    done = [c for c in state.reported_completed if is_independent_study(catalog, c)]
    total = len(done) + sum(len(codes) for codes in planned_by_term.values())
    errors = []
    crowded = [term for term, codes in planned_by_term.items() if len(codes) > INDEPENDENT_STUDY_PER_TERM]
    if crowded:
        errors.append(
            f"{', '.join(crowded)} {'has' if len(crowded) == 1 else 'have'} more than {INDEPENDENT_STUDY_PER_TERM} "
            "independent studies; a student may take at most two in a semester (catalog p.61)."
        )
    if total > INDEPENDENT_STUDY_TOTAL:
        errors.append(
            f"{total} independent studies in the plan; at most {INDEPENDENT_STUDY_TOTAL} are allowed in a "
            "student's career (catalog p.61)."
        )
    if _enforces_academic_policies(catalog):
        errors += _eligibility_errors(state, planned_by_term, gpa)
    return errors, {"count": total, "limit": INDEPENDENT_STUDY_TOTAL}


def _eligibility_errors(state: PlanState, planned_by_term: Dict[str, List[str]], gpa: float | None) -> List[str]:
    earned = state.earned_before_plan
    too_early: List[str] = []
    for term in state.semester_plan:
        label = term.get("term") or ""
        if planned_by_term[label] and earned < INDEPENDENT_STUDY_CREDITS:
            too_early += [f"{code} in {label}" for code in planned_by_term[label]]
        earned += int(term.get("credits") or 0) + int(state.occupied_credits_by_term.get(label, 0) or 0)
    studies = [code for codes in planned_by_term.values() for code in codes]
    errors = []
    if too_early:
        errors.append(
            f"Independent study needs {INDEPENDENT_STUDY_CREDITS} earned credits first: {', '.join(too_early)} "
            "comes too early (catalog p.61)."
        )
    if studies and gpa is not None and gpa < INDEPENDENT_STUDY_GPA:
        errors.append(
            f"Independent study ({', '.join(studies)}) needs a cumulative GPA of at least "
            f"{INDEPENDENT_STUDY_GPA:.3f}; yours is {gpa:.3f} (catalog p.61)."
        )
    return errors

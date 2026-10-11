"""Audits a finished plan against the catalog rules the requirement slots do not express.

`generate_plan` schedules the plan, validates it (validate_plan) and builds a `PlanState`; this
module turns that state into everything the response reports beyond the schedule: the progress
rows, elective progress, the graduation checks and the GPA record, plus their errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from academic_record import academic_record
from catalog_options import placement_tests, selected_programs
from degree_engine import (
    _apply_manual_credit_progress,
    _category_credit_progress,
    _completed_credit_total,
    _course_credits,
    _is_business_administration_major,
)
from elective_progress import compute_elective_progress
from graduation_checks import graduation_checks
from plan_state import PlanState


@dataclass(frozen=True)
class PlanAudit:
    errors: List[str]
    """Graduation-check errors, then GPA and course-load errors (after validate_plan's own)."""
    graduation_checks: Dict
    elective_progress: List[Dict]
    category_progress: Dict[str, Dict]
    total_required_credits: int
    earned_credits: int
    in_progress_credits: int
    academic_record: Dict


def audit_plan(state: PlanState) -> PlanAudit:
    graduation_errors, graduation_details = graduation_checks(state)
    elective_progress = _elective_progress(state)
    category_progress = _category_progress(state, elective_progress)
    record_errors, record = academic_record(state, elective_progress)
    return PlanAudit(
        errors=graduation_errors + record_errors,
        graduation_checks=graduation_details,
        elective_progress=elective_progress,
        category_progress=category_progress,
        total_required_credits=_total_required_credits(category_progress),
        earned_credits=state.earned_credits,
        in_progress_credits=_completed_credit_total(state.catalog, state.in_progress),
        academic_record=record,
    )


def _elective_progress(state: PlanState) -> List[Dict]:
    return compute_elective_progress(
        state.catalog,
        programs=[(name, "major") for name in state.majors] + [(name, "minor") for name in state.minors],
        slots=state.slots,
        # Every completed course, including topics courses outside the planning pool (POS 4400).
        completed=state.effective_completed | state.reported_completed,
        planned=state.planned,
        manual_major_elective_credits=state.manual_credit_breakdown.get("major_electives", {}),
        program_options=state.program_options,
        extra_elective_credits=_placement_elective_credits(state),
        waived=state.placement_waived,
    )


def _placement_elective_credits(state: PlanState) -> Dict[Tuple[str, str], int]:
    """Elective credits a program adds for each course a placement test waived ("students who pass
    the placement test may choose another course from the list of electives", p.86)."""
    extra: Dict[Tuple[str, str], int] = {}
    for kind, name in selected_programs(state.majors, state.minors):
        for test in placement_tests(state.catalog, kind, name):
            if test.course in state.placement_waived and test.replace_with_elective:
                extra[(name, kind)] = extra.get((name, kind), 0) + _course_credits(state.catalog, test.course)
    return extra


def _category_progress(state: PlanState, elective_progress: List[Dict]) -> Dict[str, Dict]:
    """Progress rows: each program's required slots and its electives, GenEd, foundation and
    collateral options. Progress counts what is done, not this semester's courses."""
    done = state.done
    progress = _category_credit_progress(
        state.catalog,
        state.slots,
        state.slot_assignment,
        done,
        state.waived,
        selected_majors=state.majors,
        business_concentration=state.business_concentration,
    )
    _apply_manual_credit_progress(progress, state.manual_credit_breakdown)
    # Each program's row covers its electives too (Business has its own breakdown above).
    for entry in elective_progress:
        if entry["program_type"] == "major" and _is_business_administration_major(entry["program"]):
            continue
        group = progress.setdefault("majors" if entry["program_type"] == "major" else "minors", {})
        bucket = group.setdefault(entry["program"], {"required": 0, "completed": 0})
        required = int(entry.get("credits_required") or 0) or 3 * int(entry.get("courses_required") or 0)
        done_credits = sum(int(c.get("credits") or 0) for c in entry.get("courses") or [] if c.get("code") in done)
        bucket["required"] += required
        bucket["completed"] = min(bucket["required"], bucket["completed"] + min(required, done_credits))
    return progress


def _total_required_credits(progress: Dict[str, Dict]) -> int:
    return int(
        sum(v.get("required", 0) for v in progress.get("majors", {}).values())
        + sum(v.get("required", 0) for v in progress.get("minors", {}).values())
        + int(progress.get("gen_ed", {}).get("required", 0) or 0)
        + int(progress.get("foundation", {}).get("required", 0) or 0)
        + sum(v.get("required", 0) for v in progress.get("options", {}).values())
    )

"""The finished plan and the student's record: the facts every plan audit reads.

`generate_plan` builds one `PlanState` after scheduling and the student's edits, and hands it to
plan_audit.py, which runs the graduation checks, elective progress and the GPA record from it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from degree_engine import _completed_credit_total, _is_free_elective, _projected_degree_credits


@dataclass(frozen=True)
class PlanState:
    catalog: Dict
    majors: List[str]
    minors: List[str]
    slots: Dict
    semester_plan: List[Dict]
    slot_assignment: Dict[str, str] = field(default_factory=dict)
    """The planner's requirement slot -> course matching."""
    business_concentration: str | None = None
    # Course codes are current codes (renumbered courses translated).
    reported_completed: Set[str] = field(default_factory=set)
    """Every completed course the student reported, including ones outside the planning pool
    (topics courses such as POS 4400) and, as the frontend sends them, this semester's courses."""
    completed: Set[str] = field(default_factory=set)
    """The planner's completed set: reported courses in the planning pool, plus waived courses."""
    effective_completed: Set[str] = field(default_factory=set)
    """`completed` minus courses whose latest attempt is planned again (a retake)."""
    in_progress: Set[str] = field(default_factory=set)
    """This semester's courses (all of them)."""
    in_progress_in_pool: Set[str] = field(default_factory=set)
    """This semester's courses that are in the planning pool."""
    waived: Set[str] = field(default_factory=set)
    """Placement waivers (MAT 1000, ENG 1000 and program placement tests): satisfied, no credits."""
    placement_waived: Set[str] = field(default_factory=set)
    """Program placement tests only (COS 1020, INF 1030, MLL 2025, ...)."""
    retake_requests: Set[str] = field(default_factory=set)
    program_options: Dict[str, List[str]] = field(default_factory=dict)
    grades: List[Dict[str, Any]] = field(default_factory=list)
    occupied_credits_by_term: Dict[str, int] = field(default_factory=dict)
    credit_offset: int = 0
    """Earned credits beyond `completed`: transfer credits, completed courses outside the pool,
    minus placement waivers (degree_engine.generate_plan)."""
    manual_credit_breakdown: Dict[str, Any] = field(default_factory=dict)
    """Transfer (manual) credits by kind: `total`, `gened`, `major_electives`, `free_elective`."""

    @property
    def planned(self) -> Set[str]:
        """Course codes in the plan, without free-elective placeholders."""
        return {
            course["code"]
            for term in self.semester_plan
            for course in term.get("courses", []) or []
            if isinstance(course.get("code"), str) and not _is_free_elective(course["code"])
        }

    @property
    def courses(self) -> Set[str]:
        """Every completed, in-progress and planned course."""
        return self.reported_completed | self.in_progress | self.planned

    @property
    def done(self) -> Set[str]:
        """Courses already earned: completed, not in progress this semester, and not planned again
        (a retake carries its credits on the planned attempt, so the course counts once, p.67)."""
        return (self.effective_completed | self.reported_completed) - self.in_progress - self.planned

    @property
    def retakes(self) -> Set[str]:
        """Requested retakes plus planned ones (the frontend adds retakes as `is_retake` overrides)."""
        return self.retake_requests | {
            course["code"]
            for term in self.semester_plan
            for course in term.get("courses", []) or []
            if course.get("is_retake") and isinstance(course.get("code"), str)
        }

    @property
    def total_manual_credits(self) -> int:
        return int(self.manual_credit_breakdown.get("total", 0) or 0)

    @property
    def earned_credits(self) -> int:
        """Credits earned so far, each course once; placement waivers earn none, transfer credits count.
        Unlike `done`, a course planned again as a retake keeps the credits it earned until the retake."""
        earned = (self.effective_completed | self.reported_completed) - self.in_progress - self.waived
        return _completed_credit_total(self.catalog, earned) + self.total_manual_credits

    @property
    def earned_before_plan(self) -> int:
        """Earned credits standing and the load rules start from (this semester's courses included)."""
        return _completed_credit_total(self.catalog, self.completed) + self.credit_offset

    @property
    def aubg_credits(self) -> int:
        """Credits earned or planned at AUBG: the projected total minus transfer credits."""
        projected = _projected_degree_credits(
            self.catalog, self.semester_plan, self.completed, self.in_progress_in_pool, self.credit_offset
        )
        return projected - self.total_manual_credits

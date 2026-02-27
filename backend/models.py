from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict

class UploadCatalogResponse(BaseModel):
    catalog_id: str
    catalog_year: Optional[str] = None
    majors: List[str]
    minors: List[str]
    courses: Dict[str, str]  # code -> name
    course_meta: Dict[str, Dict] = Field(default_factory=dict)
    gen_ed: Dict[str, Dict] = Field(default_factory=dict)
    excel_only_codes: List[str] = Field(default_factory=list)

class GeneratePlanRequest(BaseModel):
    catalog_id: str
    majors: List[str] = Field(default_factory=list)
    minors: List[str] = Field(default_factory=list)
    completed_courses: List[str] = Field(default_factory=list)
    retake_courses: List[str] = Field(default_factory=list)
    in_progress_courses: List[str] = Field(default_factory=list)
    in_progress_terms: Dict[str, str] = Field(default_factory=dict)
    current_term_label: Optional[str] = None
    max_credits_per_semester: int = 16
    start_term_season: Optional[str] = None
    start_term_year: Optional[int] = None
    waived_mat1000: bool = False
    waived_eng1000: bool = False
    strict_prereqs: bool = False
    overrides: Optional[PlanOverrides] = None

    # Phase 9: plan optimization (multi-candidate scheduling + scoring)
    optimize: bool = False
    optimization_passes: int = 1


class PlanOverrideAdd(BaseModel):
    term: str
    code: str
    instance_id: Optional[str] = None
    gen_ed_category: Optional[str] = None

class PlanOverrideRemove(BaseModel):
    term: Optional[str] = None  # if None, remove from any term
    code: Optional[str] = None
    instance_id: Optional[str] = None

class PlanOverrideMove(BaseModel):
    from_term: str
    to_term: str
    code: Optional[str] = None
    instance_id: Optional[str] = None


class PlanOverrideLock(BaseModel):
    """Locks a course into a specific term.

    Unlike a move override, a lock does not require knowing the course's current term.
    The engine will locate the course in any term and place it into the locked term.
    """

    term: str
    code: Optional[str] = None
    instance_id: Optional[str] = None

class PlanOverrides(BaseModel):
    add: List[PlanOverrideAdd] = Field(default_factory=list)
    remove: List[PlanOverrideRemove] = Field(default_factory=list)
    move: List[PlanOverrideMove] = Field(default_factory=list)
    locks: List[PlanOverrideLock] = Field(default_factory=list)


class PlanCourse(BaseModel):
    code: str
    name: str
    credits: int
    tags: List[str] = Field(default_factory=list)
    satisfies: List[str] = Field(default_factory=list)
    excel_elective_tags: List[str] = Field(default_factory=list)
    type: str
    source_reason: str
    instance_id: str

class SemesterPlan(BaseModel):
    term: str
    courses: List[PlanCourse]
    credits: int

class MinorAlert(BaseModel):
    minor: str
    remaining_courses: List[str]
    # Backend uses remaining_count for conditional UI rendering.
    # Optional for compatibility with older responses.
    remaining_count: Optional[int] = None


class MinorSwapSuggestion(BaseModel):
    term: str
    replace_code: str
    replace_instance_id: Optional[str] = None
    replace_slot_index: int
    add_code: str
    reason: str


class MinorSuggestion(BaseModel):
    minor: str
    remaining_courses: List[str]
    remaining_count: int
    score: float
    why: str
    swap_suggestions: List[MinorSwapSuggestion] = Field(default_factory=list)

class ElectiveRecommendation(BaseModel):
    code: str
    name: str
    credits: int
    requirementsSatisfied: int
    tags: List[str] = Field(default_factory=list)
    explanation: str

class ElectivePlaceholder(BaseModel):
    id: str
    program: str
    program_type: str  # "major" | "minor"
    label: str
    credits_required: Optional[int] = None
    courses_required: Optional[int] = None
    allowed_courses: List[str] = Field(default_factory=list)
    rule_text: str
    is_total: bool = False

class GenEdDiscoveryCourse(BaseModel):
    code: str
    name: str
    credits: int
    tags: List[str] = Field(default_factory=list)

class GenEdDiscovery(BaseModel):
    case_studies_textual_analysis: List[GenEdDiscoveryCourse] = Field(default_factory=list)

class PlanWarning(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    message: Optional[str] = None
    course: Optional[str] = None
    term: Optional[str] = None
    credits: Optional[int] = None
    max: Optional[int] = None
    min: Optional[int] = None
    unmet: List[str] = Field(default_factory=list)

class GeneratePlanResponse(BaseModel):
    catalog_id: str
    catalog_year: Optional[str] = None
    majors: List[str]
    minors: List[str]
    completed_courses: List[str]
    remaining_courses: List[str]
    semester_plan: List[SemesterPlan]
    minor_alerts: List[MinorAlert]
    minor_suggestions: List[MinorSuggestion] = Field(default_factory=list)
    elective_recommendations: List[ElectiveRecommendation] = Field(default_factory=list)
    elective_course_codes: List[str] = Field(default_factory=list)
    excel_elective_tags: Dict[str, List[str]] = Field(default_factory=dict)
    elective_placeholders: List[ElectivePlaceholder] = Field(default_factory=list)
    gened_discovery: GenEdDiscovery = Field(default_factory=GenEdDiscovery)
    summary: Dict[str, int]
    course_reasons: Dict[str, str] = Field(default_factory=dict)
    gen_ed_status: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    category_progress: Dict[str, Dict] = Field(default_factory=dict)
    warnings: List[PlanWarning] = Field(default_factory=list)
    is_valid: bool = True
    validation_errors: List[str] = Field(default_factory=list)


# Pydantic forward refs
# GeneratePlanRequest.update_forward_refs(PlanOverrides=PlanOverrides)

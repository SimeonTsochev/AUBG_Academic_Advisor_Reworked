import type { FailedCourse, ManualCreditEntry, RetakeEntry } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE || "";

/** Options a major offers, e.g. a Computer Science concentration or the European Studies language. */
export interface ProgramOptions {
  label: string;
  required: boolean;
  multiple: boolean;
  choices: string[];
  description?: string | null;
}

/** A course a placement test can waive (catalog pp.86, 95, 105, 126). */
export interface PlacementWaiver {
  course: string;
  label: string;
}

export interface ProgramInfo {
  diploma?: "dual" | "single" | null;
  options?: ProgramOptions | null;
  placement_waivers?: PlacementWaiver[];
}

/** Per major, the chosen options (e.g. { "European Studies": ["French"] }). */
export type ProgramOptionSelection = Record<string, string[]>;

export interface UploadCatalogResponse {
  catalog_id: string;
  catalog_year?: string | null;
  majors: string[];
  minors: string[];
  excel_only_codes?: string[];
  /** Per major: diploma type ("dual" = US + Bulgarian, catalog p.72) and the options a student chooses. */
  program_info?: Record<string, ProgramInfo>;
  /** The same for minors (Modern Languages and Cultures is both, with its own options for each). */
  minor_info?: Record<string, ProgramInfo>;
  courses: Record<string, string>; // code -> title (best-effort)
  course_meta?: Record<string, {
    title?: string | null;
    credits?: number;
    gen_ed?: string | null;
    gen_ed_tags?: string[];
    wic?: boolean;
    is_excel_only?: boolean;
    semester_availability?: string[];
    prereq_text?: string | null;
    prereq_codes?: string[];
    coreq_codes?: string[];
    prereqs?: string[];
    prereq_expr?: unknown;
    prereq_blocks?: Array<{
      type?: string;
      code?: string;
      courses?: string[];
      items?: unknown[];
      blocks?: unknown[];
      options?: unknown[];
      choices?: unknown[];
    }>;
    frequency?: string | null;
  }>;
  gen_ed?: {
    categories?: Record<string, string[]>;
    rules?: Record<string, number>;
  };
}

export interface BusinessCourseClassification {
  concentration?: string | null;
  required_for_bus_core?: boolean;
  required_for_concentration?: boolean;
  elective_for_concentration?: boolean;
  counts_as_bus_elective?: boolean;
  manual_review?: boolean;
  badges?: string[];
}

export interface CourseCatalogRecord {
  code: string;
  title: string;
  credits?: number | null;
  is_excel_only?: boolean;
  department?: string;
  prefix?: string;
  level?: string | null;
  area_of_study_tags?: string[];
  gen_ed_tags?: string[];
  wic?: boolean;
  semester_availability?: string[];
  availability_fields?: Record<string, string[]>;
  business_classification?: BusinessCourseClassification;
}

export interface SearchCoursesContext {
  catalogId?: string;
  majors?: string[];
  minors?: string[];
  businessConcentration?: string | null;
}

export interface TranscriptImportMatchCandidate {
  code: string;
  title: string;
  confidence: number;
}

export interface TranscriptImportCourse {
  raw_code: string;
  matched_code?: string | null;
  title?: string | null;
  raw_title?: string | null;
  status: "completed" | "in_progress" | "failed";
  /** Final grade read from the transcript row, e.g. "B+" or "F". */
  grade?: string | null;
  term?: string | null;
  confidence: number;
  matched_confidently: boolean;
  match_candidates: TranscriptImportMatchCandidate[];
}

/** Elective credits (or courses) a program already has from completed and planned courses. */
/** One elective sub-rule from the catalog, e.g. "At most three non-COS courses" (backend elective_rules.py). */
export interface ElectiveRuleStatus {
  label: string;
  kind: "at_least" | "at_most" | "at_least_in_one_group" | string;
  unit: "credits" | "courses";
  required: number;
  counted: number;
  met: boolean;
  /** at_most only: more than the cap is planned, so the extra does not count. */
  over_cap?: boolean;
}

export interface ElectiveProgress {
  program: string;
  program_type: "major" | "minor";
  credits_required?: number | null;
  courses_required?: number | null;
  credits_counted: number;
  remaining: number;
  unit: "credits" | "courses";
  rule_text: string;
  rules?: ElectiveRuleStatus[];
  courses: { code: string; credits: number; completed: boolean }[];
}

export interface TranscriptImportResponse {
  completed: TranscriptImportCourse[];
  in_progress: TranscriptImportCourse[];
  /** Latest attempt not passed (F, W, WF, U, NP, NR, I): retaken by the plan when still required. */
  failed: TranscriptImportCourse[];
  unmatched: TranscriptImportCourse[];
  /** Lines that look like course rows but could not be read (usually OCR damage). */
  unread_lines?: TranscriptUnreadLine[];
  warnings: string[];
}

export interface TranscriptUnreadLine {
  text: string;
  page_number: number;
}

export interface TranscriptImportLineInput {
  text: string;
  page_number?: number;
  confidence?: number;
}

// Legacy upload flow (kept for future multi-university support)
/*
export async function uploadCatalog(file: File): Promise<UploadCatalogResponse> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/catalog/upload`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail ?? `Upload failed (${res.status})`);
  }
  return res.json();
}
*/

export async function loadDefaultCatalog(): Promise<UploadCatalogResponse> {
  const res = await fetch(`${API_BASE}/catalog/load-default`, {
    method: "GET",
  });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail ?? `Catalog load failed (${res.status})`);
  }
  return res.json();
}

export async function searchCourses(
  query: string,
  term?: string,
  limit = 50,
  context?: SearchCoursesContext
): Promise<CourseCatalogRecord[]> {
  const q = query.trim();
  if (!q) return [];
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (term?.trim()) params.set("term", term.trim());
  if (context?.catalogId?.trim()) params.set("catalog_id", context.catalogId.trim());
  if (context?.businessConcentration?.trim()) {
    params.set("business_concentration", context.businessConcentration.trim());
  }
  for (const major of context?.majors ?? []) {
    if (major.trim()) params.append("major", major.trim());
  }
  for (const minor of context?.minors ?? []) {
    if (minor.trim()) params.append("minor", minor.trim());
  }

  const res = await fetch(`${API_BASE}/courses/search?${params.toString()}`, {
    method: "GET",
  });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail ?? `Course search failed (${res.status})`);
  }
  return res.json();
}

export async function getCourse(code: string): Promise<CourseCatalogRecord> {
  const encoded = encodeURIComponent(code);
  const res = await fetch(`${API_BASE}/courses/${encoded}`, {
    method: "GET",
  });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail ?? `Course lookup failed (${res.status})`);
  }
  return res.json();
}

export async function listCourses(term?: string): Promise<CourseCatalogRecord[]> {
  const params = new URLSearchParams();
  if (term?.trim()) params.set("term", term.trim());
  const query = params.toString();
  const url = query ? `${API_BASE}/courses?${query}` : `${API_BASE}/courses`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    const detail = await safeDetail(res);
    throw new Error(detail ?? `Course list failed (${res.status})`);
  }
  return res.json();
}

export async function importTranscript(
  file: File,
  catalogId?: string
): Promise<TranscriptImportResponse> {
  const form = new FormData();
  form.append("file", file);
  if (catalogId?.trim()) {
    form.append("catalog_id", catalogId.trim());
  }

  const res = await fetch(`${API_BASE}/transcript/import`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const detail = (await readErrorDetail(res)) ?? (await safeDetail(res));
    throw new Error(detail ?? `Transcript import failed (${res.status})`);
  }
  return res.json();
}

export async function importTranscriptText(
  lines: TranscriptImportLineInput[],
  options?: {
    text?: string;
    usedOcr?: boolean;
  }
): Promise<TranscriptImportResponse> {
  const res = await fetch(`${API_BASE}/transcript/import-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: options?.text ?? null,
      lines,
      used_ocr: options?.usedOcr ?? false,
    }),
  });
  if (!res.ok) {
    const detail = (await readErrorDetail(res)) ?? (await safeDetail(res));
    throw new Error(detail ?? `Transcript import failed (${res.status})`);
  }
  return res.json();
}


export interface PlanOverrideAdd { term: string; code: string; instance_id?: string | null; gen_ed_category?: string | null; is_retake?: boolean; }
export interface PlanOverrideRemove { term?: string | null; code?: string | null; instance_id?: string | null; }
export interface PlanOverrideMove { from_term: string; to_term: string; code?: string | null; instance_id?: string | null; }

export interface PlanOverrides {
  add: PlanOverrideAdd[];
  remove: PlanOverrideRemove[];
  move: PlanOverrideMove[];
}

export interface ProgramSnapshotSwappedElective {
  termLabel: string;
  addedCourseCode: string;
  addedCourseInstanceId: string;
  replacedPlaceholderInstanceId: string;
  placeholderCode: string;
  placeholderCredits: number;
}

export interface ProgramSnapshotPayload {
  majors: string[];
  minors: string[];
  businessConcentration?: string | null;
  economicsIntermediateChoice?: "ECO 3001" | "ECO 3002" | null;
  programOptions?: ProgramOptionSelection;
  /** Courses a placement test waived. */
  placementWaivers?: string[];
  completedCourses: string[];
  inProgressCourses: string[];
  failedCourses?: FailedCourse[];
  manualCredits: ManualCreditEntry[];
  completedOverrides: Record<string, string>;
  inProgressOverrides: Record<string, string>;
  overrides: PlanOverrides;
  swappedElectives: ProgramSnapshotSwappedElective[];
  removedCourses: string[];
  start_term_season: string;
  start_term_year: number;
  /** Older snapshots only: plans follow the catalog's course load now. */
  max_credits_per_semester?: number;
  waived_mat1000: boolean;
  waived_eng1000: boolean;
  strict_prereqs: boolean;
  retakeCourses: string[];
  retakeEntries: RetakeEntry[];
  current_term_label?: string | null;
  lastRolloverTermApplied?: string;
}

export interface CreateProgramSnapshotResponse {
  token: string;
  expires_at: number;
}

export interface GetProgramSnapshotResponse {
  token: string;
  expires_at: number;
  catalog_year: string;
  payload: ProgramSnapshotPayload;
}

export interface GeneratePlanRequest {
  catalog_id: string;
  majors: string[];
  minors: string[];
  business_concentration?: string | null;
  program_options?: ProgramOptionSelection;
  completed_courses: string[];
  /** Transcript grades for GPA; kept in the browser, never in a snapshot. */
  grades?: GradeEntry[];
  placement_waivers?: string[];
  manual_credits?: ManualCreditEntry[];
  retake_courses?: string[];
  /** The student's pick for a "choose one" requirement, e.g. ECO 3002 for the Economics minor. */
  preferred_courses?: string[];
  in_progress_courses?: string[];
  in_progress_terms?: Record<string, string>;
  current_term_label?: string | null;
  start_term_season?: string | null;
  start_term_year?: number | null;
  waived_mat1000?: boolean;
  waived_eng1000?: boolean;
  strict_prereqs?: boolean;
  overrides?: PlanOverrides;
}

export interface SemesterPlan {
  term: string;
  courses: PlanCourse[];
  credits: number;
}

export interface CourseRequirement {
  program?: string | null;
  program_type: "major" | "minor" | "gened" | "foundation" | "free" | string;
  kind: "required" | "choice" | "gened" | "elective" | string;
  /** e.g. "Computer Science major: required course", "GenEd: Aesthetic Expression" */
  label: string;
}

export interface PlanCourse {
  code: string;
  name: string;
  credits: number;
  tags: string[];
  satisfies: string[];
  requirements?: CourseRequirement[];
  /** Planned courses that list this one as a prerequisite. */
  unlocks?: string[];
  excel_elective_tags?: string[];
  type: "PROGRAM" | "GENED" | "FREE" | "FOUNDATION" | "FREE_ELECTIVE";
  source_reason?: string;
  instance_id: string;
  is_retake?: boolean;
}

export interface MinorAlert {
  minor: string;
  remaining_courses: string[];
  remaining_count?: number;
}

export interface MinorSwapSuggestion {
  term: string;
  replace_code: string;
  replace_instance_id?: string | null;
  replace_slot_index: number;
  add_code: string;
  reason: string;
}

export interface MinorSuggestion {
  minor: string;
  remaining_courses: string[];
  remaining_count: number;
  score: number;
  why: string;
  swap_suggestions: MinorSwapSuggestion[];
}

export interface PlanWarning {
  type: string;
  course?: string;
  term?: string;
  message?: string;
  unmet?: string[];
  offered_terms?: string[];
  [key: string]: unknown;
}

export interface GradeEntry {
  code: string;
  grade: string;
  term?: string | null;
}

/** GPA, honors and the course-load limit from the student's grades (backend academic_record.py). */
export interface AcademicRecord {
  has_grades: boolean;
  gpa: number | null;
  attempted_credits: number;
  quality_points: number;
  terms: { term: string; gpa: number | null; credits: number; deans_list: boolean }[];
  presidents_list: boolean;
  honors: {
    current: string | null;
    next: { name: string; min_gpa: number; needed_average: number | null; reachable: boolean } | null;
  };
  majors: { major: string; gpa: number | null; credits: number; courses: string[] }[];
  max_load: number;
  remaining_credits: number;
  /** Completed courses with credit but no grade (the transcript import missed it). */
  ungraded_courses?: string[];
}

/** Catalog graduation rules outside the requirement slots (backend graduation_checks.py). */
export interface GraduationChecks {
  wic: { required: number; counted: number; courses: string[] };
  dual_diploma: { ok: boolean; majors: Record<string, "dual" | "single" | null> };
  residency: { aubg_credits: number; required: number };
  retakes: { count: number; limit: number };
  double_counting: { programs: string[]; courses: string[]; limit: number }[];
  program_options: ProgramOptionSelection;
  internships: { courses: string[]; credits: number; limit: number };
  independent_study: { count: number; limit: number };
  sequence: { program: string; before: string; courses: string[] }[];
}

export interface GeneratePlanResponse {
  catalog_id: string;
  catalog_year?: string | null;
  majors: string[];
  minors: string[];
  business_concentration?: string | null;
  completed_courses: string[];
  remaining_courses: string[];
  semester_plan: SemesterPlan[];
  minor_alerts: MinorAlert[];
  minor_suggestions?: MinorSuggestion[];
  elective_recommendations?: {
    code: string;
    name: string;
    credits: number;
    requirementsSatisfied: number;
    tags: string[];
    explanation: string;
  }[];
  elective_course_codes?: string[];
  excel_elective_tags?: Record<string, string[]>;
  elective_placeholders?: {
    id: string;
    program: string;
    program_type: "major" | "minor";
    label: string;
    credits_required?: number | null;
    courses_required?: number | null;
    allowed_courses?: string[];
    rule_text?: string;
    is_total?: boolean;
  }[];
  elective_progress?: ElectiveProgress[];
  business_concentration_audit?: {
    selected?: string;
    required_courses?: {
      code: string;
      title: string;
      credits: number;
      status: "completed" | "planned" | "missing";
    }[];
    elective_pools?: {
      id: string;
      label: string;
      required_credits?: number;
      counted_credits?: number;
      remaining_credits?: number;
      courses_required?: number;
      counted_courses?: number;
      remaining_courses?: number;
      matched_courses?: {
        code: string;
        title: string;
        credits: number;
        counted_credits: number;
        status: "completed" | "planned";
      }[];
      notes?: string[];
    }[];
    messages?: {
      kind: string;
      message: string;
    }[];
    summary?: Record<string, number>;
  } | null;
  summary: Record<string, number>;
  gen_ed_status?: Record<string, { required: number; completed: number; planned: number }>;
  category_progress?: {
    majors?: Record<string, { required: number; completed: number }>;
    minors?: Record<string, { required: number; completed: number }>;
    gen_ed?: { required: number; completed: number };
    foundation?: { required: number; completed: number };
    /** Requirements a major sets outside its own credits, e.g. "European Studies: French language proficiency (B1)". */
    options?: Record<string, { program: string; label: string; required: number; completed: number }>;
    free_elective?: { required: number; completed: number };
    minors_gened?: { required: number; completed: number };
  };
  course_reasons?: Record<string, string>;
  warnings?: PlanWarning[];
  is_valid?: boolean;
  validation_errors?: string[];
  graduation_checks?: GraduationChecks | null;
  academic_record?: AcademicRecord | null;
  gened_discovery?: {
    case_studies_textual_analysis?: {
      code: string;
      name: string;
      credits: number;
      tags: string[];
    }[];
  };
}

export async function generatePlan(payload: GeneratePlanRequest): Promise<GeneratePlanResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/plan/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e: any) {
    throw new Error(`POST /plan/generate failed: ${e?.message ?? e}`);
  }
  if (!res.ok) {
    const detail = (await readErrorDetail(res)) ?? (await safeDetail(res));
    const statusInfo = `${res.status} ${res.statusText}`.trim();
    throw new Error(
      detail
        ? `POST /plan/generate failed (${statusInfo}): ${detail}`
        : `POST /plan/generate failed (${statusInfo})`
    );
  }
  return res.json();
}

export async function downloadPlanPdf(payload: GeneratePlanRequest): Promise<Blob> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/plan/download.pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e: any) {
    throw new Error(`POST /plan/download.pdf failed: ${e?.message ?? e}`);
  }
  if (!res.ok) {
    const detail = (await readErrorDetail(res)) ?? (await safeDetail(res));
    const statusInfo = `${res.status} ${res.statusText}`.trim();
    throw new Error(
      detail
        ? `POST /plan/download.pdf failed (${statusInfo}): ${detail}`
        : `POST /plan/download.pdf failed (${statusInfo})`
    );
  }
  return res.blob();
}

export async function createProgramSnapshot(
  catalog_year: string,
  payload: ProgramSnapshotPayload
): Promise<CreateProgramSnapshotResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/program-snapshots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ catalog_year, payload }),
    });
  } catch (e: any) {
    throw new Error(`POST /program-snapshots failed: ${e?.message ?? e}`);
  }
  if (!res.ok) {
    const detail = (await readErrorDetail(res)) ?? (await safeDetail(res));
    const statusInfo = `${res.status} ${res.statusText}`.trim();
    throw new Error(
      detail
        ? `POST /program-snapshots failed (${statusInfo}): ${detail}`
        : `POST /program-snapshots failed (${statusInfo})`
    );
  }
  return res.json();
}

export async function getProgramSnapshot(token: string): Promise<GetProgramSnapshotResponse> {
  const encodedToken = encodeURIComponent(token);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/program-snapshots/${encodedToken}`, {
      method: "GET",
    });
  } catch (e: any) {
    throw new Error(`GET /program-snapshots/${token} failed: ${e?.message ?? e}`);
  }
  if (!res.ok) {
    const detail = (await readErrorDetail(res)) ?? (await safeDetail(res));
    const statusInfo = `${res.status} ${res.statusText}`.trim();
    throw new Error(
      detail
        ? `GET /program-snapshots/${token} failed (${statusInfo}): ${detail}`
        : `GET /program-snapshots/${token} failed (${statusInfo})`
    );
  }
  return res.json();
}


async function readErrorDetail(res: Response): Promise<string | null> {
  try {
    const data = await res.clone().json();
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.message === "string") return data.message;
  } catch {
    // ignore
  }
  try {
    const txt = await res.text();
    return txt ? txt : null;
  } catch {
    return null;
  }
}
async function safeDetail(res: Response): Promise<string | null> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    return null;
  } catch {
    return null;
  }
}

import type { ManualCreditEntry, RetakeEntry } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE || "";

export interface UploadCatalogResponse {
  catalog_id: string;
  catalog_year?: string | null;
  majors: string[];
  minors: string[];
  excel_only_codes?: string[];
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
  status: "completed" | "in_progress";
  term?: string | null;
  confidence: number;
  matched_confidently: boolean;
  match_candidates: TranscriptImportMatchCandidate[];
}

export interface TranscriptImportResponse {
  completed: TranscriptImportCourse[];
  in_progress: TranscriptImportCourse[];
  unmatched: TranscriptImportCourse[];
  warnings: string[];
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
  locks?: PlanOverrideLock[];
}

export interface PlanOverrideLock {
  term: string;
  code?: string;
  instance_id?: string;
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
  completedCourses: string[];
  inProgressCourses: string[];
  manualCredits: ManualCreditEntry[];
  completedOverrides: Record<string, string>;
  inProgressOverrides: Record<string, string>;
  overrides: PlanOverrides;
  swappedElectives: ProgramSnapshotSwappedElective[];
  removedCourses: string[];
  start_term_season: string;
  start_term_year: number;
  max_credits_per_semester: number;
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
  completed_courses: string[];
  manual_credits?: ManualCreditEntry[];
  retake_courses?: string[];
  in_progress_courses?: string[];
  in_progress_terms?: Record<string, string>;
  current_term_label?: string | null;
  max_credits_per_semester: number;
  start_term_season?: string | null;
  start_term_year?: number | null;
  waived_mat1000?: boolean;
  waived_eng1000?: boolean;
  strict_prereqs?: boolean;
  overrides?: PlanOverrides;

  // Phase 9 optimization
  optimize?: boolean;
  optimization_passes?: number;
}

export interface SemesterPlan {
  term: string;
  courses: PlanCourse[];
  credits: number;
}

export interface PlanCourse {
  code: string;
  name: string;
  credits: number;
  tags: string[];
  satisfies: string[];
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
    free_elective?: { required: number; completed: number };
    minors_gened?: { required: number; completed: number };
  };
  course_reasons?: Record<string, string>;
  warnings?: PlanWarning[];
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

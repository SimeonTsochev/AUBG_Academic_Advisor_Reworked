import type { CourseCatalogRecord } from "../api";

type CourseAvailabilitySource = Pick<CourseCatalogRecord, "semester_availability"> | null | undefined;

export type CourseSelectionMode = "completed" | "in_progress" | "plan_add";

export interface CourseAvailabilityContext {
  mode: CourseSelectionMode;
  isExcelOnly?: boolean;
  currentTermLabel?: string | null;
  targetTermLabel?: string | null;
  /**
   * Terms that have a published schedule (see scheduleTermsFromCourseMeta). The schedule data
   * covers single semesters, so a course is only "not offered" in a term that has one; any other
   * term is unknown and never blocked.
   */
  scheduleTerms?: readonly string[] | null;
}

export interface CourseAvailabilityInfo {
  unavailableThisTerm: boolean;
  isSelectionBlocked: boolean;
  rowShouldBeMuted: boolean;
  termToCheck: string | null;
  warningLabel: string | null;
  detailsLabel: string | null;
  offeredTerms: string[];
}

const normalizeTermLabel = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");

/** Every term that at least one course is listed for, i.e. the terms with a published schedule. */
export function scheduleTermsFromCourseMeta(
  courseMeta: Record<string, { semester_availability?: string[] | null } | undefined> | null | undefined
): string[] {
  const terms = new Set<string>();
  for (const meta of Object.values(courseMeta ?? {})) {
    for (const term of meta?.semester_availability ?? []) {
      if (typeof term === "string" && term.trim()) terms.add(term.trim());
    }
  }
  return Array.from(terms);
}

export function getCourseAvailabilityInfo(
  course: CourseAvailabilitySource,
  context: CourseAvailabilityContext
): CourseAvailabilityInfo {
  const { mode, isExcelOnly, currentTermLabel, targetTermLabel, scheduleTerms } = context;
  const offeredTerms = (course?.semester_availability ?? [])
    .filter((term): term is string => typeof term === "string" && term.trim().length > 0)
    .map((term) => term.trim());
  // Adding to a chosen term follows the planner's rule for every course with a schedule record
  // (an empty list is a record that no published term lists); the planner refuses anything else.
  // Other checks only cover Excel-only courses with listed terms.
  const shouldEnforceTermAvailability =
    mode === "plan_add" && Boolean(targetTermLabel?.trim())
      ? Array.isArray(course?.semester_availability)
      : isExcelOnly === true && offeredTerms.length > 0;
  const publishedTerms = new Set((scheduleTerms ?? []).map(normalizeTermLabel));
  const offeredTermsLabel =
    offeredTerms.length > 0 ? `Offered only in: ${offeredTerms.join(", ")}` : "Not listed in any published schedule";

  const computeUnavailable = (termToCheck: string | null) => {
    if (!shouldEnforceTermAvailability || !termToCheck) return false;
    const normalizedTarget = normalizeTermLabel(termToCheck);
    if (!publishedTerms.has(normalizedTarget)) return false;
    return !offeredTerms.some((term) => normalizeTermLabel(term) === normalizedTarget);
  };

  if (mode === "completed") {
    const hasCurrentMismatch = computeUnavailable(currentTermLabel?.trim() || null);
    if (!hasCurrentMismatch) {
      return {
        unavailableThisTerm: false,
        isSelectionBlocked: false,
        rowShouldBeMuted: false,
        termToCheck: null,
        warningLabel: null,
        detailsLabel: null,
        offeredTerms,
      };
    }
    return {
      unavailableThisTerm: false,
      isSelectionBlocked: false,
      rowShouldBeMuted: false,
      termToCheck: null,
      warningLabel: `Not offered in ${currentTermLabel?.trim() ?? "this term"} (OK if completed earlier)`,
      detailsLabel: offeredTermsLabel,
      offeredTerms,
    };
  }

  const termToCheck =
    mode === "plan_add"
      ? targetTermLabel?.trim() || currentTermLabel?.trim() || null
      : currentTermLabel?.trim() || null;
  const isUnavailable = computeUnavailable(termToCheck);
  const shouldBlock = mode === "plan_add" && isUnavailable;

  if (!isUnavailable) {
    return {
      unavailableThisTerm: false,
      isSelectionBlocked: false,
      rowShouldBeMuted: false,
      termToCheck,
      warningLabel: null,
      detailsLabel: null,
      offeredTerms,
    };
  }

  const termLabel = termToCheck ?? "this term";
  return {
    unavailableThisTerm: true,
    isSelectionBlocked: shouldBlock,
    rowShouldBeMuted: shouldBlock,
    termToCheck,
    warningLabel: `Not offered in ${termLabel}`,
    detailsLabel: offeredTermsLabel,
    offeredTerms,
  };
}

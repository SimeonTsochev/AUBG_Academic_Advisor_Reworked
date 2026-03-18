import type { CourseCatalogRecord } from "../api";

type CourseAvailabilitySource = Pick<CourseCatalogRecord, "semester_availability"> | null | undefined;

export type CourseSelectionMode = "completed" | "in_progress" | "plan_add";

export interface CourseAvailabilityContext {
  mode: CourseSelectionMode;
  isExcelOnly?: boolean;
  currentTermLabel?: string | null;
  targetTermLabel?: string | null;
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

const extractSeason = (value: string): string | null => {
  const match = value.trim().match(/^(Spring|Fall)\s+\d{4}$/i);
  return match?.[1]?.toLowerCase() ?? null;
};

export function getCourseAvailabilityInfo(
  course: CourseAvailabilitySource,
  context: CourseAvailabilityContext
): CourseAvailabilityInfo {
  const { mode, isExcelOnly, currentTermLabel, targetTermLabel } = context;
  const offeredTerms = (course?.semester_availability ?? [])
    .filter((term): term is string => typeof term === "string" && term.trim().length > 0)
    .map((term) => term.trim());

  const computeUnavailable = (termToCheck: string | null) => {
    if (!termToCheck || offeredTerms.length === 0) return false;
    if (isExcelOnly === true) {
      const normalizedTarget = normalizeTermLabel(termToCheck);
      return !offeredTerms.some((term) => normalizeTermLabel(term) === normalizedTarget);
    }

    const targetSeason = extractSeason(termToCheck);
    if (!targetSeason) return false;

    return !offeredTerms.some((term) => {
      const offeredSeason = extractSeason(term);
      return offeredSeason ? offeredSeason === targetSeason : true;
    });
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
      detailsLabel: `Offered only in: ${offeredTerms.join(", ")}`,
      offeredTerms,
    };
  }

  const termToCheck =
    mode === "plan_add"
      ? targetTermLabel?.trim() || currentTermLabel?.trim() || null
      : currentTermLabel?.trim() || null;
  const isUnavailable = computeUnavailable(termToCheck);
  const shouldBlock = mode === "plan_add" && isUnavailable && isExcelOnly === true;

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
    detailsLabel: `Offered only in: ${offeredTerms.join(", ")}`,
    offeredTerms,
  };
}

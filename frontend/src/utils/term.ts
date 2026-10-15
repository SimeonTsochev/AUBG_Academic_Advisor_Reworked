export function termToNumber(term: string): number | null {
  const match = term.match(/^(Spring|Fall)\s+(\d{4})$/);
  if (!match) return null;
  const year = Number(match[2]);
  if (!Number.isFinite(year)) return null;
  const seasonValue = match[1] === "Spring" ? 1 : 2;
  return (year * 10) + seasonValue;
}

export function isEarlierTerm(a: string, b: string): boolean {
  const aValue = termToNumber(a);
  const bValue = termToNumber(b);
  if (aValue === null || bValue === null) return false;
  return aValue < bValue;
}

export function previousTermLabel(term: string): string | null {
  const match = term.match(/^(Spring|Fall)\s+(\d{4})$/);
  if (!match) return null;
  const season = match[1];
  const year = Number(match[2]);
  if (!Number.isFinite(year)) return null;
  if (season === 'Spring') {
    return `Fall ${year - 1}`;
  }
  return `Spring ${year}`;
}

/**
 * The start term a student's record proves, when it is earlier than the one they chose: a course
 * recorded in an earlier semester, or more completed credits than the semesters before the current one
 * could hold at `maxCreditsPerTerm`. Null when the chosen start fits (a student who is behind, or who
 * took fewer credits, started when they said they did).
 */
export function impliedEarlierStart(params: {
  chosenStart: string;
  currentTerm: string;
  completedCredits: number;
  recordedTerms: readonly string[];
  maxCreditsPerTerm: number;
}): { term: string; reason: "recorded" | "credits" } | null {
  const { chosenStart, currentTerm, completedCredits, recordedTerms, maxCreditsPerTerm } = params;
  const chosen = termToNumber(chosenStart);
  if (chosen === null) return null;
  let best: { term: string; reason: "recorded" | "credits" } | null = null;
  const consider = (term: string, reason: "recorded" | "credits") => {
    const value = termToNumber(term);
    if (value === null || value >= chosen) return;
    if (!best || value < (termToNumber(best.term) ?? Infinity)) best = { term, reason };
  };
  recordedTerms.forEach((term) => consider(term, "recorded"));
  const priorTermsNeeded = Math.ceil(Math.max(0, completedCredits) / Math.max(1, maxCreditsPerTerm));
  let start: string | null = currentTerm;
  for (let i = 0; i < priorTermsNeeded && start; i += 1) start = previousTermLabel(start);
  if (start && priorTermsNeeded > 0) consider(start, "credits");
  return best;
}

export interface CourseStatusRolloverInput {
  currentTermLabel: string;
  lastRolloverTermApplied?: string;
  completedCourses: string[];
  inProgressCourses: string[];
  completedOverrides: Record<string, string>;
  inProgressOverrides: Record<string, string>;
}

export interface CourseStatusRolloverResult {
  completedCourses: string[];
  inProgressCourses: string[];
  completedOverrides: Record<string, string>;
  inProgressOverrides: Record<string, string>;
  lastRolloverTermApplied?: string;
  changed: boolean;
}

// Dev note: manually verify same-term no-op, past-term promotion, future-term no-op,
// missing override safety, duplicate safety, and restoring a prior-term snapshot.
export function applyRolloverIfNeeded({
  currentTermLabel,
  lastRolloverTermApplied,
  completedCourses,
  inProgressCourses,
  completedOverrides,
  inProgressOverrides,
}: CourseStatusRolloverInput): CourseStatusRolloverResult {
  if (lastRolloverTermApplied === currentTermLabel) {
    return {
      completedCourses,
      inProgressCourses,
      completedOverrides,
      inProgressOverrides,
      lastRolloverTermApplied,
      changed: false,
    };
  }

  const completedSet = new Set(completedCourses);
  const inProgressSet = new Set(inProgressCourses);
  const nextCompletedOverrides = { ...completedOverrides };
  const nextInProgressOverrides = { ...inProgressOverrides };

  for (const courseCode of inProgressSet) {
    const inProgressTerm = nextInProgressOverrides[courseCode];
    if (!inProgressTerm) continue;
    if (!isEarlierTerm(inProgressTerm, currentTermLabel)) continue;

    inProgressSet.delete(courseCode);
    completedSet.add(courseCode);
    delete nextInProgressOverrides[courseCode];

    if (!nextCompletedOverrides[courseCode]) {
      nextCompletedOverrides[courseCode] = inProgressTerm;
    }
  }

  return {
    completedCourses: Array.from(completedSet),
    inProgressCourses: Array.from(inProgressSet),
    completedOverrides: nextCompletedOverrides,
    inProgressOverrides: nextInProgressOverrides,
    lastRolloverTermApplied: currentTermLabel,
    changed: true,
  };
}

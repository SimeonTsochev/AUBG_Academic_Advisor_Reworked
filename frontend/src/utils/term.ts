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

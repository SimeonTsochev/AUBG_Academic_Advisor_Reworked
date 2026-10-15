import type { PlanWarning } from "../api";

const text = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value.trim() : null;

const offeredIn = (warning: PlanWarning): string => {
  const terms = (warning.offered_terms ?? []).filter((term) => typeof term === "string" && term.trim());
  return terms.length > 0 ? `it is offered in ${terms.join(", ")}` : "it is not on that term's published schedule";
};

/**
 * One sentence for a change the student made that the planner did not apply as asked (backend
 * `OVERRIDE_*` warnings from `_apply_plan_overrides`), or null for warnings the plan already shows
 * elsewhere or that need no action (a removal whose course is gone anyway, a removal that followed
 * its course to another term).
 */
export function describeEditWarning(warning: PlanWarning): string | null {
  const course = text(warning.course) ?? "A course";
  const term = text(warning.term);
  const from = text(warning.from);
  const to = text(warning.to) ?? term;
  switch (warning.type) {
    case "OVERRIDE_ADD_TERM_UNAVAILABLE":
      return `${course} was not added to ${term ?? "that term"}: ${offeredIn(warning)}.`;
    case "OVERRIDE_MOVE_TERM_UNAVAILABLE":
      return `${course} was not moved to ${to ?? "that term"}: ${offeredIn(warning)}.`;
    case "OVERRIDE_ADD_ALREADY_COMPLETED":
      return `${course} was not added to ${term ?? "your plan"}: it is already completed. Add it as a retake to take it again.`;
    case "OVERRIDE_ADD_UNKNOWN":
      return `${course} was not added: it is not in the course catalog.`;
    case "OVERRIDE_CONFLICT":
      return `${course} was both added and removed in ${term ?? "your plan"}; the removal was kept.`;
    case "OVERRIDE_INVALID_TERM":
    case "OVERRIDE_TERM_BEFORE_START":
      return `${course} was not placed in ${to ?? "that term"}: the term is before your plan starts or not a semester.`;
    case "OVERRIDE_MOVE_NOT_FOUND":
    case "OVERRIDE_MOVE_TERM_NOT_FOUND":
      return `${course} was not moved: it is no longer in ${from ?? "that term"}.`;
    case "OVERRIDE_MOVE_INELIGIBLE":
      return `${course} was not moved to ${to ?? "that term"}: it would break a course sequence rule.`;
    case "OVERRIDE_COURSE_RELIEVED":
      return `${course} moved from ${from ?? "its semester"} to ${term ?? "a later semester"} to make room for your changes.`;
    default:
      return null;
  }
}

/** The distinct sentences for every edit the planner skipped or adjusted, in the plan's order. */
export function describeEditWarnings(warnings: readonly PlanWarning[] | null | undefined): string[] {
  const sentences: string[] = [];
  for (const warning of warnings ?? []) {
    const sentence = describeEditWarning(warning);
    if (sentence && !sentences.includes(sentence)) sentences.push(sentence);
  }
  return sentences;
}

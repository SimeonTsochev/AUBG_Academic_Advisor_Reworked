import type { PlanCourse } from "../api";

/**
 * One line explaining why a planned course is in the plan, built from the requirements the
 * backend says it fills, e.g. "Computer Science major: required course; Prerequisite for COS 3015".
 */
export function describeCourseReason(
  course: Pick<PlanCourse, "requirements" | "unlocks" | "satisfies">
): string | undefined {
  const parts = (course.requirements ?? []).map((requirement) => requirement.label).filter(Boolean);
  if (course.unlocks && course.unlocks.length > 0) {
    parts.push(`Prerequisite for ${course.unlocks.join(", ")}`);
  }
  if (parts.length > 0) return parts.join("; ");
  // Older responses (e.g. restored snapshots) only carry the coarse labels.
  return course.satisfies && course.satisfies.length > 0 ? course.satisfies.join("; ") : undefined;
}

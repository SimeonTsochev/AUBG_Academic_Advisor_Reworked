/*
 * Class standing by semester of study, counted from the student's start term:
 * semesters 1-2 freshman, 3-4 sophomore, 5-6 junior, 7-8 senior.
 */

export type Standing = "sophomore" | "junior" | "senior";

/** First semester (1-based) of each standing. */
export const STANDING_FIRST_SEMESTER: Record<Standing, number> = {
  sophomore: 3,
  junior: 5,
  senior: 7,
};

export interface StandingRequirement {
  /** Earliest semester (1-based) the course can be taken in; 1 means no restriction. */
  minSemester: number;
  /** Why, for messages ("junior standing", "junior standing (4000-level course)"); null when unrestricted. */
  reason: string | null;
}

/**
 * The standing a course needs, from its prerequisite text and course level. A declared major
 * counts as sophomore standing; 3000- and 4000-level courses need sophomore and junior standing.
 */
export function standingRequirement(code: string, prereqText: string | null | undefined): StandingRequirement {
  const text = (prereqText ?? "").toLowerCase();
  const rules: Array<[number, string]> = [];
  for (const standing of ["senior", "junior", "sophomore"] as Standing[]) {
    if (text.includes(`${standing} standing`)) rules.push([STANDING_FIRST_SEMESTER[standing], `${standing} standing`]);
  }
  if (text.includes("declared major")) rules.push([STANDING_FIRST_SEMESTER.sophomore, "sophomore standing (declared major)"]);
  const level = Number(code.match(/^[A-Z]{3}\s?(\d{3,4})$/)?.[1] ?? 0);
  if (level >= 4000) rules.push([STANDING_FIRST_SEMESTER.junior, "junior standing (4000-level course)"]);
  else if (level >= 3000) rules.push([STANDING_FIRST_SEMESTER.sophomore, "sophomore standing (3000-level course)"]);

  let best: StandingRequirement = { minSemester: 1, reason: null };
  for (const [minSemester, reason] of rules) {
    if (minSemester > best.minSemester) best = { minSemester, reason };
  }
  return best;
}

/** 1-based semester of study for a term, given term indexes (one per Spring/Fall). */
export function semesterOfStudy(termIdx: number, startTermIdx: number): number {
  return termIdx - startTermIdx + 1;
}

export function ordinal(n: number): string {
  const suffix = n % 10 === 1 && n % 100 !== 11 ? "st" : n % 10 === 2 && n % 100 !== 12 ? "nd" : n % 10 === 3 && n % 100 !== 13 ? "rd" : "th";
  return `${n}${suffix}`;
}

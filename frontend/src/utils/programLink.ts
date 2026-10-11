/** Programs named by a requirement-page link such as `/?major=Computer%20Science&minor=Finance`. */
export interface ProgramLink {
  majors: string[];
  minors: string[];
}

export const NO_PROGRAM_LINK: ProgramLink = { majors: [], minors: [] };

const MAX_PROGRAMS_PER_TYPE = 2;

function matchPrograms(requested: string[], available: string[]): string[] {
  const byKey = new Map(available.map((name) => [name.trim().toLowerCase(), name]));
  const matched: string[] = [];
  for (const raw of requested) {
    const name = byKey.get(raw.trim().toLowerCase());
    if (name && !matched.includes(name)) matched.push(name);
  }
  return matched.slice(0, MAX_PROGRAMS_PER_TYPE);
}

/**
 * Reads `major` / `minor` query parameters and keeps only names the catalog offers.
 * A program cannot be both: a minor that is also a selected major is dropped.
 */
export function readProgramLink(search: string, majors: string[], minors: string[]): ProgramLink {
  const params = new URLSearchParams(search);
  const linkedMajors = matchPrograms(params.getAll("major"), majors);
  const linkedMinors = matchPrograms(
    params.getAll("minor"),
    minors.filter((name) => !linkedMajors.includes(name)),
  );
  if (!linkedMajors.length && !linkedMinors.length) return NO_PROGRAM_LINK;
  return { majors: linkedMajors, minors: linkedMinors };
}

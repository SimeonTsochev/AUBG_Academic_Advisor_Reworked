import type { TranscriptDeclaredPrograms } from "../api";

export type ProgramSelection = { majors: string[]; minors: string[] };

/**
 * Adds the programs a transcript lists as declared to the student's selection. Only programs the
 * catalog offers are taken, at most `maxPerType` of each kind, and a declared major replaces the same
 * program chosen as a minor. Returns null when the transcript adds nothing.
 */
export function mergeDeclaredPrograms(
  current: ProgramSelection,
  declared: TranscriptDeclaredPrograms | null | undefined,
  available: ProgramSelection,
  maxPerType: number,
): ProgramSelection | null {
  const declaredMajors = (declared?.majors ?? []).filter((name) => available.majors.includes(name));
  const declaredMinors = (declared?.minors ?? []).filter((name) => available.minors.includes(name));
  if (declaredMajors.length === 0 && declaredMinors.length === 0) return null;

  const majors = [...current.majors];
  for (const name of declaredMajors) {
    if (!majors.includes(name) && majors.length < maxPerType) majors.push(name);
  }
  const minors = current.minors.filter((name) => !majors.includes(name));
  for (const name of declaredMinors) {
    if (!majors.includes(name) && !minors.includes(name) && minors.length < maxPerType) minors.push(name);
  }

  const same = (a: string[], b: string[]) => a.length === b.length && a.every((name, i) => name === b[i]);
  if (same(majors, current.majors) && same(minors, current.minors)) return null;
  return { majors, minors };
}

/** "Major: Computer Science · Minor: Economics", for the note that says what the transcript filled in. */
export function describeDeclaredPrograms(declared: TranscriptDeclaredPrograms): string {
  const part = (label: string, names: string[]) =>
    names.length === 0 ? null : `${label}${names.length > 1 ? "s" : ""}: ${names.join(", ")}`;
  return [part("Major", declared.majors), part("Minor", declared.minors)].filter(Boolean).join(" · ");
}

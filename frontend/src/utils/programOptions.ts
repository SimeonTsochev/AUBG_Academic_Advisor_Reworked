import type { PlacementWaiver, ProgramInfo, ProgramOptionSelection } from '../api';

/**
 * Per selected program, the info that applies to it: majors read `program_info`, minors `minor_info`.
 * A student never has the same program as both, so one name-keyed map is unambiguous.
 */
export function selectedProgramInfo(
  majors: string[],
  minors: string[],
  majorInfo: Record<string, ProgramInfo> = {},
  minorInfo: Record<string, ProgramInfo> = {},
): Record<string, ProgramInfo> {
  const info: Record<string, ProgramInfo> = {};
  for (const minor of minors) if (minorInfo[minor]) info[minor] = minorInfo[minor];
  for (const major of majors) if (majorInfo[major]) info[major] = majorInfo[major];
  return info;
}

/**
 * The chosen options that apply to `programs`: programs without options, choices the program does
 * not offer and duplicates are dropped, and a single-choice option keeps only its first choice.
 */
export function normalizeProgramOptions(
  selection: unknown,
  programs: string[],
  info: Record<string, ProgramInfo>,
): ProgramOptionSelection {
  const raw = selection && typeof selection === 'object' && !Array.isArray(selection)
    ? (selection as Record<string, unknown>)
    : {};
  const result: ProgramOptionSelection = {};
  for (const program of programs) {
    const options = info[program]?.options;
    const chosen = raw[program];
    if (!options || !Array.isArray(chosen)) continue;
    const valid = Array.from(new Set(
      chosen.filter((c): c is string => typeof c === 'string' && options.choices.includes(c)),
    ));
    if (valid.length > 0) result[program] = options.multiple ? valid : valid.slice(0, 1);
  }
  return result;
}

/** Selected programs whose required option (the European Studies language, an MLC focus) has no choice yet. */
export function majorsMissingRequiredOption(
  programs: string[],
  info: Record<string, ProgramInfo>,
  selection: ProgramOptionSelection,
): string[] {
  return programs.filter((program) => info[program]?.options?.required && !(selection[program]?.length));
}

/** The selection after the student toggles `choice` for `program`. */
export function toggleProgramOption(
  selection: ProgramOptionSelection,
  program: string,
  choice: string,
  multiple: boolean,
): ProgramOptionSelection {
  const current = selection[program] ?? [];
  let next: string[];
  if (!multiple) next = [choice];
  else next = current.includes(choice) ? current.filter((c) => c !== choice) : [...current, choice];
  const result = { ...selection };
  if (next.length > 0) result[program] = next;
  else delete result[program];
  return result;
}

/** Placement tests the selected programs offer, one per course (the CS major and minor share COS 1020). */
export function offeredPlacementWaivers(programs: string[], info: Record<string, ProgramInfo>): PlacementWaiver[] {
  const byCourse = new Map<string, PlacementWaiver>();
  for (const program of programs) {
    for (const waiver of info[program]?.placement_waivers ?? []) {
      if (!byCourse.has(waiver.course)) byCourse.set(waiver.course, waiver);
    }
  }
  return Array.from(byCourse.values());
}

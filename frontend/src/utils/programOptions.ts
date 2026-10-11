import type { ProgramInfo, ProgramOptionSelection } from '../api';

/**
 * The chosen options that apply to `majors`: majors without options, choices the major does not
 * offer and duplicates are dropped, and a single-choice option keeps only its first choice.
 */
export function normalizeProgramOptions(
  selection: unknown,
  majors: string[],
  info: Record<string, ProgramInfo>,
): ProgramOptionSelection {
  const raw = selection && typeof selection === 'object' && !Array.isArray(selection)
    ? (selection as Record<string, unknown>)
    : {};
  const result: ProgramOptionSelection = {};
  for (const major of majors) {
    const options = info[major]?.options;
    const chosen = raw[major];
    if (!options || !Array.isArray(chosen)) continue;
    const valid = Array.from(new Set(
      chosen.filter((c): c is string => typeof c === 'string' && options.choices.includes(c)),
    ));
    if (valid.length > 0) result[major] = options.multiple ? valid : valid.slice(0, 1);
  }
  return result;
}

/** Selected majors whose required option (e.g. the European Studies language) has no choice yet. */
export function majorsMissingRequiredOption(
  majors: string[],
  info: Record<string, ProgramInfo>,
  selection: ProgramOptionSelection,
): string[] {
  return majors.filter((major) => info[major]?.options?.required && !(selection[major]?.length));
}

/** The selection after the student toggles `choice` for `major`. */
export function toggleProgramOption(
  selection: ProgramOptionSelection,
  major: string,
  choice: string,
  multiple: boolean,
): ProgramOptionSelection {
  const current = selection[major] ?? [];
  let next: string[];
  if (!multiple) next = [choice];
  else next = current.includes(choice) ? current.filter((c) => c !== choice) : [...current, choice];
  const result = { ...selection };
  if (next.length > 0) result[major] = next;
  else delete result[major];
  return result;
}

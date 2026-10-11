import { useMemo, useState } from 'react';
import type { ProgramInfo, ProgramOptionSelection } from '../api';
import { majorsMissingRequiredOption, normalizeProgramOptions, selectedProgramInfo } from '../utils/programOptions';

/**
 * The selected programs' options and placement tests (majors read `program_info`, minors
 * `minor_info`) and the student's choices. The choices are editable on the advisor screen, so a plan
 * saved without a required option (the European Studies language) can add it without redoing setup,
 * which would start a new plan.
 */
export function useProgramOptions(
  selection: { majors: string[]; minors: string[]; programOptions?: ProgramOptionSelection },
  majorInfo: Record<string, ProgramInfo> | undefined,
  minorInfo: Record<string, ProgramInfo> | undefined,
) {
  const { majors, minors } = selection;
  const optionInfo = useMemo(
    () => selectedProgramInfo(majors, minors, majorInfo, minorInfo),
    [majors, minors, majorInfo, minorInfo],
  );
  const selectedPrograms = useMemo(() => [...majors, ...minors], [majors, minors]);
  const [programOptions, setProgramOptions] = useState<ProgramOptionSelection>(
    () => normalizeProgramOptions(selection.programOptions, selectedPrograms, optionInfo),
  );
  const programsNeedingOption = majorsMissingRequiredOption(selectedPrograms, optionInfo, programOptions);
  const chooseOption = (program: string, choice: string) =>
    setProgramOptions((prev) => ({ ...prev, [program]: [choice] }));

  return { optionInfo, selectedPrograms, programOptions, programsNeedingOption, chooseOption };
}

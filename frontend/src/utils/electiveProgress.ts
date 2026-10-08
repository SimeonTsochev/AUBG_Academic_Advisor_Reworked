import type { ElectiveProgress } from '../api';
import type { ElectivePlaceholder } from '../types';

/** Excel area-of-study tag prefixes per program; mirrors backend excel_catalog.PROGRAM_TAG_ALIASES. */
const PROGRAM_TAG_ALIASES: Record<string, string[]> = {
  'Business Administration': ['BUS'],
  'Computer Science': ['COS', 'CS'],
  'Economics': ['ECO'],
  'European Studies': ['EUR'],
  'Finance': ['FIN'],
  'History and Civilizations': ['HC', 'HTY'],
  'Information Systems': ['IS', 'ISM'],
  'Journalism and Mass Communication': ['JMC'],
  'Literature': ['LIT', 'ENG'],
  'Mathematics': ['MAT'],
  'Modern Languages and Cultures': ['MLC'],
  'Physics': ['PHY'],
  'Political Science and International Relations': ['POS'],
  'Psychology': ['PSY'],
  'Film and Creative Media': ['Film', 'FIL'],
  'Sustainability Studies': ['Sustainability', 'Sustainabiliy'],
};

export interface ElectiveRequirementSummary {
  key: string;
  program: string;
  programType: 'major' | 'minor';
  /** "Major: Economics" */
  label: string;
  required: number;
  counted: number;
  remaining: number;
  unit: 'credits' | 'courses';
  isComplete: boolean;
  /** Courses already counting toward this requirement, completed first. */
  courses: ElectiveProgress['courses'];
  /** Courses the catalog lists by name (rule-based electives such as "any ECO course" are not listed). */
  allowedCourses: string[];
  ruleText: string;
  /** Lower-case tag prefixes used to match elective recommendations ("eco"). */
  tagPrefixes: string[];
  /** "ECO Minor Elective" */
  displayTag: string;
}

const normalizeCode = (value: string) => value.replace(/\s+/g, ' ').trim().toUpperCase();

/**
 * The backend decides which courses count (elective_progress); placeholders only add the catalog's
 * listed courses and rule text for display.
 */
export function summarizeElectiveRequirements(
  progress: ElectiveProgress[],
  placeholders: ElectivePlaceholder[]
): ElectiveRequirementSummary[] {
  return progress
    .map((entry) => {
      const blocks = placeholders.filter(
        (block) => block.program === entry.program && block.program_type === entry.program_type
      );
      const allowedCourses = Array.from(
        new Set(blocks.flatMap((block) => (block.allowed_courses ?? []).map(normalizeCode)).filter(Boolean))
      );
      const aliases = PROGRAM_TAG_ALIASES[entry.program] ?? [];
      const listedPrefixes = allowedCourses.map((code) => code.split(' ')[0] ?? '');
      const tagPrefixes = Array.from(
        new Set([...aliases, ...listedPrefixes].map((prefix) => prefix.trim().toLowerCase()).filter(Boolean))
      );
      const primaryPrefix = aliases[0] ?? listedPrefixes[0] ?? entry.program;
      const kind = entry.program_type === 'major' ? 'Major' : 'Minor';
      const required = entry.unit === 'credits' ? entry.credits_required ?? 0 : entry.courses_required ?? 0;
      return {
        key: `${entry.program_type}:${entry.program}`,
        program: entry.program,
        programType: entry.program_type,
        label: `${kind}: ${entry.program}`,
        required,
        counted: required - entry.remaining,
        remaining: entry.remaining,
        unit: entry.unit,
        isComplete: entry.remaining === 0,
        courses: [...entry.courses].sort((a, b) => Number(b.completed) - Number(a.completed)),
        allowedCourses,
        ruleText: entry.rule_text,
        tagPrefixes,
        displayTag: `${primaryPrefix} ${kind} Elective`,
      };
    })
    .sort((a, b) =>
      a.programType !== b.programType ? (a.programType === 'major' ? -1 : 1) : a.label.localeCompare(b.label)
    );
}

/** "3 credits left", "1 course left" or "Completed". */
export function describeElectiveRemaining(summary: Pick<ElectiveRequirementSummary, 'remaining' | 'unit'>): string {
  if (summary.remaining <= 0) return 'Completed';
  const noun = summary.unit === 'credits' ? 'credit' : 'course';
  return `${summary.remaining} ${noun}${summary.remaining === 1 ? '' : 's'} left`;
}

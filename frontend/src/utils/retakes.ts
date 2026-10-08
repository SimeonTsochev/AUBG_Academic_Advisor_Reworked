import { termToNumber } from './term';

export type CourseAttemptLike = {
  instance_id?: string;
  code: string;
  term: string;
  status?: 'PLANNED' | 'IN_PROGRESS' | 'COMPLETED';
  is_retake?: boolean;
  credits?: number;
};

export type ActiveAttemptResolution = {
  activeInstanceIds: Set<string>;
  replacedInstanceIds: Set<string>;
};

const normalizeCode = (value: string) => value.replace(/\s+/g, ' ').trim().toUpperCase();

const statusRank = (value?: CourseAttemptLike['status']) => {
  switch ((value ?? 'PLANNED').toUpperCase()) {
    case 'COMPLETED':
      return 2;
    case 'IN_PROGRESS':
      return 1;
    default:
      return 0;
  }
};

const attemptId = (attempt: CourseAttemptLike, index: number) =>
  typeof attempt.instance_id === 'string' && attempt.instance_id.trim().length > 0
    ? attempt.instance_id.trim()
    : `idx:${index}`;

export function resolveActiveAttempts(attempts: CourseAttemptLike[]): ActiveAttemptResolution {
  const grouped = new Map<string, Array<CourseAttemptLike & { __index: number; __id: string }>>();

  attempts.forEach((attempt, index) => {
    if (!attempt || typeof attempt.code !== 'string') return;
    const code = normalizeCode(attempt.code);
    if (!code) return;
    const withMeta = {
      ...attempt,
      __index: index,
      __id: attemptId(attempt, index),
    };
    if (!grouped.has(code)) grouped.set(code, []);
    grouped.get(code)!.push(withMeta);
  });

  const activeInstanceIds = new Set<string>();
  const replacedInstanceIds = new Set<string>();

  for (const group of grouped.values()) {
    if (group.length === 0) continue;
    const ordered = [...group].sort((a, b) => {
      const aTerm = termToNumber(a.term) ?? -1;
      const bTerm = termToNumber(b.term) ?? -1;
      if (aTerm !== bTerm) return aTerm - bTerm;
      const aStatus = statusRank(a.status);
      const bStatus = statusRank(b.status);
      if (aStatus !== bStatus) return aStatus - bStatus;
      return a.__index - b.__index;
    });
    const active = ordered[ordered.length - 1];
    activeInstanceIds.add(active.__id);
    for (let i = 0; i < ordered.length - 1; i += 1) {
      replacedInstanceIds.add(ordered[i].__id);
    }
  }

  return { activeInstanceIds, replacedInstanceIds };
}

export type FailedAttempt = { code: string; grade: string | null; term: string | null };

/** Snapshot data is untrusted JSON: keep only well-formed failed attempts, keyed by normalized code. */
export function normalizeFailedCourses(value: unknown): FailedAttempt[] {
  if (!Array.isArray(value)) return [];
  const byCode = new Map<string, FailedAttempt>();
  for (const raw of value) {
    if (!raw || typeof raw !== 'object') continue;
    const entry = raw as Record<string, unknown>;
    const code = typeof entry.code === 'string' ? normalizeCode(entry.code) : '';
    if (!code) continue;
    byCode.set(code, {
      code,
      grade: typeof entry.grade === 'string' && entry.grade.trim() ? entry.grade.trim().toUpperCase() : null,
      term: typeof entry.term === 'string' && entry.term.trim() ? entry.term.trim() : null,
    });
  }
  return Array.from(byCode.values());
}

/** "Retake: not passed in Fall 2025 (grade F)." for a course the plan schedules again. */
export function describeFailedAttempt(attempt: FailedAttempt): string {
  const when = attempt.term ? ` in ${attempt.term}` : '';
  const grade = attempt.grade ? ` (grade ${attempt.grade})` : '';
  return `Retake: not passed${when}${grade}.`;
}

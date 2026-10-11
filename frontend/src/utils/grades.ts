import type { GradeEntry } from '../api';

/**
 * Transcript grades, per course code. They are private: kept in this browser's localStorage under
 * the plan's share token and sent with plan requests for GPA, but never put in a snapshot payload,
 * so a shared /p/<token> link never reveals them.
 */
export interface GradeRecord {
  grade: string;
  term?: string | null;
}
export type GradeMap = Record<string, GradeRecord>;

const STORAGE_KEY = 'aubg-advisor:grades';
// Each edit saves the plan under a new token; keep only the most recent plans' grades.
const MAX_STORED_PLANS = 20;

type StoredGrades = Record<string, { savedAt: number; grades: GradeMap }>;

/** Storage that may be missing or throw (private mode, blocked site data). */
export type GradeStorage = Pick<Storage, 'getItem' | 'setItem'>;

function defaultStorage(): GradeStorage | null {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

function readAll(storage: GradeStorage | null): StoredGrades {
  try {
    const parsed: unknown = JSON.parse(storage?.getItem(STORAGE_KEY) ?? '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as StoredGrades) : {};
  } catch {
    return {};
  }
}

function writeAll(storage: GradeStorage | null, all: StoredGrades): void {
  const newest = Object.entries(all)
    .sort(([, a], [, b]) => (b.savedAt ?? 0) - (a.savedAt ?? 0))
    .slice(0, MAX_STORED_PLANS);
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(newest)));
  } catch {
    // Quota or blocked storage: grades then last only for this visit.
  }
}

/** Only well-formed entries: a non-empty grade, an optional term. */
export function normalizeGrades(value: unknown): GradeMap {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const out: GradeMap = {};
  for (const [code, entry] of Object.entries(value as Record<string, unknown>)) {
    if (!entry || typeof entry !== 'object') continue;
    const { grade, term } = entry as Record<string, unknown>;
    if (typeof grade !== 'string' || !grade.trim()) continue;
    out[code] = { grade: grade.trim().toUpperCase(), term: typeof term === 'string' ? term : null };
  }
  return out;
}

export function loadGrades(token: string | null, storage: GradeStorage | null = defaultStorage()): GradeMap {
  if (!token) return {};
  return normalizeGrades(readAll(storage)[token]?.grades);
}

/** Store `grades` under `token`, dropping the copy kept under the plan's previous token. */
export function saveGrades(
  token: string,
  grades: GradeMap,
  previousToken: string | null = null,
  storage: GradeStorage | null = defaultStorage(),
  now: number = Date.now(),
): void {
  const all = readAll(storage);
  if (previousToken && previousToken !== token) delete all[previousToken];
  if (Object.keys(grades).length > 0) all[token] = { savedAt: now, grades };
  else delete all[token];
  writeAll(storage, all);
}

/** Grades of the courses a transcript import marked completed or failed (in-progress has none yet). */
export function gradesFromTranscript(
  entries: { matchedCode: string | null; status: string; grade: string | null; term: string | null }[],
  normalizeCode: (code: string) => string,
): GradeMap {
  const out: GradeMap = {};
  for (const entry of entries) {
    if (!entry.matchedCode || !entry.grade || entry.status === 'in_progress') continue;
    out[normalizeCode(entry.matchedCode)] = { grade: entry.grade.trim().toUpperCase(), term: entry.term };
  }
  return out;
}

export function toGradeEntries(grades: GradeMap): GradeEntry[] {
  return Object.entries(grades).map(([code, { grade, term }]) => ({ code, grade, term: term ?? null }));
}

/** "3.571" with the catalog's three decimals, or a dash. */
export function formatGpa(gpa: number | null | undefined): string {
  return typeof gpa === 'number' ? gpa.toFixed(3) : '–';
}

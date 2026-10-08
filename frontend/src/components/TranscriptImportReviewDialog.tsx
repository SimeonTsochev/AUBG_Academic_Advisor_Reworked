import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  searchCourses,
  type SearchCoursesContext,
  type TranscriptImportCourse,
  type TranscriptImportMatchCandidate,
} from '../api';

export type TranscriptCourseStatus = TranscriptImportCourse['status'];

const STATUS_LABELS: Record<TranscriptCourseStatus, string> = {
  completed: 'Completed',
  in_progress: 'In Progress',
  failed: 'Not passed (retake)',
};

export interface TranscriptImportReviewEntry {
  reviewId: string;
  rawCode: string;
  matchedCode: string | null;
  title: string | null;
  rawTitle: string | null;
  status: TranscriptCourseStatus;
  grade: string | null;
  term: string | null;
  confidence: number;
  matchedConfidently: boolean;
  matchCandidates: TranscriptImportMatchCandidate[];
}

interface TranscriptImportReviewDialogProps {
  open: boolean;
  entries: TranscriptImportReviewEntry[];
  warnings: string[];
  searchContext: SearchCoursesContext;
  onCancel: () => void;
  onConfirm: () => void;
  onRemove: (reviewId: string) => void;
  onUpdateStatus: (reviewId: string, nextStatus: TranscriptCourseStatus) => void;
  onUpdateMatch: (
    reviewId: string,
    nextMatch: {
      code: string;
      title: string;
      confidence: number;
      matchedConfidently: boolean;
      matchCandidates?: TranscriptImportMatchCandidate[];
    } | null
  ) => void;
}

interface TranscriptMatchSelectorProps {
  entry: TranscriptImportReviewEntry;
  searchContext: SearchCoursesContext;
  onUpdateMatch: TranscriptImportReviewDialogProps['onUpdateMatch'];
}

function TranscriptMatchSelector({
  entry,
  searchContext,
  onUpdateMatch,
}: TranscriptMatchSelectorProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Array<{ code: string; title: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(async () => {
      try {
        const response = await searchCourses(query, undefined, 8, searchContext);
        if (cancelled) return;
        setResults(
          response.map((course) => ({
            code: course.code,
            title: course.title,
          }))
        );
      } catch (searchError: any) {
        if (cancelled) return;
        setError(searchError?.message ?? 'Catalog search failed.');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, searchContext]);

  const selectOptions = useMemo(() => {
    const options = new Map<string, { code: string; title: string; confidence: number }>();
    if (entry.matchedCode) {
      options.set(entry.matchedCode, {
        code: entry.matchedCode,
        title: entry.title ?? entry.rawTitle ?? entry.matchedCode,
        confidence: entry.confidence,
      });
    }
    entry.matchCandidates.forEach((candidate) => {
      options.set(candidate.code, {
        code: candidate.code,
        title: candidate.title,
        confidence: candidate.confidence,
      });
    });
    results.forEach((result) => {
      options.set(result.code, {
        code: result.code,
        title: result.title,
        confidence: 1,
      });
    });
    return Array.from(options.values()).sort((left, right) => left.code.localeCompare(right.code));
  }, [entry.confidence, entry.matchCandidates, entry.matchedCode, entry.rawTitle, entry.title, results]);

  return (
    <div className="mt-3 grid gap-2">
      <label className="text-xs font-medium" style={{ color: 'var(--neutral-dark)' }}>
        Catalog match
      </label>
      <select
        value={entry.matchedCode ?? ''}
        onChange={(event) => {
          const nextCode = event.target.value;
          if (!nextCode) {
            onUpdateMatch(entry.reviewId, null);
            return;
          }
          const selected = selectOptions.find((option) => option.code === nextCode);
          if (!selected) return;
          onUpdateMatch(entry.reviewId, {
            code: selected.code,
            title: selected.title,
            confidence: selected.confidence,
            matchedConfidently: true,
            matchCandidates: entry.matchCandidates,
          });
        }}
        className="w-full px-3 py-2 rounded-lg border text-sm"
        style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
      >
        <option value="">Needs review</option>
        {selectOptions.map((option) => (
          <option key={option.code} value={option.code}>
            {option.code} - {option.title}
          </option>
        ))}
      </select>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search catalog to change match"
        className="w-full px-3 py-2 rounded-lg border text-sm"
        style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
      />
      {loading && (
        <div className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
          Searching catalog...
        </div>
      )}
      {!loading && error && (
        <div className="text-xs" style={{ color: '#b45309' }}>
          {error}
        </div>
      )}
    </div>
  );
}

function TranscriptReviewSection({
  title,
  description,
  entries,
  searchContext,
  onRemove,
  onUpdateStatus,
  onUpdateMatch,
}: {
  title: string;
  description?: string;
  entries: TranscriptImportReviewEntry[];
  searchContext: SearchCoursesContext;
  onRemove: (reviewId: string) => void;
  onUpdateStatus: TranscriptImportReviewDialogProps['onUpdateStatus'];
  onUpdateMatch: TranscriptImportReviewDialogProps['onUpdateMatch'];
}) {
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between gap-3">
        <h4>{title}</h4>
        <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
          {entries.length} detected
        </div>
      </div>
      {description && (
        <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>{description}</p>
      )}
      {entries.length === 0 && (
        <div
          className="px-4 py-3 rounded-xl border text-sm"
          style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-cream)', color: 'var(--neutral-dark)' }}
        >
          No courses detected in this section.
        </div>
      )}
      {entries.map((entry) => {
        const statusLabel = STATUS_LABELS[entry.status];
        const titleText = entry.title ?? entry.rawTitle ?? entry.matchedCode ?? entry.rawCode;
        const needsReview = !entry.matchedCode;
        const matchLabel = needsReview
          ? 'Needs catalog match'
          : entry.matchedConfidently
            ? 'Matched confidently'
            : 'Review suggested match';
        const matchColor = needsReview
          ? { borderColor: '#f59e0b', background: '#fffbeb', color: '#92400e' }
          : entry.matchedConfidently
            ? { borderColor: '#86efac', background: '#f0fdf4', color: '#166534' }
            : { borderColor: '#fde68a', background: '#fffbeb', color: '#92400e' };

        return (
          <div
            key={entry.reviewId}
            className="p-4 rounded-xl border"
            style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="grid gap-2">
                <div className="font-medium">
                  {entry.matchedCode ?? entry.rawCode}
                  {entry.matchedCode && entry.matchedCode !== entry.rawCode ? ` (from ${entry.rawCode})` : ''}
                </div>
                <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                  {titleText}
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <span
                    className="px-2 py-1 rounded-full border"
                    style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-cream)', color: 'var(--navy-dark)' }}
                  >
                    {statusLabel}
                  </span>
                  {entry.grade && (
                    <span className={`badge ${entry.status === 'failed' ? 'badge-danger' : 'badge-neutral'}`}>
                      Grade {entry.grade}
                    </span>
                  )}
                  {entry.term && (
                    <span
                      className="px-2 py-1 rounded-full border"
                      style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)', color: 'var(--neutral-dark)' }}
                    >
                      {entry.term}
                    </span>
                  )}
                  <span className="px-2 py-1 rounded-full border" style={matchColor}>
                    {matchLabel}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onRemove(entry.reviewId)}
                className="px-3 py-2 rounded-lg text-sm border"
                style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)', color: 'var(--neutral-dark)' }}
              >
                Remove
              </button>
            </div>
            <div className="mt-3 grid gap-2">
              <label className="text-xs font-medium" style={{ color: 'var(--neutral-dark)' }}>
                Detected status
              </label>
              <select
                value={entry.status}
                onChange={(event) => onUpdateStatus(entry.reviewId, event.target.value as TranscriptCourseStatus)}
                className="w-full px-3 py-2 rounded-lg border text-sm"
                style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
              >
                {(Object.keys(STATUS_LABELS) as TranscriptCourseStatus[]).map((status) => (
                  <option key={status} value={status}>{STATUS_LABELS[status]}</option>
                ))}
              </select>
              <div className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
                Change this if the transcript parser picked the wrong status.
              </div>
            </div>
            {(!entry.matchedConfidently || !entry.matchedCode) && (
              <TranscriptMatchSelector
                entry={entry}
                searchContext={searchContext}
                onUpdateMatch={onUpdateMatch}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function TranscriptImportReviewDialog({
  open,
  entries,
  warnings,
  searchContext,
  onCancel,
  onConfirm,
  onRemove,
  onUpdateStatus,
  onUpdateMatch,
}: TranscriptImportReviewDialogProps) {
  const completedEntries = useMemo(
    () => entries.filter((entry) => entry.status === 'completed'),
    [entries]
  );
  const inProgressEntries = useMemo(
    () => entries.filter((entry) => entry.status === 'in_progress'),
    [entries]
  );
  const failedEntries = useMemo(
    () => entries.filter((entry) => entry.status === 'failed'),
    [entries]
  );
  const unresolvedCount = entries.filter((entry) => !entry.matchedCode).length;

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel();
      }
    };
    window.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleEscape);
    };
  }, [onCancel, open]);

  if (!open || typeof document === 'undefined') {
    return null;
  }

  return createPortal(
    <div
      onClick={onCancel}
      role="presentation"
      className="modal-overlay"
    >
      <div
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="transcript-import-title"
        className="modal"
        style={{ width: 'min(100%, 56rem)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
      >
        <div
          className="flex items-start justify-between gap-4"
          style={{
            borderBottom: '1px solid var(--neutral-border)',
            padding: '1.25rem 1.5rem',
          }}
        >
          <div className="grid gap-2">
            <h3 id="transcript-import-title">Review Transcript Import</h3>
            <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
              Confirm the detected completed and in-progress courses before they are merged into your setup.
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="btn btn-outline btn-sm"
          >
            Close
          </button>
        </div>

        <div
          className="grid gap-6"
          style={{
            overflowY: 'auto',
            padding: '1.25rem 1.5rem',
          }}
        >
          {warnings.length > 0 && (
            <div className="grid gap-2">
              {warnings.map((warning) => (
                <div
                  key={warning}
                  className="px-4 py-3 rounded-xl border text-sm"
                  style={{ borderColor: '#fde68a', background: '#fffbeb', color: '#92400e' }}
                >
                  {warning}
                </div>
              ))}
            </div>
          )}

          {unresolvedCount > 0 && (
            <div
              className="px-4 py-3 rounded-xl border text-sm"
              style={{ borderColor: '#f59e0b', background: '#fffbeb', color: '#92400e' }}
            >
              {unresolvedCount} course{unresolvedCount === 1 ? '' : 's'} still need a catalog match or should be removed.
            </div>
          )}

          <TranscriptReviewSection
            title="Detected Completed Courses"
            entries={completedEntries}
            searchContext={searchContext}
            onRemove={onRemove}
            onUpdateStatus={onUpdateStatus}
            onUpdateMatch={onUpdateMatch}
          />

          <TranscriptReviewSection
            title="Detected In-Progress Courses"
            entries={inProgressEntries}
            searchContext={searchContext}
            onRemove={onRemove}
            onUpdateStatus={onUpdateStatus}
            onUpdateMatch={onUpdateMatch}
          />

          {failedEntries.length > 0 && (
            <TranscriptReviewSection
              title="Not Passed: Retaken If Required"
              description="These grades (F, W, WF, U, NP, NR, I) earn no credit. They are not counted as completed, so your plan schedules the course again when a requirement still needs it."
              entries={failedEntries}
              searchContext={searchContext}
              onRemove={onRemove}
              onUpdateStatus={onUpdateStatus}
              onUpdateMatch={onUpdateMatch}
            />
          )}
        </div>

        <div
          className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"
          style={{
            borderTop: '1px solid var(--neutral-border)',
            padding: '1rem 1.5rem',
          }}
        >
          <button
            type="button"
            onClick={onCancel}
            className="btn btn-outline"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={entries.length === 0 || unresolvedCount > 0}
            className="btn btn-primary"
          >
            Import Courses
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

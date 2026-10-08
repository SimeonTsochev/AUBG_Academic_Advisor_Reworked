import { useEffect, useMemo, useState } from 'react';
import { Course } from '../types';
import { ArrowLeftRight, CheckCircle2, Circle, Clock, History, Info, Plus, RefreshCcw, Search, Trash2, X } from 'lucide-react';
import { searchCourses, type CourseCatalogRecord } from '../api';
import { getCourseAvailabilityInfo } from '../utils/courseAvailability';

interface SemesterPlanViewProps {
  courses: Course[];
  catalogId?: string;
  catalogCourses?: Record<string, string>;
  selectedMajors?: string[];
  selectedMinors?: string[];
  businessConcentration?: string | null;
  startTermSeason?: string;
  startTermYear?: number;
  totalTerms?: number;
  scheduleTerms?: string[];
  /** Instance ids of electives the student chose for a FREE ELECTIVE slot (they can be swapped). */
  swappableElectiveIds?: ReadonlySet<string>;
  onSwapElective?: (instanceId: string) => void;
  onToggleCompleted?: (instanceId: string) => void;
  onToggleInProgress?: (instanceId: string) => void;
  onRemoveCourse?: (instanceId: string) => void;
  onMoveCourse?: (instanceId: string) => void;
  movingCourseInstanceId?: string | null;
  onAddCourse?: (code: string) => void;
  onAddRetakeCourse?: (code: string) => void;
  onMoveCompleted?: (instanceId: string, term: string) => void;
  onChangeGenEd?: (instanceId: string, term: string) => void;
  onAddTransferCredit?: () => void;
  onRemoveTransferCredit?: (instanceId: string) => void;
}

const TAG_BADGES: Record<string, { label: string; className: string }> = {
  PROGRAM: { label: 'Program', className: 'badge-navy' },
  'GEN ED': { label: 'GenEd', className: 'badge-gold' },
  'Writing Intensive Course': { label: 'Writing intensive', className: 'badge-info' },
  'FREE ELECTIVE': { label: 'Free elective', className: 'badge-neutral' },
  FOUNDATION: { label: 'Foundation', className: 'badge-neutral' },
  Completed: { label: 'Completed', className: 'badge-success' },
  'In Progress': { label: 'In progress', className: 'badge-info' },
  'TRANSFER CREDIT': { label: 'Transfer credit', className: 'badge-navy' },
  Retake: { label: 'Retake', className: 'badge-warning' },
  'Previous Attempt': { label: 'Previous attempt', className: 'badge-danger' },
};
// "Planned" is every remaining course; the status icon already says so.
const HIDDEN_TAGS = new Set(['Planned']);
const TERM_STATUS_BADGE: Record<string, string> = {
  Completed: 'badge-success',
  'In Progress': 'badge-info',
  Planned: 'badge-neutral',
};

interface GroupedCourses {
  [semester: string]: Course[];
}

export function SemesterPlanView({
  courses,
  catalogId,
  catalogCourses,
  selectedMajors,
  selectedMinors,
  businessConcentration,
  startTermSeason,
  startTermYear,
  totalTerms = 8,
  scheduleTerms,
  swappableElectiveIds,
  onSwapElective,
  onToggleCompleted,
  onToggleInProgress,
  onRemoveCourse,
  onMoveCourse,
  movingCourseInstanceId,
  onAddCourse,
  onAddRetakeCourse,
  onMoveCompleted,
  onChangeGenEd,
  onAddTransferCredit,
  onRemoveTransferCredit
}: SemesterPlanViewProps) {
  const [hoveredCourse, setHoveredCourse] = useState<string | null>(null);
  const [showEmptyPastTerms, setShowEmptyPastTerms] = useState(false);
  const [query, setQuery] = useState('');
  const [catalogResults, setCatalogResults] = useState<CourseCatalogRecord[]>([]);
  const [catalogSearchLoading, setCatalogSearchLoading] = useState(false);
  const [catalogSearchError, setCatalogSearchError] = useState<string | null>(null);
  const currentTermLabel = useMemo(() => {
    const now = new Date();
    const season = now.getMonth() + 1 <= 5 ? "Spring" : "Fall";
    const year = now.getFullYear();
    return `${season} ${year}`;
  }, []);

  const normalizedCourses = useMemo(() => {
    return courses.map((course) =>
      course.semester === 'In Progress' ? { ...course, semester: currentTermLabel } : course
    );
  }, [courses, currentTermLabel]);

  const coursesForGrouping = useMemo(() => {
    return normalizedCourses;
  }, [normalizedCourses]);

  const normalizedQuery = useMemo(() => query.trim(), [query]);
  const canSearch = normalizedQuery.length >= 2;

  const filteredCourses = coursesForGrouping;

  useEffect(() => {
    if (!canSearch) {
      setCatalogResults([]);
      setCatalogSearchError(null);
      setCatalogSearchLoading(false);
      return;
    }

    let cancelled = false;
    setCatalogSearchLoading(true);
    setCatalogSearchError(null);

    const timer = window.setTimeout(async () => {
      try {
        const results = await searchCourses(normalizedQuery, undefined, 20, {
          catalogId,
          majors: selectedMajors,
          minors: selectedMinors,
          businessConcentration,
        });
        if (cancelled) return;
        setCatalogResults(results);
      } catch (error: any) {
        if (cancelled) return;
        const fallbackQuery = normalizedQuery.toLowerCase().replace(/\s+/g, '');
        const fallback = Object.entries(catalogCourses ?? {})
          .map(([code, title]) => {
            const codeNorm = code.replace(/\s+/g, '').toLowerCase();
            const titleNorm = title.toLowerCase();
            let rank: number | null = null;
            if (codeNorm.startsWith(fallbackQuery)) rank = 0;
            else if (codeNorm.includes(fallbackQuery)) rank = 1;
            else if (titleNorm.startsWith(fallbackQuery)) rank = 2;
            else if (titleNorm.includes(fallbackQuery)) rank = 3;
            if (rank === null) return null;
            return { code, title, rank };
          })
          .filter((entry): entry is { code: string; title: string; rank: number } => entry !== null)
          .sort((a, b) => a.rank - b.rank || a.code.localeCompare(b.code))
          .slice(0, 20)
          .map((entry) => ({ code: entry.code, title: entry.title, credits: 3 } as CourseCatalogRecord));
        setCatalogResults(fallback);
        setCatalogSearchError(error?.message ?? 'Course search failed. Showing fallback results.');
      } finally {
        if (!cancelled) setCatalogSearchLoading(false);
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [businessConcentration, canSearch, catalogCourses, catalogId, normalizedQuery, selectedMajors, selectedMinors]);

  const planCodeSet = useMemo(() => new Set(courses.map((c) => c.code)), [courses]);
  const isFreeElectivePlaceholderCode = (code: string) => {
    const upper = code.toUpperCase();
    return upper.startsWith('FREE ELECTIVE') || upper.startsWith('FREE_ELECTIVE');
  };
  const isTransferCredit = (course: Course) => (course.tags ?? []).includes('TRANSFER CREDIT');
  const isRetakeCourse = (course: Course) =>
    course.isRetake === true ||
    (course.tags ?? []).includes('Retake') ||
    (course.tags ?? []).includes('Previous Attempt');
  const isPreviousAttemptCourse = (course: Course) =>
    (course.tags ?? []).includes('Previous Attempt');
  const retakeEligibleCodeSet = useMemo(
    () =>
      new Set(
        courses
          .filter(
            (course) =>
              !isTransferCredit(course) &&
              course.courseType !== 'FREE_ELECTIVE' &&
              !isFreeElectivePlaceholderCode(course.code)
          )
          .map((course) => course.code)
      ),
    [courses]
  );

  const completedCourses = filteredCourses.filter((c) => c.semester === 'Completed');
  const inProgressCourses = filteredCourses.filter((c) => c.semester === 'In Progress');
  const plannedCourses = filteredCourses.filter((c) => c.semester !== 'Completed' && c.semester !== 'In Progress');

  // Group courses by semester (exclude Completed)
  const groupedCourses = plannedCourses.reduce<GroupedCourses>((acc, course) => {
    if (!acc[course.semester]) {
      acc[course.semester] = [];
    }
    acc[course.semester].push(course);
    return acc;
  }, {});

  const sortedGroupedCourses = useMemo(() => {
    const order: Record<string, number> = {
      PROGRAM: 0,
      FOUNDATION: 0,
      GENED: 1,
      FREE: 2,
      FREE_ELECTIVE: 2
    };
    const rank = (course: Course) => {
      const type = course.courseType ?? '';
      if (type in order) return order[type];
      if ((course.tags ?? []).includes('GEN ED')) return order.GENED;
      if ((course.tags ?? []).includes('PROGRAM')) return order.PROGRAM;
      if ((course.tags ?? []).includes('FOUNDATION')) return order.FOUNDATION;
      if ((course.tags ?? []).includes('FREE ELECTIVE')) return order.FREE_ELECTIVE;
      return 3;
    };
    const sorted: GroupedCourses = {};
    for (const [term, list] of Object.entries(groupedCourses)) {
      sorted[term] = [...list].sort((a, b) => {
        const diff = rank(a) - rank(b);
        if (diff !== 0) return diff;
        return a.code.localeCompare(b.code);
      });
    }
    return sorted;
  }, [groupedCourses]);

  const sortedGroupedEntries = useMemo(() => {
    const seasonOrder: Record<string, number> = { Spring: 0, Fall: 1 };
    const termKey = (term: string) => {
      const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
      if (!m) return { year: 9999, season: 9, term };
      return { year: Number(m[2]), season: seasonOrder[m[1]] ?? 9, term };
    };
    return Object.entries(groupedCourses).sort((a, b) => {
      const ka = termKey(a[0]);
      const kb = termKey(b[0]);
      if (ka.year !== kb.year) return ka.year - kb.year;
      if (ka.season !== kb.season) return ka.season - kb.season;
      return ka.term.localeCompare(kb.term);
    });
  }, [groupedCourses]);

  const getStatusIcon = (status: Course['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 style={{ color: 'var(--completed)' }} />;
      case 'in-progress':
        return <Clock style={{ color: 'var(--in-progress)' }} />;
      default:
        return <Circle style={{ color: 'var(--border-strong)' }} />;
    }
  };

  const termIndex = (season: string, year: number) => year * 2 + (season === "Fall" ? 1 : 0);
  const termLabels = useMemo(() => {
    if (!startTermSeason || !startTermYear) return [] as string[];
    const baseIdx = termIndex(startTermSeason, startTermYear);
    const labels: string[] = [];
    for (let i = 0; i < totalTerms; i += 1) {
      const idx = baseIdx + i;
      const season = idx % 2 === 1 ? "Fall" : "Spring";
      const year = Math.floor(idx / 2);
      labels.push(`${season} ${year}`);
    }
    return labels;
  }, [startTermSeason, startTermYear, totalTerms]);
  const currentTermIndex = useMemo(() => {
    const now = new Date();
    const currentSeason = now.getMonth() + 1 <= 5 ? "Spring" : "Fall";
    const currentYear = now.getFullYear();
    return termIndex(currentSeason, currentYear);
  }, []);
  const getTermCompletionLabel = (term: string) => {
    const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
    if (!m) return null;
    const season = m[1];
    const year = Number(m[2]);
    const idx = termIndex(season, year);
    if (idx < currentTermIndex) return { label: 'Completed', color: 'var(--completed)' };
    if (idx === currentTermIndex) return { label: 'In Progress', color: 'var(--in-progress)' };
    return { label: 'Planned', color: 'var(--neutral-dark)' };
  };

  const hasAnyPlanned = sortedGroupedEntries.length > 0;
  const termSequence = useMemo(() => {
    const merged = new Set<string>();
    sortedGroupedEntries.forEach(([term]) => merged.add(term));
    termLabels.forEach((term) => merged.add(term));
    const parseTerm = (term: string) => {
      const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
      if (!m) return { year: 9999, season: 9, term };
      return {
        year: Number(m[2]),
        season: m[1] === 'Spring' ? 0 : 1,
        term,
      };
    };
    return Array.from(merged).sort((a, b) => {
      const ka = parseTerm(a);
      const kb = parseTerm(b);
      if (ka.year !== kb.year) return ka.year - kb.year;
      if (ka.season !== kb.season) return ka.season - kb.season;
      return a.localeCompare(b);
    });
  }, [sortedGroupedEntries, termLabels]);
  const boundedTermSequence = termSequence;

  const completedTermOptions = (currentTerm: string) => {
    const allowedTerms = boundedTermSequence.filter((term) => {
      const match = term.match(/^(Spring|Fall)\s+(\d{4})$/);
      const currentMatch = currentTermLabel.match(/^(Spring|Fall)\s+(\d{4})$/);
      if (!match || !currentMatch) return term === currentTermLabel;
      const value = Number(match[2]) * 2 + (match[1] === 'Fall' ? 1 : 0);
      const currentValue = Number(currentMatch[2]) * 2 + (currentMatch[1] === 'Fall' ? 1 : 0);
      return value <= currentValue;
    });

    if (!allowedTerms.includes(currentTerm)) {
      return [...allowedTerms, currentTerm];
    }
    return allowedTerms;
  };
  const hasAnyCourses =
    completedCourses.length > 0 ||
    inProgressCourses.length > 0 ||
    hasAnyPlanned;

  const isProgramOrGenEdCourse = (course: Course) => {
    if (course.courseType === 'PROGRAM' || course.courseType === 'GENED' || course.courseType === 'FOUNDATION') return true;
    const normalizedTags = (course.tags ?? []).map((tag) => tag.trim().toUpperCase());
    return (
      normalizedTags.includes('PROGRAM') ||
      normalizedTags.includes('GEN ED') ||
      normalizedTags.includes('FOUNDATION')
    );
  };
  const hasGenEdSignal = (course: Course) =>
    course.courseType === 'GENED' ||
    (course.tags ?? []).includes('GEN ED') ||
    (course.satisfies ?? []).some((s) => typeof s === 'string' && s.startsWith('GenEd:')) ||
    (course.reason ?? '').includes('GenEd:');
  const hasProgramRequiredSignal = (course: Course) =>
    course.courseType === 'PROGRAM' ||
    (course.tags ?? []).includes('PROGRAM');
  const canChangeGenEdCourse = (course: Course) =>
    hasGenEdSignal(course) && !hasProgramRequiredSignal(course);

  const normalizeCourseCode = (value: string) => value.replace(/\s+/g, '').toUpperCase();

  const recordedCourseRow = (course: Course, mode: 'completed' | 'in-progress') => (
    <div key={course.instanceId} className="record-row">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="course-code">{course.code}</span>
          <span className="muted text-xs num">{course.credits} cr</span>
          {isRetakeCourse(course) && !isPreviousAttemptCourse(course) && <span className="badge badge-warning">Retake</span>}
          {isPreviousAttemptCourse(course) && <span className="badge badge-danger">Previous attempt</span>}
        </div>
        <p className="course-name">{course.name}</p>
      </div>
      <div className="flex flex-wrap items-center gap-1 justify-end">
        {onToggleCompleted && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onToggleCompleted(course.instanceId)}
            title="Remove from completed"
          >
            Remove
          </button>
        )}
        {onToggleInProgress && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onToggleInProgress(course.instanceId)}
            title={mode === 'completed' ? 'Move to currently taking' : 'Remove from currently taking'}
          >
            {mode === 'completed' ? 'Move to in progress' : 'Clear'}
          </button>
        )}
      </div>
    </div>
  );

  const hiddenPastTerms = showEmptyPastTerms
    ? []
    : boundedTermSequence.filter(
        (term) => (sortedGroupedCourses[term] ?? []).length === 0 && getTermCompletionLabel(term)?.label === 'Completed'
      );
  const visibleTerms = boundedTermSequence.filter((term) => !hiddenPastTerms.includes(term));

  return (
    <div className="plan-view">
      <div className="plan-toolbar">
        <div className="search-field">
          <Search aria-hidden="true" className="search-field-icon" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the catalog or your plan (code or title)"
            className="input"
            aria-label="Search courses"
          />
          {query.length > 0 && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="btn btn-ghost btn-icon search-field-clear"
              aria-label="Clear search"
              title="Clear search"
            >
              <X aria-hidden="true" />
            </button>
          )}
        </div>
        {onAddTransferCredit && (
          <button type="button" onClick={onAddTransferCredit} className="btn btn-outline">
            <Plus aria-hidden="true" />
            <span>Transfer credit</span>
          </button>
        )}
      </div>

      {normalizedQuery.length > 0 && (
        <section className="plan-section stack-2" aria-label="Catalog results">
          <p className="plan-section-title">Catalog results <span className="muted">(up to 20)</span></p>
          {!canSearch && <p className="text-sm muted">Type at least 2 characters.</p>}
          {canSearch && catalogSearchLoading && <p className="text-sm muted">Searching courses…</p>}
          {canSearch && !catalogSearchLoading && catalogSearchError && (
            <p className="text-sm muted">{catalogSearchError}</p>
          )}
          {canSearch && !catalogSearchLoading && !catalogSearchError && catalogResults.length === 0 && (
            <p className="text-sm muted">No matching catalog courses.</p>
          )}
          <div className="stack-2">
            {catalogResults.map((result) => {
              const code = result.code;
              const credits = typeof result.credits === 'number' && result.credits >= 0 ? result.credits : 3;
              const genEdTags = (result.gen_ed_tags ?? []).filter((tag) => typeof tag === 'string' && tag.trim().length > 0);
              const businessBadges = (result.business_classification?.badges ?? []).filter(
                (badge): badge is string =>
                  typeof badge === 'string'
                  && badge.trim().length > 0
                  && badge !== 'Required for BUS Core'
                  && badge !== 'Counts as BUS elective'
              );
              const availability = getCourseAvailabilityInfo(result, {
                mode: "plan_add",
                isExcelOnly: result.is_excel_only === true,
                currentTermLabel,
                scheduleTerms
              });
              const hasWarning = Boolean(availability.warningLabel);
              const inPlan = planCodeSet.has(code);
              return (
                <div key={code} className="search-result card-interactive">
                  <div className="min-w-0 stack-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="course-code">{code}</span>
                      <span className="course-name-inline">{result.title}</span>
                      <span className="muted text-xs num">{credits} cr</span>
                      {hasWarning && availability.warningLabel && (
                        <span className="badge badge-warning">{availability.warningLabel}</span>
                      )}
                    </div>
                    {genEdTags.length > 0 && <p className="text-xs muted">GenEd: {genEdTags.join(' · ')}</p>}
                    {businessBadges.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {businessBadges.map((badge) => (
                          <span key={`${code}:${badge}`} className="badge badge-neutral">{badge}</span>
                        ))}
                      </div>
                    )}
                    {hasWarning && availability.detailsLabel && <p className="text-xs muted">{availability.detailsLabel}</p>}
                  </div>
                  <div className="flex flex-wrap items-center gap-2 justify-end">
                    {inPlan && <span className="badge badge-success">In your record</span>}
                    {onAddCourse && !inPlan && (
                      <button
                        type="button"
                        onClick={() => onAddCourse(code)}
                        className="btn btn-primary btn-sm"
                        title={
                          hasWarning
                            ? availability.isSelectionBlocked
                              ? `${availability.warningLabel}. ${availability.detailsLabel}. Availability is enforced after you choose a term.`
                              : `${availability.warningLabel}. ${availability.detailsLabel}.`
                            : "Add to plan"
                        }
                      >
                        <Plus aria-hidden="true" />
                        <span>Add</span>
                      </button>
                    )}
                    {onAddRetakeCourse && retakeEligibleCodeSet.has(code) && (
                      <button
                        type="button"
                        onClick={() => onAddRetakeCourse(code)}
                        className="btn btn-outline btn-sm"
                        title="Add as Retake (0 credits)"
                      >
                        <RefreshCcw aria-hidden="true" />
                        <span>Add as retake</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {!hasAnyCourses && <p className="plan-section text-sm muted">No matching courses.</p>}

      {inProgressCourses.length > 0 && (
        <section className="plan-section stack-2" aria-label="Currently taking">
          <p className="plan-section-title">Currently taking</p>
          <div className="card record-list">{inProgressCourses.map((course) => recordedCourseRow(course, 'in-progress'))}</div>
        </section>
      )}

      {completedCourses.length > 0 && (
        <section className="plan-section stack-2" aria-label="Completed">
          <p className="plan-section-title">Completed</p>
          <div className="card record-list">{completedCourses.map((course) => recordedCourseRow(course, 'completed'))}</div>
        </section>
      )}

      {hiddenPastTerms.length > 0 && (
        <div className="plan-section">
          <div className="collapsed-terms">
            <History aria-hidden="true" />
            <span>
              {hiddenPastTerms.length} earlier semester{hiddenPastTerms.length === 1 ? '' : 's'} ({hiddenPastTerms[0]}
              {hiddenPastTerms.length > 1 ? ` – ${hiddenPastTerms[hiddenPastTerms.length - 1]}` : ''}){' '}
              {hiddenPastTerms.length === 1 ? 'has' : 'have'} no recorded courses.
            </span>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowEmptyPastTerms(true)}>
              Show
            </button>
          </div>
        </div>
      )}

      <div className="term-grid">
        {visibleTerms.map((semester) => {
          const semesterCourses = sortedGroupedCourses[semester] ?? [];
          const totalCredits = semesterCourses.reduce((sum, course) => sum + Number(course.credits ?? 0), 0);
          const completionLabel = getTermCompletionLabel(semester);
          const termNumber = boundedTermSequence.indexOf(semester) + 1;

          return (
            <section key={semester} className="term-card card" aria-label={semester}>
              <header className="term-card-header">
                <span className="term-number num" aria-hidden="true">{termNumber}</span>
                <div className="min-w-0">
                  <h3 className="term-title">{semester}</h3>
                  <span className="text-sm muted num">{totalCredits} credits</span>
                </div>
                {completionLabel && (
                  <span className={`badge ${TERM_STATUS_BADGE[completionLabel.label] ?? 'badge-neutral'}`}>
                    {completionLabel.label}
                  </span>
                )}
              </header>

              <div className="term-card-body">
                {semesterCourses.length === 0 && <p className="text-sm muted term-empty">No courses scheduled.</p>}
                {semesterCourses.map((course) => {
                  const electiveNotes = (course.electiveNotes ?? []).filter((note) =>
                    /major elective|minor elective/i.test(note)
                  );
                  const transferCredit = isTransferCredit(course);
                  const retake = isRetakeCourse(course);
                  const canToggle = !!onToggleCompleted && !transferCredit && !retake;
                  const tags = course.tags.filter((tag) => !HIDDEN_TAGS.has(tag));
                  return (
                    <article
                      key={course.instanceId}
                      className={`course-card is-${course.status}${transferCredit ? ' is-transfer' : ''}${retake ? ' is-retake' : ''}${movingCourseInstanceId === course.instanceId ? ' is-moving' : ''}`}
                      onMouseEnter={() => setHoveredCourse(course.instanceId)}
                      onMouseLeave={() => setHoveredCourse(null)}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          if (canToggle) onToggleCompleted?.(course.instanceId);
                        }}
                        className="course-status"
                        aria-label={course.status === 'completed' ? `Mark ${course.code} not completed` : `Mark ${course.code} completed`}
                        title={canToggle ? (course.status === 'completed' ? 'Mark as not completed' : 'Mark as completed') : undefined}
                        disabled={!canToggle}
                      >
                        {getStatusIcon(course.status)}
                      </button>

                      <div className="course-main">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="course-code">{course.code}</span>
                          <span className="muted text-xs num">{course.credits} cr</span>
                          {tags.map((tag) => (
                            <span key={tag} className={`badge ${TAG_BADGES[tag]?.className ?? 'badge-neutral'}`}>
                              {TAG_BADGES[tag]?.label ?? tag}
                            </span>
                          ))}
                        </div>
                        <p className="course-name">{course.name}</p>
                        {course.reason && <p className="course-reason">{course.reason}</p>}
                        {electiveNotes.length > 0 && <p className="course-reason">{electiveNotes.join(' · ')}</p>}

                        {onMoveCompleted && course.status === 'completed' && !transferCredit && !retake && (
                          <label className="course-inline-field">
                            <span>Completed term</span>
                            <select
                              value={course.semester}
                              onChange={(e) => onMoveCompleted(course.instanceId, e.target.value)}
                              className="input input-sm"
                            >
                              {completedTermOptions(course.semester).map((term) => (
                                <option key={term} value={term}>
                                  {term}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}

                        <div className="course-actions">
                          {onToggleInProgress && course.status !== 'completed' && !transferCredit && !retake && (
                            <button type="button" onClick={() => onToggleInProgress(course.instanceId)} className="btn btn-ghost btn-sm">
                              <Clock aria-hidden="true" />
                              <span>{course.status === 'in-progress' ? 'Clear in progress' : 'Mark in progress'}</span>
                            </button>
                          )}
                          {onChangeGenEd && course.status !== 'completed' && !transferCredit && !retake && canChangeGenEdCourse(course) && (
                            <button
                              type="button"
                              onClick={() => onChangeGenEd(course.instanceId, course.semester)}
                              className="btn btn-ghost btn-sm"
                              title="Choose a different course for this GenEd category"
                            >
                              <RefreshCcw aria-hidden="true" />
                              <span>Change course</span>
                            </button>
                          )}
                          {onSwapElective && course.status === 'remaining' && swappableElectiveIds?.has(course.instanceId) && (
                            <button
                              type="button"
                              onClick={() => onSwapElective(course.instanceId)}
                              className="btn btn-ghost btn-sm"
                              title="Replace this elective with another course"
                            >
                              <RefreshCcw aria-hidden="true" />
                              <span>Swap elective</span>
                            </button>
                          )}
                          {onMoveCourse && course.status === 'remaining' && !transferCredit && (
                            <button
                              type="button"
                              onClick={() => onMoveCourse(course.instanceId)}
                              className={`btn btn-sm ${movingCourseInstanceId === course.instanceId ? 'btn-primary' : 'btn-ghost'}`}
                              title="Move this course to another semester"
                            >
                              <ArrowLeftRight aria-hidden="true" />
                              <span>Move</span>
                            </button>
                          )}
                          {transferCredit && onRemoveTransferCredit && (
                            <button
                              type="button"
                              onClick={() => onRemoveTransferCredit(course.instanceId)}
                              className="btn btn-ghost btn-sm course-action-danger"
                              title="Remove transfer credit"
                            >
                              <Trash2 aria-hidden="true" />
                              <span>Remove</span>
                            </button>
                          )}
                          {onRemoveCourse && !transferCredit && (retake || !isProgramOrGenEdCourse(course)) && (
                            <button
                              type="button"
                              onClick={() => onRemoveCourse(course.instanceId)}
                              className="btn btn-ghost btn-sm course-action-danger"
                              title="Remove course"
                            >
                              <Trash2 aria-hidden="true" />
                              <span>Remove</span>
                            </button>
                          )}
                        </div>
                      </div>

                      {hoveredCourse === course.instanceId && (course.prerequisites?.length || course.prereqText) && (
                        <div className="course-tooltip" role="tooltip">
                          <Info aria-hidden="true" />
                          <div>
                            <p className="course-tooltip-title">Prerequisites</p>
                            <p>{course.prereqText ? course.prereqText : (course.prerequisites ?? []).join(', ')}</p>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

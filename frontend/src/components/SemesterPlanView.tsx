import { useEffect, useMemo, useState } from 'react';
import { Course, ElectivePlaceholder } from '../types';
import { BookOpen, CheckCircle2, ChevronDown, ChevronUp, Circle, Clock, Info, RefreshCcw, X } from 'lucide-react';
import { searchCourses, type CourseCatalogRecord } from '../api';
import { getCourseAvailabilityInfo } from '../utils/courseAvailability';

interface SemesterPlanViewProps {
  courses: Course[];
  catalogCourses?: Record<string, string>;
  startTermSeason?: string;
  startTermYear?: number;
  totalTerms?: number;
  electivePlaceholders?: ElectivePlaceholder[];
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

interface GroupedCourses {
  [semester: string]: Course[];
}

const ELECTIVE_TAG_ALIASES: Record<string, string[]> = {
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
  'Sustainability Studies': ['Sustainability', 'Sustainabiliy']
};

export function SemesterPlanView({
  courses,
  catalogCourses,
  startTermSeason,
  startTermYear,
  totalTerms = 8,
  electivePlaceholders,
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
  const [query, setQuery] = useState('');
  const [catalogResults, setCatalogResults] = useState<CourseCatalogRecord[]>([]);
  const [catalogSearchLoading, setCatalogSearchLoading] = useState(false);
  const [catalogSearchError, setCatalogSearchError] = useState<string | null>(null);
  const [expandedElectiveRequirement, setExpandedElectiveRequirement] = useState<string | null>(null);
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
        const results = await searchCourses(normalizedQuery, undefined, 20);
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
  }, [canSearch, normalizedQuery, catalogCourses]);

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
        return <CheckCircle2 className="w-5 h-5" style={{ color: 'var(--completed)' }} />;
      case 'in-progress':
        return <Clock className="w-5 h-5" style={{ color: 'var(--in-progress)' }} />;
      default:
        return <Circle className="w-5 h-5" style={{ color: 'var(--neutral-dark)' }} />;
    }
  };

  const getStatusColor = (status: Course['status']) => {
    switch (status) {
      case 'completed':
        return 'var(--completed)';
      case 'in-progress':
        return 'var(--in-progress)';
      default:
        return 'var(--neutral-border)';
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
    if (boundedTermSequence.includes(currentTerm)) return boundedTermSequence;
    return [currentTerm, ...boundedTermSequence];
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

  const electiveRequirementCards = useMemo(() => {
    if (!electivePlaceholders || electivePlaceholders.length === 0) return [];

    const normalizeText = (value: string) => value.replace(/\s+/g, ' ').trim().toLowerCase();
    const manualMajorCreditsByProgram = new Map<string, number>();
    courses.forEach((course) => {
      if (!isTransferCredit(course)) return;
      const reason = typeof course.reason === 'string' ? course.reason : '';
      const match = reason.match(/^Major Elective:\s+(.+)$/i);
      if (!match) return;
      const program = (match[1] ?? '').trim();
      if (!program) return;
      manualMajorCreditsByProgram.set(
        program,
        (manualMajorCreditsByProgram.get(program) ?? 0) + Number(course.credits ?? 0)
      );
    });
    const grouped = new Map<
      string,
      { programType: ElectivePlaceholder['program_type']; program: string; items: ElectivePlaceholder[] }
    >();

    electivePlaceholders.forEach((placeholder) => {
      const key = `${placeholder.program_type}:${placeholder.program}`;
      if (!grouped.has(key)) {
        grouped.set(key, {
          programType: placeholder.program_type,
          program: placeholder.program,
          items: []
        });
      }
      grouped.get(key)?.items.push(placeholder);
    });

    return Array.from(grouped.entries())
      .map(([key, group]) => {
        const { programType, program, items } = group;
        const programLabel = `${programType === 'major' ? 'Major' : 'Minor'}: ${program}`;
        const headerTotals = items.filter(
          (item) => item.is_total && (Number(item.credits_required ?? 0) > 0 || Number(item.courses_required ?? 0) > 0)
        );
        const totalCredits =
          headerTotals.length > 0
            ? Math.max(...headerTotals.map((item) => Number(item.credits_required ?? 0)))
            : items.reduce((sum, item) => sum + Number(item.credits_required ?? 0), 0);
        const totalCourses =
          headerTotals.length > 0
            ? Math.max(...headerTotals.map((item) => Number(item.courses_required ?? 0)))
            : items.reduce((sum, item) => sum + Number(item.courses_required ?? 0), 0);

        const allowedByNormalized = new Map<string, string>();
        items.forEach((item) => {
          (item.allowed_courses ?? []).forEach((code) => {
            const trimmed = (code ?? '').trim();
            if (!trimmed) return;
            const normalized = normalizeCourseCode(trimmed);
            if (!allowedByNormalized.has(normalized)) {
              allowedByNormalized.set(normalized, trimmed);
            }
          });
        });
        const allowedCourses = Array.from(allowedByNormalized.values());
        const noteNeedle = programType === 'major' ? 'major elective' : 'minor elective';
        const aliasPrefixes = (ELECTIVE_TAG_ALIASES[program] ?? []).map((alias) => normalizeText(alias));
        const matchingCourses = Array.from(
          courses.reduce((matched, course) => {
            const normalizedCode = normalizeCourseCode(course.code);
            const matchesByAllowedCourse = allowedByNormalized.has(normalizedCode);
            const matchesByElectiveNote = (course.electiveNotes ?? []).some((note) => {
              const normalizedNote = normalizeText(note);
              if (!normalizedNote.includes(noteNeedle)) return false;
              if (aliasPrefixes.length === 0) return false;
              return aliasPrefixes.some((alias) => normalizedNote.startsWith(`${alias} `));
            });

            if (!matchesByAllowedCourse && !matchesByElectiveNote) {
              return matched;
            }

            if (!matched.has(normalizedCode)) {
              matched.set(normalizedCode, course);
            }
            return matched;
          }, new Map<string, Course>())
            .values()
        );
        const manualMajorCredits =
          programType === 'major' ? Number(manualMajorCreditsByProgram.get(program) ?? 0) : 0;
        const matchedCredits =
          matchingCourses.reduce((sum, course) => sum + Number(course.credits ?? 0), 0) + manualMajorCredits;
        const matchedCourseCodes = matchingCourses.map((course) => course.code);
        const matchedCourseEquivalentCount =
          matchedCourseCodes.length + (programType === 'major' ? Math.floor(manualMajorCredits / 3) : 0);
        const requirementText =
          totalCredits > 0
            ? matchedCredits > 0
              ? Math.max(totalCredits - matchedCredits, 0) > 0
                ? `${Math.max(totalCredits - matchedCredits, 0)} credits left`
                : 'Completed'
              : `${totalCredits} credits`
            : totalCourses > 0
              ? matchedCourseEquivalentCount > 0
                ? Math.max(totalCourses - matchedCourseEquivalentCount, 0) > 0
                  ? `${Math.max(totalCourses - matchedCourseEquivalentCount, 0)} courses left`
                  : 'Completed'
                : `${totalCourses} courses`
              : 'Electives required';

        const inferredTotal = totalCourses > 0 ? totalCourses : allowedCourses.length;
        const totalCount = Math.max(inferredTotal, matchedCourseEquivalentCount);

        const ruleText = Array.from(
          new Set(
            items
              .map((item) => item.rule_text?.trim() ?? '')
              .filter((value) => value.length > 0)
          )
        ).join(' ');

        return {
          key,
          programType,
          programLabel,
          requirementText,
          matchingCourses: matchedCourseCodes,
          allowedCourses,
          ruleText,
          doneCount: matchedCourseEquivalentCount,
          totalCount
        };
      })
      .sort((a, b) => {
        if (a.programType !== b.programType) return a.programType === 'major' ? -1 : 1;
        return a.programLabel.localeCompare(b.programLabel);
      });
  }, [electivePlaceholders, courses]);

  return (
    <div className="space-y-6">
      <div className="px-6 pt-4">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1" style={{ position: 'relative' }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search courses (code or title)"
              className="w-full px-4 py-3 pr-12 rounded-lg border box-border"
              style={{ borderColor: 'var(--neutral-border)' }}
            />
            {query.length > 0 && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="cursor-pointer"
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: '26px',
                  height: '26px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--neutral-dark)',
                  background: 'var(--white)',
                  border: '1px solid var(--neutral-border)',
                  borderRadius: '9999px'
                }}
                aria-label="Clear search"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            </div>
            {onAddTransferCredit && (
              <button
                type="button"
                onClick={onAddTransferCredit}
                className="text-xs px-3 py-2 rounded-lg border whitespace-nowrap"
                style={{
                  borderColor: 'var(--navy-blue)',
                  background: '#eef6ff',
                  color: 'var(--navy-dark)'
                }}
              >
                Add Transfer Credit (OTH 0001)
              </button>
            )}
          </div>
        </div>
      </div>

      {normalizedQuery.length > 0 && (
        <div className="px-6">
          <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
            Catalog results (showing up to 20)
          </div>
          {!canSearch && (
            <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
              Type at least 2 characters.
            </div>
          )}
          {canSearch && catalogSearchLoading && (
            <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
              Searching courses...
            </div>
          )}
          {canSearch && !catalogSearchLoading && catalogSearchError && (
            <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
              {catalogSearchError}
            </div>
          )}
          {canSearch && !catalogSearchLoading && !catalogSearchError && catalogResults.length === 0 && (
            <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
              No matching catalog courses.
            </div>
          )}
          <div className="grid gap-2">
            {catalogResults.map((result) => {
              const code = result.code;
              const title = result.title;
              const credits = typeof result.credits === 'number' && result.credits > 0 ? result.credits : 3;
              const genEdTags = (result.gen_ed_tags ?? []).filter((tag) => typeof tag === 'string' && tag.trim().length > 0);
              const availability = getCourseAvailabilityInfo(result, {
                mode: "plan_add",
                isExcelOnly: result.is_excel_only === true,
                currentTermLabel
              });
              const hasWarning = Boolean(availability.warningLabel);
              return (
                <div
                  key={code}
                  className="p-3 rounded-lg border"
                  style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-start gap-2">
                        <div className="font-medium">
                          {code} - {title}
                        </div>
                        {hasWarning && availability.warningLabel && (
                          <span
                            className="text-xs px-2 py-1 rounded-full border"
                            style={{
                              borderColor: '#f59e0b',
                              background: '#fffbeb',
                              color: '#92400e'
                            }}
                          >
                            {availability.warningLabel}
                          </span>
                        )}
                      </div>
                      <div className="text-xs mt-1" style={{ color: 'var(--neutral-dark)' }}>
                        {credits} credits
                      </div>
                      {genEdTags.length > 0 && (
                        <div className="text-xs mt-1" style={{ color: 'var(--neutral-dark)' }}>
                          Gen-Ed: {genEdTags.join(' | ')}
                        </div>
                      )}
                      {hasWarning && availability.detailsLabel && (
                        <div
                          className="text-xs mt-1"
                          style={{ color: 'var(--neutral-dark)', fontStyle: 'italic' }}
                        >
                          {availability.detailsLabel}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
                        {planCodeSet.has(code) ? 'In record' : 'Not in plan'}
                      </div>
                      {onAddCourse && !planCodeSet.has(code) && (
                        <button
                          type="button"
                          onClick={() => onAddCourse(code)}
                          className="text-xs px-2 py-1 rounded border"
                          style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                          title={
                            hasWarning
                              ? availability.isSelectionBlocked
                                ? `${availability.warningLabel}. ${availability.detailsLabel}. Availability is enforced after you choose a term.`
                                : `${availability.warningLabel}. ${availability.detailsLabel}.`
                              : "Add to plan"
                          }
                        >
                          Add
                        </button>
                      )}
                      {onAddRetakeCourse && retakeEligibleCodeSet.has(code) && (
                        <button
                          type="button"
                          onClick={() => onAddRetakeCourse(code)}
                          className="text-xs px-2 py-1 rounded border"
                          style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                          title="Add as Retake (0 credits)"
                        >
                          Add as Retake
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!hasAnyCourses && (
        <div className="px-6 pb-6 text-sm" style={{ color: 'var(--neutral-dark)' }}>
          No matching courses.
        </div>
      )}

      {inProgressCourses.length > 0 && (
        <div className="px-6 pb-2">
          <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
            Currently Taking
          </div>
          <div className="grid gap-2">
            {inProgressCourses.map((course) => (
              <div
                key={course.instanceId}
                className="p-3 rounded-lg border"
                style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{course.code}</div>
                    <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      {course.name}
                    </div>
                    {(isRetakeCourse(course) || isPreviousAttemptCourse(course)) && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {isRetakeCourse(course) && !isPreviousAttemptCourse(course) && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: '#e2e8f0', color: '#0f172a' }}
                          >
                            Retake
                          </span>
                        )}
                        {isPreviousAttemptCourse(course) && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: '#fee2e2', color: '#7f1d1d' }}
                          >
                            Previous Attempt
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
                      {course.credits} credits
                    </div>
                    {onToggleCompleted && (
                      <button
                        type="button"
                        onClick={() => onToggleCompleted(course.instanceId)}
                        className="text-xs px-2 py-1 rounded border cursor-pointer"
                        style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        title="Remove from completed"
                      >
                        Remove
                      </button>
                    )}
                    {onToggleInProgress && (
                      <button
                        type="button"
                        onClick={() => onToggleInProgress(course.instanceId)}
                        className="text-xs px-2 py-1 rounded border"
                        style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        title="Remove from currently taking"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {completedCourses.length > 0 && (
        <div className="px-6 pb-2">
          <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
            Completed
          </div>
          <div className="grid gap-2">
            {completedCourses.map((course) => (
              <div
                key={course.instanceId}
                className="p-3 rounded-lg border"
                style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{course.code}</div>
                    <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      {course.name}
                    </div>
                    {(isRetakeCourse(course) || isPreviousAttemptCourse(course)) && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {isRetakeCourse(course) && !isPreviousAttemptCourse(course) && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: '#e2e8f0', color: '#0f172a' }}
                          >
                            Retake
                          </span>
                        )}
                        {isPreviousAttemptCourse(course) && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: '#fee2e2', color: '#7f1d1d' }}
                          >
                            Previous Attempt
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
                      {course.credits} credits
                    </div>
                    {onToggleCompleted && (
                      <button
                        type="button"
                        onClick={() => onToggleCompleted(course.instanceId)}
                        className="text-xs px-2 py-1 rounded border cursor-pointer"
                        style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        title="Remove from completed"
                      >
                        Remove
                      </button>
                    )}
                    {onToggleInProgress && (
                      <button
                        type="button"
                        onClick={() => onToggleInProgress(course.instanceId)}
                        className="text-xs px-2 py-1 rounded border"
                        style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        title="Move to currently taking"
                      >
                        Move to In Progress
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {boundedTermSequence.map((semester, index) => {
        const semesterCourses = sortedGroupedCourses[semester] ?? [];
        const totalCredits = semesterCourses.reduce((sum, course) => sum + Number(course.credits ?? 0), 0);
        const hasFreeElective = semesterCourses.some(
          (c) =>
            (c.tags ?? []).includes('FREE ELECTIVE') ||
            c.code.startsWith('FREE_ELECTIVE') ||
            c.code.startsWith('FREE ELECTIVE')
        );

        const completionLabel = getTermCompletionLabel(semester);
        
        return (
          <div key={semester} className="relative">
            {/* Timeline connector */}
            {index < termSequence.length - 1 && (
              <div
                className="absolute left-6 top-16 w-0.5 h-full"
                style={{ backgroundColor: 'var(--neutral-border)', zIndex: 0 }}
              />
            )}

            {/* Semester Header */}
            <div className="flex items-center gap-4 mb-4 relative z-10">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: 'var(--navy-blue)', color: 'var(--white)' }}
              >
                {index + 1}
              </div>
              <div className="flex-1">
                <h4>{semester}</h4>
                <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                  {totalCredits} credits
                </p>
              </div>
              {completionLabel && (
                <span
                  className="px-3 py-1 rounded-full text-xs"
                  style={{ backgroundColor: 'var(--neutral-gray)', color: completionLabel.color }}
                >
                  {completionLabel.label}
                </span>
              )}
            </div>

            {/* Course Cards */}
            <div className="ml-16 space-y-3">
              {semesterCourses.length === 0 && (
                <div
                  className="rounded-lg p-4 border-2"
                  style={{ backgroundColor: 'var(--white)', borderColor: 'var(--neutral-border)' }}
                >
                  <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                    No courses scheduled.
                  </div>
                </div>
              )}
              {semesterCourses.map((course) => (
                <div
                  key={course.instanceId}
                  className="rounded-lg p-4 border-2 transition-all cursor-pointer relative"
                  style={{
                    backgroundColor: isTransferCredit(course)
                      ? '#eef6ff'
                      : isRetakeCourse(course)
                        ? '#f8fafc'
                        : 'var(--white)',
                    borderColor: isTransferCredit(course)
                      ? 'var(--navy-blue)'
                      : isRetakeCourse(course)
                        ? '#64748b'
                        : getStatusColor(course.status)
                  }}
                  onMouseEnter={() => setHoveredCourse(course.instanceId)}
                  onMouseLeave={() => setHoveredCourse(null)}
                >
                  {(() => {
                    const electiveNotes = (course.electiveNotes ?? []).filter((note) =>
                      /major elective|minor elective/i.test(note)
                    );
                    const transferCredit = isTransferCredit(course);
                    const retake = isRetakeCourse(course);
                    return (
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <button
                        type="button"
                        onClick={() => {
                          if (!transferCredit && !retake) {
                            onToggleCompleted?.(course.instanceId);
                          }
                        }}
                        className={onToggleCompleted && !transferCredit && !retake ? "cursor-pointer" : ""}
                        style={{ background: "transparent", border: "none", padding: 0 }}
                        aria-label="Toggle completed"
                        disabled={transferCredit || retake}
                      >
                        {getStatusIcon(course.status)}
                      </button>
                      <div className="flex-1">
                        <div className="flex items-baseline gap-2 mb-1">
                          <span style={{ fontWeight: 600, color: 'var(--navy-dark)' }}>
                            {course.code}
                          </span>
                          <span className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                            {course.credits} credits
                          </span>
                        </div>
                        <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                          {course.name}
                        </p>
                        {course.reason && (
                          <p className="text-xs mt-1" style={{ color: 'var(--neutral-dark)' }}>
                            {course.reason}
                          </p>
                        )}
                        <div className="flex flex-wrap gap-2 mt-2">
                          {course.tags.map((tag, i) => {
                            let background = 'var(--neutral-gray)';
                            let color = 'var(--neutral-dark)';
                            if (tag === 'PROGRAM') {
                              background = 'var(--navy-blue)';
                              color = 'var(--white)';
                            } else if (tag === 'GEN ED') {
                              background = 'var(--academic-gold)';
                              color = 'var(--navy-dark)';
                            } else if (tag === 'Writing Intensive Course') {
                              background = 'var(--navy-blue)';
                              color = 'var(--white)';
                            } else if (tag === 'FREE ELECTIVE') {
                              background = 'var(--neutral-border)';
                              color = 'var(--navy-dark)';
                            } else if (tag === 'FOUNDATION') {
                              background = 'var(--neutral-dark)';
                              color = 'var(--white)';
                            } else if (tag === 'Completed') {
                              background = 'var(--completed)';
                              color = 'var(--white)';
                            } else if (tag === 'TRANSFER CREDIT') {
                              background = 'var(--navy-blue)';
                              color = 'var(--white)';
                            } else if (tag === 'Retake') {
                              background = '#e2e8f0';
                              color = '#0f172a';
                            } else if (tag === 'Previous Attempt') {
                              background = '#fee2e2';
                              color = '#7f1d1d';
                            }
                            return (
                            <span
                              key={i}
                              className="px-2 py-1 rounded text-xs"
                              style={{
                                backgroundColor: background,
                                color
                              }}
                            >
                              {tag}
                            </span>
                          )})}
                        </div>
                        {onToggleInProgress && course.status !== 'completed' && !transferCredit && !retake && (
                          <div className="mt-2">
                            <button
                              type="button"
                              onClick={() => onToggleInProgress(course.instanceId)}
                              className="text-xs px-2 py-1 rounded border"
                              style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                            >
                              {course.status === 'in-progress' ? 'Clear In Progress' : 'Mark In Progress'}
                            </button>
                          </div>
                        )}
                        {onMoveCompleted && course.status === 'completed' && !transferCredit && !retake && (
                          <div className="mt-2">
                            <label className="text-xs mr-2" style={{ color: 'var(--neutral-dark)' }}>
                              Completed term
                            </label>
                            <select
                              value={course.semester}
                              onChange={(e) => onMoveCompleted(course.instanceId, e.target.value)}
                              className="text-xs px-2 py-1 rounded border"
                              style={{ borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                            >
                              {completedTermOptions(course.semester).map((term) => (
                                <option key={term} value={term}>
                                  {term}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      {electiveNotes.length > 0 && (
                        <div className="text-xs text-right" style={{ color: 'var(--neutral-dark)' }}>
                          {electiveNotes.join(' | ')}
                        </div>
                      )}
                      {onChangeGenEd && course.status !== 'completed' && !transferCredit && !retake && canChangeGenEdCourse(course) && (
                        <button
                          type="button"
                          onClick={() => onChangeGenEd(course.instanceId, course.semester)}
                          className="text-xs px-1.5 py-0.5 rounded inline-flex items-center justify-center gap-1 leading-none font-medium transition-opacity duration-150 hover:opacity-90 active:opacity-100"
                          style={{
                            color: 'var(--navy-dark)',
                            backgroundColor: 'var(--academic-gold)'
                          }}
                          title="Change GenEd course"
                        >
                          <RefreshCcw className="w-2 h-2" />
                          Change course
                        </button>
                      )}
                      {transferCredit && onRemoveTransferCredit && (
                        <button
                          type="button"
                          onClick={() => onRemoveTransferCredit(course.instanceId)}
                          className="text-sm"
                          style={{ color: 'var(--navy-dark)' }}
                          title="Remove transfer credit"
                        >
                          Remove
                        </button>
                      )}
                      {onRemoveCourse && !transferCredit && (retake || !isProgramOrGenEdCourse(course)) && (
                        <button
                          type="button"
                          onClick={() => onRemoveCourse(course.instanceId)}
                          className="text-sm"
                          style={{ color: 'var(--neutral-dark)' }}
                          title="Remove course"
                        >
                          Remove
                        </button>
                      )}
                      {onMoveCourse && course.status === 'remaining' && !transferCredit && (
                        <button
                          type="button"
                          onClick={() => onMoveCourse(course.instanceId)}
                          className="text-sm"
                          style={
                            movingCourseInstanceId === course.instanceId
                              ? {
                                  color: 'var(--white)',
                                  background: 'var(--navy-blue)',
                                  padding: '2px 8px',
                                  borderRadius: '8px'
                                }
                              : { color: 'var(--navy-dark)' }
                          }
                          title="Move course"
                        >
                          Move course
                        </button>
                      )}
                    </div>
</div>
                    );
                  })()}

                  {/* Hover Tooltip */}
                  {hoveredCourse === course.instanceId && (course.prerequisites?.length || course.prereqText) && (
                    <div
                      className="absolute left-0 top-full mt-2 p-3 rounded-lg shadow-lg z-20 text-sm"
                      style={{
                        backgroundColor: 'var(--navy-dark)',
                        color: '#EAF4FF',
                        width: '280px'
                      }}
                    >
                      <div className="flex items-start gap-2">
                        <Info className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#EAF4FF' }} />
                        <div>
                          <p style={{ fontWeight: 600, marginBottom: '0.25rem', color: '#EAF4FF' }}>Prerequisites</p>
                          <p style={{ fontSize: '0.875rem', color: '#EAF4FF' }}>
                            {course.prereqText
                              ? course.prereqText
                              : (course.prerequisites ?? []).join(", ")}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {electiveRequirementCards.length > 0 && (
        <div className="px-6 pb-8">
          <div
            className="rounded-2xl border p-5"
            style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: 'var(--navy-blue)' }}
              >
                <BookOpen className="w-4 h-4" style={{ color: 'var(--academic-gold)' }} />
              </div>
              <div>
                <h4 style={{ color: 'var(--navy-dark)', marginBottom: '2px' }}>Elective Requirements</h4>
                <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                  Choose from approved courses
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {electiveRequirementCards.map((card) => {
                const isOpen = expandedElectiveRequirement === card.key;
                return (
                  <div
                    key={card.key}
                    className="rounded-xl border"
                    style={{
                      borderColor: isOpen ? 'var(--academic-gold)' : 'var(--neutral-border)',
                      background: 'var(--white)'
                    }}
                  >
                    <button
                      type="button"
                      className="w-full p-4 text-left"
                      onClick={() => setExpandedElectiveRequirement((prev) => (prev === card.key ? null : card.key))}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold" style={{ color: 'var(--navy-dark)' }}>
                            {card.programLabel}
                          </span>
                          {card.doneCount > 0 && (
                            <span
                              className="px-1.5 py-0.5 rounded text-xs font-semibold"
                              style={{ color: 'var(--white)' }}
                            >
                              {card.doneCount}
                            </span>
                          )}
                        </div>
                        {isOpen ? (
                          <ChevronUp className="w-4 h-4" style={{ color: 'var(--neutral-dark)' }} />
                        ) : (
                          <ChevronDown className="w-4 h-4" style={{ color: 'var(--neutral-dark)' }} />
                        )}
                      </div>

                      <div className="text-sm mt-1" style={{ color: 'var(--neutral-dark)' }}>
                        {card.requirementText}
                      </div>
                    </button>

                    {isOpen && (
                      <div className="px-4 pb-4 pt-0 border-t" style={{ borderColor: 'var(--neutral-border)' }}>
                        {card.matchingCourses.length > 0 && (
                          <div
                            className="mt-2 p-2 rounded text-sm"
                            style={{ background: 'var(--neutral-cream)', color: 'var(--navy-dark)' }}
                          >
                            In your plan: {card.matchingCourses.join(', ')}
                          </div>
                        )}

                        {card.allowedCourses.length > 0 && (
                          <div className="mt-2">
                            <div className="text-xs font-semibold mb-1" style={{ color: 'var(--neutral-dark)' }}>
                              Approved courses
                            </div>
                            <div className="flex flex-wrap gap-1">
                              {card.allowedCourses.slice(0, 18).map((code) => (
                                <span
                                  key={`${card.key}:${code}`}
                                  className="px-2 py-1 rounded text-xs border"
                                  style={{ borderColor: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                                >
                                  {code}
                                </span>
                              ))}
                              {card.allowedCourses.length > 18 && (
                                <span className="text-xs px-2 py-1" style={{ color: 'var(--neutral-dark)' }}>
                                  +{card.allowedCourses.length - 18} more
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {card.ruleText && (
                          <div className="text-xs mt-2" style={{ color: 'var(--neutral-dark)' }}>
                            {card.ruleText}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

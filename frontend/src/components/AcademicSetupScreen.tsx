import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowRight, ArrowLeft, CheckCircle2 } from 'lucide-react';
import {
  importTranscript,
  searchCourses,
  type CourseCatalogRecord,
  type TranscriptImportCourse,
  type TranscriptImportResponse,
} from '../api';
import { getCourseAvailabilityInfo } from '../utils/courseAvailability';
import { MIN_CREDITS_PER_TERM } from '../constants/academic';
import type { ManualCreditEntry } from '../types';
import {
  TranscriptImportReviewDialog,
  type TranscriptImportReviewEntry,
} from './TranscriptImportReviewDialog';

const BUSINESS_CONCENTRATION_OPTIONS = [
  'General',
  'Accounting',
  'Finance',
  'Marketing',
  'Management',
  'Tourism and Hospitality'
] as const;

type TranscriptImportPhase = 'idle' | 'uploading' | 'extracting' | 'matching' | 'ready' | 'error';

const TRANSCRIPT_ACCEPT = '.pdf,.png,.jpg,.jpeg';
const SUPPORTED_TRANSCRIPT_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg'];

const buildTranscriptReviewEntries = (response: TranscriptImportResponse): TranscriptImportReviewEntry[] => {
  const toEntry = (course: TranscriptImportCourse, index: number): TranscriptImportReviewEntry => ({
    reviewId: `${course.status}:${course.matched_code ?? course.raw_code}:${course.term ?? 'none'}:${index}`,
    rawCode: course.raw_code,
    matchedCode: course.matched_code ?? null,
    title: course.title ?? null,
    rawTitle: course.raw_title ?? null,
    status: course.status,
    term: course.term ?? null,
    confidence: course.confidence,
    matchedConfidently: course.matched_confidently,
    matchCandidates: course.match_candidates ?? [],
  });

  return [...response.completed, ...response.in_progress].map(toEntry);
};

const transcriptStatusLabel = (phase: TranscriptImportPhase) => {
  switch (phase) {
    case 'uploading':
      return 'Uploading transcript...';
    case 'extracting':
      return 'Extracting transcript data...';
    case 'matching':
      return 'Matching courses...';
    case 'ready':
      return 'Ready for review.';
    case 'error':
      return null;
    default:
      return null;
  }
};

interface AcademicSetupScreenProps {
  catalogId?: string;
  catalogYear?: string;
  majors: string[];
  minors: string[];
  courses: Record<string, string>; // code -> title
  courseMeta?: Record<string, {
    credits?: number;
    prereq_text?: string | null;
    prereq_codes?: string[];
    prereqs?: string[];
  }>;
  onComplete: (data: {
    majors: string[];
    minors: string[];
    businessConcentration: string | null;
    economicsIntermediateChoice: "ECO 3001" | "ECO 3002" | null;
    completedCourses: string[];
    inProgressCourses: string[];
    manualCredits: ManualCreditEntry[];
    inProgressOverrides?: Record<string, string>;
    completedOverrides?: Record<string, string>;
    lastRolloverTermApplied?: string;
    maxCreditsPerSemester: number;
    startTermSeason: string;
    startTermYear: number;
    waivedMat1000: boolean;
    waivedEng1000: boolean;
  }) => void;
  onBack: () => void;
}

export function AcademicSetupScreen({
  catalogId,
  catalogYear,
  majors,
  minors,
  courses,
  courseMeta,
  onComplete,
  onBack
}: AcademicSetupScreenProps) {
  const MAX_CREDITS_PER_TERM = 20;
  const MAX_PROGRAMS_PER_TYPE = 2;
  const [step, setStep] = useState<1 | 2>(1);
  const [selectedMajors, setSelectedMajors] = useState<string[]>([]);
  const [selectedMinors, setSelectedMinors] = useState<string[]>([]);
  const [businessConcentration, setBusinessConcentration] = useState<string>('General');
  const [economicsIntermediateChoice, setEconomicsIntermediateChoice] = useState<"ECO 3001" | "ECO 3002" | null>(null);
  const [maxCreditsPerSemester, setMaxCreditsPerSemester] = useState(17);
  const [maxCreditsInput, setMaxCreditsInput] = useState('17');
  const [waivedMat1000, setWaivedMat1000] = useState(false);
  const [waivedEng1000, setWaivedEng1000] = useState(false);
  const [completedCourses, setCompletedCourses] = useState<string[]>([]);
  const [courseQuery, setCourseQuery] = useState('');
  const [courseSearchResults, setCourseSearchResults] = useState<CourseCatalogRecord[]>([]);
  const [courseSearchLoading, setCourseSearchLoading] = useState(false);
  const [courseSearchError, setCourseSearchError] = useState<string | null>(null);
  const [courseLookupByCode, setCourseLookupByCode] = useState<Record<string, CourseCatalogRecord>>({});
  const [importedCompletedCourses, setImportedCompletedCourses] = useState<string[]>([]);
  const [importedInProgressCourses, setImportedInProgressCourses] = useState<string[]>([]);
  const [importedCompletedTerms, setImportedCompletedTerms] = useState<Record<string, string>>({});
  const [importedInProgressTerms, setImportedInProgressTerms] = useState<Record<string, string>>({});
  const [transcriptImportPhase, setTranscriptImportPhase] = useState<TranscriptImportPhase>('idle');
  const [transcriptImportError, setTranscriptImportError] = useState<string | null>(null);
  const [transcriptImportWarnings, setTranscriptImportWarnings] = useState<string[]>([]);
  const [selectedTranscriptName, setSelectedTranscriptName] = useState<string | null>(null);
  const [isTranscriptDragging, setIsTranscriptDragging] = useState(false);
  const [transcriptReviewEntries, setTranscriptReviewEntries] = useState<TranscriptImportReviewEntry[]>([]);
  const [isTranscriptReviewOpen, setIsTranscriptReviewOpen] = useState(false);
  const [programConflictMsg, setProgramConflictMsg] = useState<string | null>(null);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const transcriptInputRef = useRef<HTMLInputElement | null>(null);
  const transcriptPhaseTimersRef = useRef<number[]>([]);

  const termOptions = useMemo(() => {
    const today = new Date();
    const month = today.getMonth() + 1;
    let season = month <= 5 ? "Spring" : "Fall";
    let year = today.getFullYear();
    const options: { label: string; value: string; season: string; year: number }[] = [];
    const backTerms = 6;
    const buildTerm = (s: string, y: number) => ({ label: `${s} ${y}`, value: `${s} ${y}`, season: s, year: y });
    const temp: { label: string; value: string; season: string; year: number }[] = [buildTerm(season, year)];
    let s = season;
    let y = year;
    const past: { label: string; value: string; season: string; year: number }[] = [];
    for (let i = 0; i < backTerms; i += 1) {
      if (s === "Spring") {
        s = "Fall";
        y -= 1;
      } else {
        s = "Spring";
      }
      past.push(buildTerm(s, y));
    }
    return [...past.reverse(), ...temp];
  }, []);

  const [startTermValue, setStartTermValue] = useState(termOptions[0]?.value ?? "");
  const selectedStartTerm = termOptions.find((t) => t.value === startTermValue) ?? termOptions[0];
  const currentTerm = termOptions[termOptions.length - 1];
  const currentTermLabel = currentTerm?.label ?? null;

  const canToggleMajor = (m: string) =>
    selectedMajors.includes(m) || selectedMajors.length < MAX_PROGRAMS_PER_TYPE;

  const canToggleMinor = (m: string) =>
    !selectedMajors.includes(m) && (selectedMinors.includes(m) || selectedMinors.length < MAX_PROGRAMS_PER_TYPE);

  const economicsMinorSelected = selectedMinors.includes("Economics");
  const businessMajorSelected = selectedMajors.includes("Business Administration");
  const marketingImcConflict =
    businessMajorSelected
    && businessConcentration === 'Marketing'
    && selectedMinors.includes('Integrated Marketing Communications');
  const canSubmit =
    selectedMajors.length > 0
    && (!economicsMinorSelected || economicsIntermediateChoice !== null)
    && !marketingImcConflict;

  const availableMinors = useMemo(
    () => minors.filter((m) => !selectedMajors.includes(m)),
    [minors, selectedMajors]
  );

  const showProgramConflict = (msg: string) => {
    setProgramConflictMsg(msg);
    window.setTimeout(() => setProgramConflictMsg(null), 2500);
  };

  const handleToggleMajor = (major: string) => {
    if (selectedMajors.includes(major)) {
      setSelectedMajors((prev) => {
        const next = prev.filter((m) => m !== major);
        if (!next.includes('Business Administration')) {
          setBusinessConcentration('General');
        }
        return next;
      });
      return;
    }
    if (!canToggleMajor(major)) return;
    const wasSelectedAsMinor = selectedMinors.includes(major);
    setSelectedMajors((prev) => [...prev, major]);
    if (wasSelectedAsMinor) {
      setSelectedMinors((prev) => prev.filter((m) => m !== major));
      if (major === "Economics") {
        setEconomicsIntermediateChoice(null);
      }
      showProgramConflict(`${major} was removed from minors because it is now a major.`);
    }
  };

  const handleToggleMinor = (minor: string) => {
    if (selectedMajors.includes(minor)) return;
    if (selectedMinors.includes(minor)) {
      setSelectedMinors((prev) => prev.filter((m) => m !== minor));
      if (minor === "Economics") {
        setEconomicsIntermediateChoice(null);
      }
      return;
    }
    if (!canToggleMinor(minor)) return;
    setSelectedMinors((prev) => [...prev, minor]);
  };

  const commitCreditsInput = (rawInput: string) => {
    const trimmed = rawInput.trim();
    if (!trimmed) {
      setMaxCreditsInput(String(maxCreditsPerSemester));
      return;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
      setMaxCreditsInput(String(maxCreditsPerSemester));
      return;
    }
    const clamped = Math.max(MIN_CREDITS_PER_TERM, Math.min(MAX_CREDITS_PER_TERM, parsed));
    setMaxCreditsPerSemester(clamped);
    setMaxCreditsInput(String(clamped));
  };

  useEffect(() => {
    setMaxCreditsInput(String(maxCreditsPerSemester));
  }, [maxCreditsPerSemester]);

  const termIndex = (season: string, year: number) => year * 2 + (season === "Fall" ? 1 : 0);
  const termsCompleted = useMemo(() => {
    if (!selectedStartTerm || !currentTerm) return 1;
    const startIdx = termIndex(selectedStartTerm.season, selectedStartTerm.year);
    const currentIdx = termIndex(currentTerm.season, currentTerm.year);
    return Math.max(0, currentIdx - startIdx);
  }, [selectedStartTerm, currentTerm]);

  const normalizeCourseCode = (code: string) => code.replace(/\s+/g, ' ').trim().toUpperCase();

  const courseCredit = (code: string) => {
    const excelCredits = courseLookupByCode[code]?.credits;
    if (typeof excelCredits === 'number' && Number.isFinite(excelCredits) && excelCredits > 0) {
      return excelCredits;
    }
    return courseMeta?.[code]?.credits ?? 3;
  };

  const { completedForPlan: manualCompletedForPlan, inProgressCourses: manualInProgressCourses } = useMemo(() => {
    const threshold = maxCreditsPerSemester * termsCompleted;
    let running = 0;
    const completed: string[] = [];
    const inProgress: string[] = [];
    for (const code of completedCourses) {
      const credits = courseCredit(code);
      if (running + credits <= threshold) {
        completed.push(code);
        running += credits;
      } else {
        inProgress.push(code);
      }
    }
    return { completedForPlan: completed, inProgressCourses: inProgress };
  }, [completedCourses, maxCreditsPerSemester, termsCompleted, courseMeta, courseLookupByCode]);

  const { completedForPlan, inProgressCourses } = useMemo(() => {
    const importedCompletedSet = new Set(importedCompletedCourses.map(normalizeCourseCode));
    const importedInProgressSet = new Set(importedInProgressCourses.map(normalizeCourseCode));

    const adjustedManualCompleted = manualCompletedForPlan.filter((code) => !importedInProgressSet.has(code));
    const adjustedManualInProgress = manualInProgressCourses.filter((code) => !importedCompletedSet.has(code));

    const nextInProgress = Array.from(new Set([...adjustedManualInProgress, ...importedInProgressCourses]));
    const nextInProgressSet = new Set(nextInProgress.map(normalizeCourseCode));
    const nextCompleted = Array.from(new Set([...adjustedManualCompleted, ...importedCompletedCourses])).filter(
      (code) => !nextInProgressSet.has(normalizeCourseCode(code))
    );

    return {
      completedForPlan: nextCompleted,
      inProgressCourses: nextInProgress,
    };
  }, [
    importedCompletedCourses,
    importedInProgressCourses,
    manualCompletedForPlan,
    manualInProgressCourses,
  ]);

  const economicsTrackEstimate = useMemo(() => {
    const progressPool = new Set(
      [...completedForPlan, ...inProgressCourses]
        .filter((code) => typeof code === 'string' && code.trim().length > 0)
        .map(normalizeCourseCode)
    );
    const excludedElectiveCodes = new Set(["ECO 1001", "ECO 1002", "ECO 3001", "ECO 3002"]);

    const estimateFor = (trackCode: "ECO 3001" | "ECO 3002") => {
      const requiredCore = ["ECO 1001", "ECO 1002", trackCode].map(normalizeCourseCode);
      const missingCoreCount = requiredCore.filter((code) => !progressPool.has(code)).length;
      const optionMissing = progressPool.has(normalizeCourseCode(trackCode)) ? 0 : 1;

      let earnedElectiveCredits = 0;
      for (const code of progressPool) {
        if (!code.startsWith("ECO ")) continue;
        if (excludedElectiveCodes.has(code)) continue;
        earnedElectiveCredits += courseCredit(code);
      }

      const electiveCreditsRemaining = Math.max(0, 9 - earnedElectiveCredits);
      const electiveCourseEstimate = Math.ceil(electiveCreditsRemaining / 3);

      return {
        totalRemainingCourses: missingCoreCount + electiveCourseEstimate,
        optionMissing,
      };
    };

    return {
      eco3001: estimateFor("ECO 3001"),
      eco3002: estimateFor("ECO 3002"),
    };
  }, [completedForPlan, inProgressCourses, courseMeta, courseLookupByCode]);

  const economicsTrackPrereqs = useMemo(() => {
    const directCodesFor = (courseCode: string): string[] => {
      const meta = courseMeta?.[courseCode];
      const raw = Array.isArray(meta?.prereq_codes)
        ? meta.prereq_codes
        : (Array.isArray(meta?.prereqs) ? meta.prereqs : []);
      const out: string[] = [];
      const seen = new Set<string>();
      for (const code of raw) {
        if (typeof code !== 'string' || !code.trim()) continue;
        const normalized = normalizeCourseCode(code);
        if (seen.has(normalized)) continue;
        seen.add(normalized);
        out.push(normalized);
      }
      return out;
    };

    const directTextFor = (courseCode: string): string | null => {
      const raw = courseMeta?.[courseCode]?.prereq_text;
      if (typeof raw !== 'string') return null;
      const cleaned = raw.trim();
      return cleaned.length > 0 ? cleaned : null;
    };

    const allCodesFor = (courseCode: string): string[] => {
      const ordered: string[] = [];
      const seen = new Set<string>();
      const queue = [...directCodesFor(courseCode)];
      while (queue.length > 0) {
        const next = queue.shift()!;
        if (seen.has(next)) continue;
        seen.add(next);
        ordered.push(next);
        for (const nested of directCodesFor(next)) {
          if (!seen.has(nested)) queue.push(nested);
        }
      }
      return ordered;
    };

    const build = (courseCode: "ECO 3001" | "ECO 3002") => ({
      directText: directTextFor(courseCode),
      allCodes: allCodesFor(courseCode),
    });

    return {
      eco3001: build("ECO 3001"),
      eco3002: build("ECO 3002"),
    };
  }, [courseMeta]);

  const searchContext = useMemo(
    () => ({
      catalogId,
      majors: selectedMajors,
      minors: selectedMinors,
      businessConcentration: businessMajorSelected ? businessConcentration : null,
    }),
    [businessConcentration, businessMajorSelected, catalogId, selectedMajors, selectedMinors]
  );

  useEffect(() => () => {
    transcriptPhaseTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    transcriptPhaseTimersRef.current = [];
  }, []);

  const clearTranscriptPhaseTimers = () => {
    transcriptPhaseTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    transcriptPhaseTimersRef.current = [];
  };

  const queueTranscriptPhaseSequence = () => {
    clearTranscriptPhaseTimers();
    setTranscriptImportPhase('uploading');
    transcriptPhaseTimersRef.current = [
      window.setTimeout(() => setTranscriptImportPhase('extracting'), 250),
      window.setTimeout(() => setTranscriptImportPhase('matching'), 900),
    ];
  };

  const isSupportedTranscriptFile = (file: File) =>
    SUPPORTED_TRANSCRIPT_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension));

  const handleConfirmTranscriptImport = () => {
    const nextCompleted = new Set(importedCompletedCourses.map(normalizeCourseCode));
    const nextInProgress = new Set(importedInProgressCourses.map(normalizeCourseCode));
    const nextCompletedTerms = { ...importedCompletedTerms };
    const nextInProgressTerms = { ...importedInProgressTerms };

    transcriptReviewEntries.forEach((entry) => {
      const code = entry.matchedCode ? normalizeCourseCode(entry.matchedCode) : '';
      if (!code) return;

      if (entry.status === 'in_progress') {
        nextCompleted.delete(code);
        delete nextCompletedTerms[code];
        nextInProgress.add(code);
        if (entry.term) {
          nextInProgressTerms[code] = entry.term;
        } else if (currentTermLabel) {
          nextInProgressTerms[code] = currentTermLabel;
        }
        return;
      }

      nextInProgress.delete(code);
      delete nextInProgressTerms[code];
      nextCompleted.add(code);
      if (entry.term) {
        nextCompletedTerms[code] = entry.term;
      } else {
        delete nextCompletedTerms[code];
      }
    });

    setImportedCompletedCourses(Array.from(nextCompleted));
    setImportedInProgressCourses(Array.from(nextInProgress));
    setImportedCompletedTerms(
      Object.fromEntries(Object.entries(nextCompletedTerms).filter(([code]) => nextCompleted.has(code)))
    );
    setImportedInProgressTerms(
      Object.fromEntries(Object.entries(nextInProgressTerms).filter(([code]) => nextInProgress.has(code)))
    );
    setTranscriptImportWarnings([]);
    setTranscriptReviewEntries([]);
    setIsTranscriptReviewOpen(false);
    setTranscriptImportPhase('idle');
  };

  const handleCancelTranscriptImport = () => {
    setTranscriptImportWarnings([]);
    setTranscriptReviewEntries([]);
    setIsTranscriptReviewOpen(false);
    setTranscriptImportPhase('idle');
  };

  const handleTranscriptFile = async (file: File | null) => {
    if (!file) return;
    if (!isSupportedTranscriptFile(file)) {
      setTranscriptImportError('Unsupported file type. Please upload a PDF, PNG, JPG, or JPEG transcript.');
      setTranscriptImportPhase('error');
      return;
    }

    setTranscriptImportError(null);
    setTranscriptImportWarnings([]);
    setSelectedTranscriptName(file.name);
    queueTranscriptPhaseSequence();

    try {
      const response = await importTranscript(file, catalogId);
      clearTranscriptPhaseTimers();
      const nextEntries = buildTranscriptReviewEntries(response);
      if (nextEntries.length === 0) {
        throw new Error('No course rows could be detected from this file. Please try another transcript or add courses manually.');
      }
      setTranscriptImportWarnings(response.warnings ?? []);
      setTranscriptReviewEntries(nextEntries);
      setTranscriptImportPhase('ready');
      setIsTranscriptReviewOpen(true);
    } catch (error: any) {
      clearTranscriptPhaseTimers();
      setTranscriptImportError(
        error?.message ?? 'No course rows could be detected from this file. Please try another transcript or add courses manually.'
      );
      setTranscriptImportPhase('error');
    }
  };

  const handleSubmit = () => {
    if (!canSubmit) return;

    const importedCompletedSet = new Set(importedCompletedCourses.map(normalizeCourseCode));
    const manualExplicitInProgress = manualInProgressCourses.filter((code) => !importedCompletedSet.has(code));
    const nextInProgressOverrides = currentTermLabel
      ? manualExplicitInProgress.reduce<Record<string, string>>((acc, code) => {
          acc[code] = currentTermLabel;
          return acc;
        }, {})
      : {};

    Object.entries(importedInProgressTerms).forEach(([code, term]) => {
      if (inProgressCourses.includes(code) && term) {
        nextInProgressOverrides[code] = term;
      }
    });

    onComplete({
      majors: selectedMajors,
      minors: selectedMinors,
      businessConcentration: businessMajorSelected ? businessConcentration : null,
      economicsIntermediateChoice,
      completedCourses: completedForPlan,
      inProgressCourses,
      manualCredits: [],
      inProgressOverrides: nextInProgressOverrides,
      completedOverrides: Object.fromEntries(
        Object.entries(importedCompletedTerms).filter(([code]) => completedForPlan.includes(code))
      ),
      lastRolloverTermApplied: currentTermLabel ?? undefined,
      maxCreditsPerSemester,
      startTermSeason: selectedStartTerm?.season ?? "Fall",
      startTermYear: selectedStartTerm?.year ?? new Date().getFullYear(),
      waivedMat1000,
      waivedEng1000
    });
  };

  const normalizeCode = (code: string) => code.replace(/\s+/g, '').toLowerCase();
  const queryNormalized = useMemo(() => courseQuery.trim(), [courseQuery]);
  const canSearch = queryNormalized.length >= 2;
  const rankedCourseEntries = courseSearchResults;
  const dropdownOpen = queryNormalized.length > 0;

  useEffect(() => {
    if (!canSearch) {
      setCourseSearchResults([]);
      setCourseSearchError(null);
      setCourseSearchLoading(false);
      return;
    }

    let cancelled = false;
    setCourseSearchLoading(true);
    setCourseSearchError(null);

    const timer = window.setTimeout(async () => {
      try {
        const results = await searchCourses(queryNormalized, undefined, 20, searchContext);
        if (cancelled) return;
        setCourseSearchResults(results);
        setCourseLookupByCode((prev) => {
          const next = { ...prev };
          for (const result of results) {
            if (result?.code) next[result.code] = result;
          }
          return next;
        });
      } catch (error: any) {
        if (cancelled) return;
        const fallbackQuery = queryNormalized.toLowerCase().replace(/\s+/g, '');
        const fallback = Object.entries(courses)
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
          .map((entry) => ({
            code: entry.code,
            title: entry.title,
            credits: courseMeta?.[entry.code]?.credits ?? 3,
            gen_ed_tags: [],
          } as CourseCatalogRecord));
        setCourseSearchResults(fallback);
        setCourseSearchError(error?.message ?? 'Course search failed. Showing fallback results.');
      } finally {
        if (!cancelled) setCourseSearchLoading(false);
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [canSearch, queryNormalized, courses, courseMeta, searchContext]);

  useEffect(() => {
    if (!dropdownOpen) {
      setHighlightedIndex(-1);
      return;
    }
    setHighlightedIndex((prev) => (prev < 0 || prev >= rankedCourseEntries.length ? 0 : prev));
  }, [dropdownOpen, rankedCourseEntries.length]);

  useEffect(() => {
    if (highlightedIndex < 0) return;
    const el = optionRefs.current[highlightedIndex];
    if (el) {
      el.scrollIntoView({ block: 'nearest' });
    }
  }, [highlightedIndex]);

  const handleSelectCourse = (course: CourseCatalogRecord) => {
    const code = course.code;
    setCompletedCourses((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
    setCourseLookupByCode((prev) => ({ ...prev, [code]: course }));
    setCourseQuery('');
    setHighlightedIndex(-1);
  };

  const handleCourseKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setCourseQuery('');
      setHighlightedIndex(-1);
      return;
    }

    if (!rankedCourseEntries.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < 0 ? 0 : (prev + 1) % rankedCourseEntries.length));
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) =>
        prev < 0 ? rankedCourseEntries.length - 1 : (prev - 1 + rankedCourseEntries.length) % rankedCourseEntries.length
      );
      return;
    }

    if (e.key === 'Enter') {
      if (highlightedIndex < 0 || highlightedIndex >= rankedCourseEntries.length) return;
      e.preventDefault();
      handleSelectCourse(rankedCourseEntries[highlightedIndex]);
      return;
    }

  };

  const handleRemoveTranscriptReviewEntry = (reviewId: string) => {
    setTranscriptReviewEntries((prev) => prev.filter((entry) => entry.reviewId !== reviewId));
  };

  const handleUpdateTranscriptReviewStatus = (
    reviewId: string,
    nextStatus: 'completed' | 'in_progress'
  ) => {
    setTranscriptReviewEntries((prev) =>
      prev.map((entry) => {
        if (entry.reviewId !== reviewId) return entry;
        if (entry.status === nextStatus) return entry;
        return {
          ...entry,
          status: nextStatus,
          term:
            nextStatus === 'in_progress'
              ? currentTermLabel ?? entry.term ?? null
              : entry.term,
        };
      })
    );
  };

  const handleUpdateTranscriptReviewMatch = (
    reviewId: string,
    nextMatch: {
      code: string;
      title: string;
      confidence: number;
      matchedConfidently: boolean;
      matchCandidates?: Array<{ code: string; title: string; confidence: number }>;
    } | null
  ) => {
    setTranscriptReviewEntries((prev) =>
      prev.map((entry) => {
        if (entry.reviewId !== reviewId) return entry;
        if (!nextMatch) {
          return {
            ...entry,
            matchedCode: null,
            matchedConfidently: false,
            title: entry.rawTitle ?? entry.title,
          };
        }
        return {
          ...entry,
          matchedCode: nextMatch.code,
          title: nextMatch.title,
          confidence: nextMatch.confidence,
          matchedConfidently: nextMatch.matchedConfidently,
          matchCandidates: nextMatch.matchCandidates ?? entry.matchCandidates,
        };
      })
    );
  };

  const removeImportedCompletedCourse = (code: string) => {
    setImportedCompletedCourses((prev) => prev.filter((courseCode) => courseCode !== code));
    setImportedCompletedTerms((prev) => {
      const next = { ...prev };
      delete next[code];
      return next;
    });
  };

  const removeImportedInProgressCourse = (code: string) => {
    setImportedInProgressCourses((prev) => prev.filter((courseCode) => courseCode !== code));
    setImportedInProgressTerms((prev) => {
      const next = { ...prev };
      delete next[code];
      return next;
    });
  };

  return (
    <div className="min-h-screen py-12 px-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border"
            style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          {catalogYear && (
            <div className="text-sm px-3 py-2 rounded-lg border" style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}>
              Catalog: <b>AY {catalogYear}</b>
            </div>
          )}
        </div>

        <div className="text-center mb-10">
          <h2 className="mb-2">Academic Setup</h2>
          <p style={{ color: 'var(--neutral-dark)' }}>
            We will collect a few details so the plan is tailored to your start term and completed courses.
          </p>
        </div>

        {step === 1 && (
          <div className="grid gap-6">
            {/* Waivers */}
            <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
              <h3 className="mb-3">Foundation Course Waivers</h3>
              <p className="text-sm mb-4" style={{ color: 'var(--neutral-dark)' }}>
                Check a box only if AUBG officially waived that course for you and you do not need to take it. Leave it unchecked if you still need to complete the course.
              </p>
              <div className="grid md:grid-cols-2 gap-2">
                <label className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer"
                  style={{ borderColor: waivedMat1000 ? 'var(--academic-gold)' : 'var(--neutral-border)' }}
                >
                  <input
                    type="checkbox"
                    checked={waivedMat1000}
                    onChange={() => setWaivedMat1000(prev => !prev)}
                  />
                  <span>I have a waiver for MAT 1000</span>
                </label>
                <label className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer"
                  style={{ borderColor: waivedEng1000 ? 'var(--academic-gold)' : 'var(--neutral-border)' }}
                >
                  <input
                    type="checkbox"
                    checked={waivedEng1000}
                    onChange={() => setWaivedEng1000(prev => !prev)}
                  />
                  <span>I have a waiver for ENG 1000</span>
                </label>
              </div>
            </div>

            {/* Start term */}
            <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
              <h3 className="mb-3">First semester at AUBG</h3>
              <p className="text-sm mb-4" style={{ color: 'var(--neutral-dark)' }}>
                Select the semester you started studying.
              </p>
              <div className="max-w-xs">
                <select
                  className="w-full px-3 py-2 rounded-lg border"
                  style={{ borderColor: 'var(--neutral-border)' }}
                  value={startTermValue}
                  onChange={(e) => setStartTermValue(e.target.value)}
                >
                  {termOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Majors */}
            <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
              <h3 className="mb-4">Select Major(s)</h3>
              <p className="text-sm mb-4" style={{ color: 'var(--neutral-dark)' }}>
                You can choose more than one major.
              </p>

              <div className="grid md:grid-cols-2 gap-2">
                {majors.map(m => (
                  <label key={m} className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer"
                    style={{ borderColor: selectedMajors.includes(m) ? 'var(--academic-gold)' : 'var(--neutral-border)' }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedMajors.includes(m)}
                      disabled={!canToggleMajor(m)}
                      onChange={() => handleToggleMajor(m)}
                    />
                    <span>{m}</span>
                  </label>
                ))}
              </div>
            </div>

            {businessMajorSelected && (
              <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
                <h3 className="mb-3">Business Concentration</h3>
                <p className="text-sm mb-4" style={{ color: 'var(--neutral-dark)' }}>
                  Keep Business Administration as one shared major and apply concentration-specific audit, search labels, and recommendations.
                </p>
                <div className="max-w-md">
                  <select
                    className="w-full px-3 py-2 rounded-lg border"
                    style={{ borderColor: 'var(--neutral-border)' }}
                    value={businessConcentration}
                    onChange={(e) => setBusinessConcentration(e.target.value)}
                  >
                    {BUSINESS_CONCENTRATION_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="text-xs mt-3" style={{ color: 'var(--neutral-dark)' }}>
                  General keeps the shared BUS core and broad BUS electives. Other choices add concentration-specific required and elective rules.
                </div>
              </div>
            )}

            {programConflictMsg && (
              <div
                className="px-4 py-3 rounded-xl border text-sm"
                style={{ background: 'var(--neutral-cream)', borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                role="status"
                aria-live="polite"
              >
                {programConflictMsg}
              </div>
            )}

            {/* Minors */}
            <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
              <h3 className="mb-4">Select Minor(s)</h3>
              <p className="text-sm mb-4" style={{ color: 'var(--neutral-dark)' }}>
                Optional - select any minors you want to pursue.
              </p>

              <div className="grid md:grid-cols-2 gap-2">
                {availableMinors.map(m => (
                  <label key={m} className="flex items-center gap-3 p-3 rounded-lg border cursor-pointer"
                    style={{ borderColor: selectedMinors.includes(m) ? 'var(--academic-gold)' : 'var(--neutral-border)' }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedMinors.includes(m)}
                      disabled={!canToggleMinor(m)}
                      onChange={() => handleToggleMinor(m)}
                    />
                    <span>{m}</span>
                  </label>
                ))}
              </div>
              {economicsMinorSelected && (
                <div className="mt-4 p-4 rounded-xl border" style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-cream)' }}>
                  <h4 className="mb-2">Economics Minor Choice</h4>
                  <p className="text-sm mb-3" style={{ color: 'var(--neutral-dark)' }}>
                    Choose one track before generating your plan.
                  </p>
                  <div className="grid gap-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="economics-intermediate-choice"
                        checked={economicsIntermediateChoice === "ECO 3001"}
                        onChange={() => setEconomicsIntermediateChoice("ECO 3001")}
                      />
                      <span>
                        Intermediate Microeconomics (ECO 3001)
                        <span className="block text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          Estimated remaining if selected: {economicsTrackEstimate.eco3001.totalRemainingCourses} course(s)
                          {" "}({economicsTrackEstimate.eco3001.optionMissing} from this option)
                        </span>
                        <span className="block text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          Prerequisite rule: {economicsTrackPrereqs.eco3001.directText ?? "None listed"}
                        </span>
                        <span className="block text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          All prerequisite courses: {economicsTrackPrereqs.eco3001.allCodes.length > 0 ? economicsTrackPrereqs.eco3001.allCodes.join(", ") : "None"}
                        </span>
                      </span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="economics-intermediate-choice"
                        checked={economicsIntermediateChoice === "ECO 3002"}
                        onChange={() => setEconomicsIntermediateChoice("ECO 3002")}
                      />
                      <span>
                        Intermediate Macroeconomics (ECO 3002)
                        <span className="block text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          Estimated remaining if selected: {economicsTrackEstimate.eco3002.totalRemainingCourses} course(s)
                          {" "}({economicsTrackEstimate.eco3002.optionMissing} from this option)
                        </span>
                        <span className="block text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          Prerequisite rule: {economicsTrackPrereqs.eco3002.directText ?? "None listed"}
                        </span>
                        <span className="block text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          All prerequisite courses: {economicsTrackPrereqs.eco3002.allCodes.length > 0 ? economicsTrackPrereqs.eco3002.allCodes.join(", ") : "None"}
                        </span>
                      </span>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {marketingImcConflict && (
              <div
                className="px-4 py-3 rounded-xl border text-sm"
                style={{ background: '#fff7ed', borderColor: '#fdba74', color: '#9a3412' }}
                role="alert"
              >
                Marketing concentration cannot be combined with IMC minor. Choose a different BUS concentration or remove the Integrated Marketing Communications minor.
              </div>
            )}

            {/* Max credits */}
            <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
              <h3 className="mb-3">Semester Load</h3>
              <label className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                Max credits per semester
              </label>
              <div className="mt-2 flex items-center gap-3">
                <input
                  type="number"
                  min={MIN_CREDITS_PER_TERM}
                  max={MAX_CREDITS_PER_TERM}
                  value={maxCreditsInput}
                  onChange={(e) => setMaxCreditsInput(e.target.value)}
                  onBlur={() => commitCreditsInput(maxCreditsInput)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      commitCreditsInput(maxCreditsInput);
                    }
                  }}
                  className="w-28 px-3 py-2 rounded-lg border"
                  style={{ borderColor: 'var(--neutral-border)' }}
                />
                <span className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                  Typical range is 14-20.
                </span>
              </div>
            </div>

            {/* Continue */}
            <div className="flex justify-end">
              <button
                onClick={() => setStep(2)}
                disabled={!canSubmit}
                className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold"
                style={{
                  backgroundColor: canSubmit ? 'var(--academic-gold)' : 'var(--neutral-border)',
                  color: canSubmit ? 'var(--navy-dark)' : 'var(--neutral-dark)',
                  cursor: canSubmit ? 'pointer' : 'not-allowed'
                }}
              >
                Continue
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="grid gap-6">
            {/* Completed courses */}
            <div className="p-6 rounded-2xl border" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
              <h3 className="mb-3">Completed Courses</h3>
              <p className="text-sm mb-4" style={{ color: 'var(--neutral-dark)' }}>
                Search the entire catalog, import a transcript, or use both together. You can review and edit everything before continuing.
              </p>
              <input
                value={courseQuery}
                onChange={(e) => setCourseQuery(e.target.value)}
                onKeyDown={handleCourseKeyDown}
                placeholder="Search the full catalog (code or title)"
                className="w-full px-4 py-3 rounded-lg border"
                style={{ borderColor: 'var(--neutral-border)' }}
                role="combobox"
                aria-expanded={dropdownOpen}
                aria-controls="completed-course-options"
                aria-activedescendant={
                  highlightedIndex >= 0 && highlightedIndex < rankedCourseEntries.length
                    ? `completed-course-option-${normalizeCode(rankedCourseEntries[highlightedIndex].code)}`
                    : undefined
                }
                aria-autocomplete="list"
              />

              {queryNormalized && (
                <div
                  id="completed-course-options"
                  role="listbox"
                  className="mt-3 max-h-64 overflow-y-auto grid gap-2"
                >
                  {!canSearch && queryNormalized.length > 0 && (
                    <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      Type at least 2 characters.
                    </div>
                  )}
                  {canSearch && courseSearchLoading && (
                    <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      Searching courses...
                    </div>
                  )}
                  {canSearch && !courseSearchLoading && courseSearchError && (
                    <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      {courseSearchError}
                    </div>
                  )}
                  {canSearch && !courseSearchLoading && !courseSearchError && rankedCourseEntries.length === 0 && (
                    <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      No matching courses.
                    </div>
                  )}
                  {rankedCourseEntries.map((entry, idx) => {
                    const code = entry.code;
                    const title = entry.title;
                    const selected = completedCourses.includes(code);
                    const credits = typeof entry.credits === 'number' && entry.credits > 0
                      ? entry.credits
                      : courseCredit(code);
                    const genEdTags = (entry.gen_ed_tags ?? []).filter((tag) => typeof tag === 'string' && tag.trim().length > 0);
                    const businessBadges = (entry.business_classification?.badges ?? []).filter(
                      (badge): badge is string =>
                        typeof badge === 'string'
                        && badge.trim().length > 0
                        && badge !== 'Required for BUS Core'
                        && badge !== 'Counts as BUS elective'
                    );
                    const availability = getCourseAvailabilityInfo(entry, {
                      mode: "completed",
                      isExcelOnly: entry.is_excel_only === true,
                      currentTermLabel
                    });
                    const hasWarning = Boolean(availability.warningLabel);
                    const isActive = idx === highlightedIndex;
                    const borderColor = isActive
                      ? 'var(--academic-gold)'
                      : selected
                        ? 'var(--academic-gold)'
                        : 'var(--neutral-border)';
                    return (
                      <button
                        key={code}
                        type="button"
                        id={`completed-course-option-${normalizeCode(code)}`}
                        role="option"
                        aria-selected={isActive || selected}
                        ref={(el) => {
                          optionRefs.current[idx] = el;
                        }}
                        onMouseEnter={() => setHighlightedIndex(idx)}
                        onClick={() => handleSelectCourse(entry)}
                        className="text-left p-3 rounded-lg border hover:shadow-sm cursor-pointer"
                        title={
                          hasWarning
                            ? `${availability.warningLabel}. ${availability.detailsLabel}`
                            : undefined
                        }
                        style={{
                          borderColor,
                          background: isActive ? 'var(--neutral-cream)' : 'var(--white)'
                        }}
                      >
                        <div className="flex items-start justify-between gap-2">
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
                        {businessBadges.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {businessBadges.map((badge) => (
                              <span
                                key={`${code}:${badge}`}
                                className="text-[10px] leading-4 px-2 py-0.5 rounded-lg border"
                                style={{
                                  borderColor: 'var(--neutral-border)',
                                  background: '#f8fafc',
                                  color: 'var(--navy-dark)'
                                }}
                              >
                                {badge}
                              </span>
                            ))}
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
                      </button>
                    );
                  })}
                </div>
              )}

              {completedCourses.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
                    Selected courses (completed + in progress):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {completedCourses.map((code) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => setCompletedCourses(prev => prev.filter(c => c !== code))}
                        className="px-3 py-1 rounded-full text-sm border"
                        style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-gray)' }}
                        title="Remove"
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {manualInProgressCourses.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
                    Currently taking (auto-detected):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {manualInProgressCourses.map((code) => (
                      <div
                        key={code}
                        className="px-3 py-1 rounded-full text-sm border"
                        style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                      >
                        {code}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="my-6 flex items-center gap-4" aria-hidden="true">
                <div className="h-px flex-1" style={{ background: 'var(--neutral-border)' }} />
                <span className="text-xs uppercase tracking-[0.2em]" style={{ color: 'var(--neutral-dark)' }}>
                  or import from transcript
                </span>
                <div className="h-px flex-1" style={{ background: 'var(--neutral-border)' }} />
              </div>

              <div
                className="p-5 rounded-2xl border"
                style={{
                  borderColor: isTranscriptDragging ? 'var(--academic-gold)' : 'var(--neutral-border)',
                  background: isTranscriptDragging ? 'var(--neutral-cream)' : '#fcfcfd',
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsTranscriptDragging(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setIsTranscriptDragging(false);
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  setIsTranscriptDragging(false);
                  const file = event.dataTransfer.files?.[0] ?? null;
                  void handleTranscriptFile(file);
                }}
              >
                <div className="font-medium">Upload Transcript (PDF or Image)</div>
                <div className="text-sm mt-1" style={{ color: 'var(--neutral-dark)' }}>
                  Accepted formats: PDF, PNG, JPG, JPEG
                </div>
                <div className="text-sm mt-2" style={{ color: 'var(--neutral-dark)' }}>
                  Upload an official or unofficial transcript to auto-fill completed and in-progress courses. You can still edit everything manually afterward.
                </div>
                <input
                  ref={transcriptInputRef}
                  type="file"
                  accept={TRANSCRIPT_ACCEPT}
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    void handleTranscriptFile(file);
                    event.target.value = '';
                  }}
                />
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => transcriptInputRef.current?.click()}
                    className="px-4 py-2 rounded-lg font-medium"
                    style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                  >
                    Choose File
                  </button>
                  <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                    or drag and drop a transcript here
                  </div>
                </div>
                {selectedTranscriptName && (
                  <div className="text-sm mt-3" style={{ color: 'var(--neutral-dark)' }}>
                    Selected file: {selectedTranscriptName}
                  </div>
                )}
                {transcriptStatusLabel(transcriptImportPhase) && (
                  <div className="text-sm mt-3" style={{ color: 'var(--neutral-dark)' }}>
                    {transcriptStatusLabel(transcriptImportPhase)}
                  </div>
                )}
                {transcriptImportError && (
                  <div
                    className="mt-3 px-4 py-3 rounded-xl border text-sm"
                    style={{ borderColor: '#fca5a5', background: '#fef2f2', color: '#b91c1c' }}
                    role="alert"
                  >
                    {transcriptImportError}
                  </div>
                )}
              </div>

              {importedCompletedCourses.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
                    Imported completed courses:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {importedCompletedCourses.map((code) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => removeImportedCompletedCourse(code)}
                        className="px-3 py-1 rounded-full text-sm border"
                        style={{ borderColor: 'var(--neutral-border)', background: '#eef6ff', color: 'var(--navy-dark)' }}
                        title="Remove imported course"
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {importedInProgressCourses.length > 0 && (
                <div className="mt-4">
                  <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
                    Imported in-progress courses:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {importedInProgressCourses.map((code) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => removeImportedInProgressCourse(code)}
                        className="px-3 py-1 rounded-full text-sm border"
                        style={{ borderColor: 'var(--neutral-border)', background: '#eff6ff', color: '#1d4ed8' }}
                        title="Remove imported in-progress course"
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Back/Continue */}
            <div className="flex justify-between">
              <button
                onClick={() => setStep(1)}
                className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold"
                style={{
                  backgroundColor: 'var(--white)',
                  color: 'var(--neutral-dark)',
                  border: '1px solid var(--neutral-border)'
                }}
              >
                <ArrowLeft className="w-5 h-5" />
                Back
              </button>
              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="flex items-center gap-2 px-6 py-3 rounded-xl font-semibold"
                style={{
                  backgroundColor: canSubmit ? 'var(--academic-gold)' : 'var(--neutral-border)',
                  color: canSubmit ? 'var(--navy-dark)' : 'var(--neutral-dark)',
                  cursor: canSubmit ? 'pointer' : 'not-allowed'
                }}
              >
                <CheckCircle2 className="w-5 h-5" />
                Continue
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        <TranscriptImportReviewDialog
          open={isTranscriptReviewOpen}
          entries={transcriptReviewEntries}
          warnings={transcriptImportWarnings}
          searchContext={searchContext}
          onCancel={handleCancelTranscriptImport}
          onConfirm={handleConfirmTranscriptImport}
          onRemove={handleRemoveTranscriptReviewEntry}
          onUpdateStatus={handleUpdateTranscriptReviewStatus}
          onUpdateMatch={handleUpdateTranscriptReviewMatch}
        />
      </div>
    </div>
  );
}

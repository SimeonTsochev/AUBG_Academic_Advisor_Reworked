import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowRight, ArrowLeft, FileUp, Info, Search, TriangleAlert } from 'lucide-react';
import {
  importTranscript,
  importTranscriptText,
  searchCourses,
  type CourseCatalogRecord,
  type TranscriptImportCourse,
  type TranscriptImportResponse,
} from '../api';
import { getCourseAvailabilityInfo, scheduleTermsFromCourseMeta } from '../utils/courseAvailability';
import { extractTranscriptLinesFromImage, extractTranscriptLinesFromPdf } from '../utils/transcriptOcr';
import { MAX_CREDITS_PER_TERM, MIN_CREDITS_PER_TERM } from '../constants/academic';
import type { FailedCourse, ManualCreditEntry } from '../types';
import {
  TranscriptImportReviewDialog,
  type TranscriptCourseStatus,
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
const IMAGE_TRANSCRIPT_EXTENSIONS = ['.png', '.jpg', '.jpeg'];

const buildTranscriptReviewEntries = (response: TranscriptImportResponse): TranscriptImportReviewEntry[] => {
  const toEntry = (course: TranscriptImportCourse, index: number): TranscriptImportReviewEntry => ({
    reviewId: `${course.status}:${course.matched_code ?? course.raw_code}:${course.term ?? 'none'}:${index}`,
    rawCode: course.raw_code,
    matchedCode: course.matched_code ?? null,
    title: course.title ?? null,
    rawTitle: course.raw_title ?? null,
    status: course.status,
    grade: course.grade ?? null,
    term: course.term ?? null,
    confidence: course.confidence,
    matchedConfidently: course.matched_confidently,
    matchCandidates: course.match_candidates ?? [],
  });

  return [...response.completed, ...response.in_progress, ...(response.failed ?? [])].map(toEntry);
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
    semester_availability?: string[];
  }>;
  onComplete: (data: {
    majors: string[];
    minors: string[];
    businessConcentration: string | null;
    economicsIntermediateChoice: "ECO 3001" | "ECO 3002" | null;
    completedCourses: string[];
    inProgressCourses: string[];
    failedCourses: FailedCourse[];
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
  // Not completed, so the plan schedules them again when a requirement still needs them.
  const [importedFailedCourses, setImportedFailedCourses] = useState<FailedCourse[]>([]);
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

  // Default to the current term (the last option); earlier options are for continuing students.
  const [startTermValue, setStartTermValue] = useState(termOptions[termOptions.length - 1]?.value ?? "");
  const selectedStartTerm = termOptions.find((t) => t.value === startTermValue) ?? termOptions[0];
  const currentTerm = termOptions[termOptions.length - 1];
  const currentTermLabel = currentTerm?.label ?? null;
  const scheduleTerms = useMemo(() => scheduleTermsFromCourseMeta(courseMeta), [courseMeta]);

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

  const isImageTranscriptFile = (file: File) =>
    IMAGE_TRANSCRIPT_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension));

  const handleConfirmTranscriptImport = () => {
    const nextCompleted = new Set(importedCompletedCourses.map(normalizeCourseCode));
    const nextInProgress = new Set(importedInProgressCourses.map(normalizeCourseCode));
    const nextFailed = new Map(importedFailedCourses.map((entry) => [entry.code, entry]));
    const nextCompletedTerms = { ...importedCompletedTerms };
    const nextInProgressTerms = { ...importedInProgressTerms };

    transcriptReviewEntries.forEach((entry) => {
      const code = entry.matchedCode ? normalizeCourseCode(entry.matchedCode) : '';
      if (!code) return;

      if (entry.status === 'failed') {
        nextCompleted.delete(code);
        delete nextCompletedTerms[code];
        nextInProgress.delete(code);
        delete nextInProgressTerms[code];
        nextFailed.set(code, { code, grade: entry.grade, term: entry.term });
        return;
      }
      nextFailed.delete(code);

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
    setImportedFailedCourses(Array.from(nextFailed.values()));
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
      const response = isImageTranscriptFile(file)
        ? await importTranscriptText(
            await extractTranscriptLinesFromImage(file),
            { usedOcr: true }
          )
        : await importTranscript(file, catalogId).catch(async (serverError) => {
            // No text layer (e.g. a browser "Print to PDF" transcript): OCR the pages here instead.
            const ocrLines = await extractTranscriptLinesFromPdf(file).catch(() => []);
            if (ocrLines.length === 0) throw serverError;
            return importTranscriptText(ocrLines, { usedOcr: true });
          });
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
      // A course added by hand as completed or in progress overrides an earlier failed attempt.
      failedCourses: importedFailedCourses.filter(
        (entry) => !completedForPlan.includes(entry.code) && !inProgressCourses.includes(entry.code)
      ),
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
    nextStatus: TranscriptCourseStatus
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
    <div className="setup-screen">
      <div className="setup-container">
        <div className="flex items-center justify-between gap-3">
          <button type="button" onClick={onBack} className="btn btn-outline btn-back btn-sm">
            <ArrowLeft aria-hidden="true" />
            <span>Back</span>
          </button>
          {catalogYear && <span className="badge badge-neutral">Catalog AY {catalogYear}</span>}
        </div>

        <header className="setup-header">
          <h1 className="setup-title">Academic setup</h1>
          <p className="muted">A few details so the plan fits your programs, start term and completed courses.</p>
          <ol className="steps" aria-label="Setup progress">
            {(['Programs', 'Completed courses'] as const).map((label, index) => {
              const number = (index + 1) as 1 | 2;
              const state = step === number ? 'current' : step > number ? 'done' : 'upcoming';
              return (
                <li key={label} className={`step is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
                  <span className="step-dot num">{number}</span>
                  <span>{label}</span>
                </li>
              );
            })}
          </ol>
        </header>

        {step === 1 && (
          <div className="stack-4">
            {/* Waivers */}
            <div className="card card-pad setup-card">
              <h2 className="section-title">Foundation Course Waivers</h2>
              <p className="section-subtitle setup-card-intro">
                Check a box only if AUBG officially waived that course for you and you do not need to take it. Leave it unchecked if you still need to complete the course.
              </p>
              <div className="grid-auto">
                <label className="select-tile">
                  <input
                    type="checkbox"
                    checked={waivedMat1000}
                    onChange={() => setWaivedMat1000(prev => !prev)}
                  />
                  <span>I have a waiver for MAT 1000</span>
                </label>
                <label className="select-tile">
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
            <div className="card card-pad setup-card">
              <h2 className="section-title">First semester at AUBG</h2>
              <p className="section-subtitle setup-card-intro">
                Select the semester you started studying.
              </p>
              <div className="setup-field">
                <select
                  className="input"
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
            <div className="card card-pad setup-card">
              <h2 className="section-title">Select Major(s)</h2>
              <p className="section-subtitle setup-card-intro">
                You can choose more than one major.
              </p>

              <div className="grid-auto">
                {majors.map(m => (
                  <label key={m} className="select-tile">
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
              <div className="card card-pad setup-card">
                <h2 className="section-title">Business Concentration</h2>
                <p className="section-subtitle setup-card-intro">
                  Keep Business Administration as one shared major and apply concentration-specific audit, search labels, and recommendations.
                </p>
                <div className="setup-field">
                  <select
                    className="input"
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
                <div className="text-xs mt-3 muted">
                  General keeps the shared BUS core and broad BUS electives. Other choices add concentration-specific required and elective rules.
                </div>
              </div>
            )}

            {programConflictMsg && (
              <div className="alert alert-info" role="status" aria-live="polite">
                <Info aria-hidden="true" />
                <p>{programConflictMsg}</p>
              </div>
            )}

            {/* Minors */}
            <div className="card card-pad setup-card">
              <h2 className="section-title">Select Minor(s)</h2>
              <p className="section-subtitle setup-card-intro">
                Optional - select any minors you want to pursue.
              </p>

              <div className="grid-auto">
                {availableMinors.map(m => (
                  <label key={m} className="select-tile">
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
                <div className="setup-subpanel stack-3">
                  <div>
                    <h3 className="section-title">Economics minor: intermediate course</h3>
                    <p className="section-subtitle">The minor needs one of these. Pick the one you plan to take.</p>
                  </div>
                  <div className="grid gap-2">
                    <label className="select-tile select-tile-rich">
                      <input
                        type="radio"
                        name="economics-intermediate-choice"
                        checked={economicsIntermediateChoice === "ECO 3001"}
                        onChange={() => setEconomicsIntermediateChoice("ECO 3001")}
                      />
                      <span>
                        <span className="font-semibold">Intermediate Microeconomics (ECO 3001)</span>
                        <span className="block text-xs muted">
                          Estimated remaining if selected: {economicsTrackEstimate.eco3001.totalRemainingCourses} course(s)
                          {" "}({economicsTrackEstimate.eco3001.optionMissing} from this option)
                        </span>
                        <span className="block text-xs muted">
                          Prerequisite rule: {economicsTrackPrereqs.eco3001.directText ?? "None listed"}
                        </span>
                        <span className="block text-xs muted">
                          All prerequisite courses: {economicsTrackPrereqs.eco3001.allCodes.length > 0 ? economicsTrackPrereqs.eco3001.allCodes.join(", ") : "None"}
                        </span>
                      </span>
                    </label>
                    <label className="select-tile select-tile-rich">
                      <input
                        type="radio"
                        name="economics-intermediate-choice"
                        checked={economicsIntermediateChoice === "ECO 3002"}
                        onChange={() => setEconomicsIntermediateChoice("ECO 3002")}
                      />
                      <span>
                        <span className="font-semibold">Intermediate Macroeconomics (ECO 3002)</span>
                        <span className="block text-xs muted">
                          Estimated remaining if selected: {economicsTrackEstimate.eco3002.totalRemainingCourses} course(s)
                          {" "}({economicsTrackEstimate.eco3002.optionMissing} from this option)
                        </span>
                        <span className="block text-xs muted">
                          Prerequisite rule: {economicsTrackPrereqs.eco3002.directText ?? "None listed"}
                        </span>
                        <span className="block text-xs muted">
                          All prerequisite courses: {economicsTrackPrereqs.eco3002.allCodes.length > 0 ? economicsTrackPrereqs.eco3002.allCodes.join(", ") : "None"}
                        </span>
                      </span>
                    </label>
                  </div>
                </div>
              )}
            </div>

            {marketingImcConflict && (
              <div className="alert alert-warning" role="alert">
                <TriangleAlert aria-hidden="true" />
                Marketing concentration cannot be combined with IMC minor. Choose a different BUS concentration or remove the Integrated Marketing Communications minor.
              </div>
            )}

            {/* Max credits */}
            <div className="card card-pad setup-card">
              <h2 className="section-title">Semester Load</h2>
              <label className="text-sm muted" htmlFor="max-credits">
                Max credits per semester
              </label>
              <div className="mt-2 flex items-center gap-3">
                <input
                  id="max-credits"
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
                  className="input setup-number"
                />
                <span className="text-sm muted">Typical range is 14-20.</span>
              </div>
            </div>

            {/* Continue */}
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setStep(2)}
                disabled={!canSubmit}
                className="btn btn-primary btn-lg btn-forward"
              >
                <span>Continue</span>
                <ArrowRight aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="stack-4">
            {/* Completed courses */}
            <div className="card card-pad setup-card">
              <h2 className="section-title">Completed Courses</h2>
              <p className="section-subtitle setup-card-intro">
                Search the entire catalog, import a transcript, or use both together. You can review and edit everything before continuing.
              </p>
              <div className="search-field">
              <Search aria-hidden="true" className="search-field-icon" />
              <input
                value={courseQuery}
                onChange={(e) => setCourseQuery(e.target.value)}
                onKeyDown={handleCourseKeyDown}
                placeholder="Search the full catalog (code or title)"
                className="input"
                aria-label="Search completed courses"
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
              </div>

              {queryNormalized && (
                <div
                  id="completed-course-options"
                  role="listbox"
                  className="setup-results"
                >
                  {!canSearch && queryNormalized.length > 0 && (
                    <div className="text-sm muted">
                      Type at least 2 characters.
                    </div>
                  )}
                  {canSearch && courseSearchLoading && (
                    <div className="text-sm muted">
                      Searching courses...
                    </div>
                  )}
                  {canSearch && !courseSearchLoading && courseSearchError && (
                    <div className="text-sm muted">
                      {courseSearchError}
                    </div>
                  )}
                  {canSearch && !courseSearchLoading && !courseSearchError && rankedCourseEntries.length === 0 && (
                    <div className="text-sm muted">
                      No matching courses.
                    </div>
                  )}
                  {rankedCourseEntries.map((entry, idx) => {
                    const code = entry.code;
                    const title = entry.title;
                    const selected = completedCourses.includes(code);
                    const credits = typeof entry.credits === 'number' && entry.credits >= 0
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
                      currentTermLabel,
                      scheduleTerms
                    });
                    const hasWarning = Boolean(availability.warningLabel);
                    const isActive = idx === highlightedIndex;
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
                        className={`result-option${isActive ? ' is-active' : ''}${selected ? ' is-selected' : ''}`}
                        title={
                          hasWarning
                            ? `${availability.warningLabel}. ${availability.detailsLabel}`
                            : undefined
                        }
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="course-code">{code}</span> <span className="course-name-inline">{title}</span>
                          </div>
                          {hasWarning && availability.warningLabel && (
                            <span className="badge badge-warning">{availability.warningLabel}</span>
                          )}
                        </div>
                        <div className="text-xs mt-1 muted num">{credits} credits</div>
                        {genEdTags.length > 0 && (
                          <div className="text-xs mt-1 muted">GenEd: {genEdTags.join(' · ')}</div>
                        )}
                        {businessBadges.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {businessBadges.map((badge) => (
                              <span key={`${code}:${badge}`} className="badge badge-neutral">{badge}</span>
                            ))}
                          </div>
                        )}
                        {hasWarning && availability.detailsLabel && (
                          <div className="text-xs mt-1 muted">{availability.detailsLabel}</div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {completedCourses.length > 0 && (
                <div className="mt-4">
                  <div className="chip-list-label">
                    Selected courses (completed + in progress):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {completedCourses.map((code) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => setCompletedCourses(prev => prev.filter(c => c !== code))}
                        className="chip"
                        title={`Remove ${code}`}
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {manualInProgressCourses.length > 0 && (
                <div className="mt-4">
                  <div className="chip-list-label">
                    Currently taking (auto-detected):
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {manualInProgressCourses.map((code) => (
                      <span key={code} className="chip chip-info">{code}</span>
                    ))}
                  </div>
                </div>
              )}

              <div className="divider-label" aria-hidden="true">
                <span>or import a transcript</span>
              </div>

              <div
                className={`upload-zone${isTranscriptDragging ? ' dragging' : ''}`}
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
                <span className="upload-zone-icon" aria-hidden="true"><FileUp /></span>
                <div className="font-semibold">Upload your transcript</div>
                <div className="text-sm muted">
                  PDF, PNG or JPG. Completed, in-progress and not-passed courses are detected for you to review.
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
                <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
                  <button type="button" onClick={() => transcriptInputRef.current?.click()} className="btn btn-accent">
                    <FileUp aria-hidden="true" />
                    <span>Choose file</span>
                  </button>
                  <span className="text-sm muted">or drop it here</span>
                </div>
                {selectedTranscriptName && (
                  <div className="text-sm mt-3 muted">Selected file: {selectedTranscriptName}</div>
                )}
                {transcriptStatusLabel(transcriptImportPhase) && (
                  <div className="text-sm mt-3 muted" role="status">{transcriptStatusLabel(transcriptImportPhase)}</div>
                )}
                {transcriptImportError && (
                  <div className="alert alert-danger mt-3" role="alert">
                    <TriangleAlert aria-hidden="true" />
                    <p>{transcriptImportError}</p>
                  </div>
                )}
              </div>

              {importedCompletedCourses.length > 0 && (
                <div className="mt-4">
                  <div className="chip-list-label">
                    Imported completed courses:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {importedCompletedCourses.map((code) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => removeImportedCompletedCourse(code)}
                        className="chip chip-success"
                        title={`Remove ${code}`}
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {importedFailedCourses.length > 0 && (
                <div className="mt-4">
                  <div className="chip-list-label">
                    Not passed, retaken if still required:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {importedFailedCourses.map((entry) => (
                      <button
                        key={entry.code}
                        type="button"
                        onClick={() =>
                          setImportedFailedCourses((prev) => prev.filter((item) => item.code !== entry.code))
                        }
                        className="chip chip-danger"
                        title="Remove imported course"
                      >
                        {entry.code}
                        {entry.grade ? ` · ${entry.grade}` : ''}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {importedInProgressCourses.length > 0 && (
                <div className="mt-4">
                  <div className="chip-list-label">
                    Imported in-progress courses:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {importedInProgressCourses.map((code) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => removeImportedInProgressCourse(code)}
                        className="chip chip-info"
                        title={`Remove ${code}`}
                      >
                        {code}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Back/Continue */}
            <div className="flex justify-between gap-3">
              <button type="button" onClick={() => setStep(1)} className="btn btn-outline btn-lg btn-back">
                <ArrowLeft aria-hidden="true" />
                <span>Back</span>
              </button>
              <button type="button" onClick={handleSubmit} disabled={!canSubmit} className="btn btn-primary btn-lg btn-forward">
                <span>Build my plan</span>
                <ArrowRight aria-hidden="true" />
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

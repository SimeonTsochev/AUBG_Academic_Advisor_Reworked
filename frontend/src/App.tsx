import { useEffect, useState } from 'react';
import { WelcomeScreen } from './components/WelcomeScreen';
import { AcademicSetupScreen } from './components/AcademicSetupScreen';
import { MainAdvisorScreen } from './components/MainAdvisorScreen';
import { HowItWorksModal } from './components/HowItWorksModal';
import {
  getProgramSnapshot,
  loadDefaultCatalog,
  type PlanOverrides,
  type ProgramSnapshotPayload,
  type ProgramSnapshotSwappedElective,
  type UploadCatalogResponse,
} from './api';
import type { ManualCreditEntry } from './types';

type Screen = 'welcome' | 'setup' | 'advisor';

interface AcademicSelection {
  majors: string[];       // supports multiple majors
  minors: string[];       // supports multiple minors
  economicsIntermediateChoice: "ECO 3001" | "ECO 3002" | null;
  completedCourses: string[];
  inProgressCourses: string[];
  manualCredits: ManualCreditEntry[];
  inProgressOverrides?: Record<string, string>;
  completedOverrides?: Record<string, string>;
  lastRolloverTermApplied?: string;
  strictPrereqs?: boolean;
  retakeCourses?: string[];
  maxCreditsPerSemester: number;
  startTermSeason: string;
  startTermYear: number;
  waivedMat1000: boolean;
  waivedEng1000: boolean;
}

const DEFAULT_MAX_CREDITS = 16;

const toStringArray = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0)
    : [];

const toStringMap = (value: unknown): Record<string, string> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const out: Record<string, string> = {};
  Object.entries(value as Record<string, unknown>).forEach(([key, entry]) => {
    if (typeof entry === 'string' && entry.trim().length > 0) {
      out[key] = entry;
    }
  });
  return out;
};

const normalizePlanOverrides = (value: unknown): PlanOverrides => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { add: [], remove: [], move: [], locks: [] };
  }
  const source = value as Record<string, unknown>;
  return {
    add: Array.isArray(source.add)
      ? source.add
        .filter((entry): entry is PlanOverrides['add'][number] => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
        .map((entry) => ({ ...entry }))
      : [],
    remove: Array.isArray(source.remove)
      ? source.remove
        .filter((entry): entry is PlanOverrides['remove'][number] => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
        .map((entry) => ({ ...entry }))
      : [],
    move: Array.isArray(source.move)
      ? source.move
        .filter((entry): entry is PlanOverrides['move'][number] => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
        .map((entry) => ({ ...entry }))
      : [],
    locks: Array.isArray(source.locks)
      ? source.locks
        .filter((entry): entry is NonNullable<PlanOverrides['locks']>[number] => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
        .map((entry) => ({ ...entry }))
      : [],
  };
};

const normalizeSwappedElectives = (value: unknown): ProgramSnapshotSwappedElective[] => {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
    .map((entry) => ({
      termLabel: typeof entry.termLabel === 'string' ? entry.termLabel : '',
      addedCourseCode: typeof entry.addedCourseCode === 'string' ? entry.addedCourseCode : '',
      addedCourseInstanceId: typeof entry.addedCourseInstanceId === 'string' ? entry.addedCourseInstanceId : '',
      replacedPlaceholderInstanceId: typeof entry.replacedPlaceholderInstanceId === 'string' ? entry.replacedPlaceholderInstanceId : '',
      placeholderCode: typeof entry.placeholderCode === 'string' ? entry.placeholderCode : '',
      placeholderCredits:
        typeof entry.placeholderCredits === 'number' && Number.isFinite(entry.placeholderCredits)
          ? entry.placeholderCredits
          : 0,
    }))
    .filter(
      (entry) =>
        entry.termLabel.trim().length > 0
        && entry.addedCourseCode.trim().length > 0
        && entry.addedCourseInstanceId.trim().length > 0
        && entry.replacedPlaceholderInstanceId.trim().length > 0
        && entry.placeholderCode.trim().length > 0
    );
};

const normalizeManualCredits = (value: unknown): ManualCreditEntry[] => {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
    .map((entry) => {
      const rawCode = typeof entry.code === 'string' ? entry.code.trim().toUpperCase() : '';
      const rawCredits = typeof entry.credits === 'number' ? entry.credits : Number(entry.credits);
      const rawType = typeof entry.credit_type === 'string' ? entry.credit_type : '';
      const term = typeof entry.term === 'string' ? entry.term.trim() : '';
      const instanceId = typeof entry.instance_id === 'string' ? entry.instance_id.trim() : '';
      const creditType =
        rawType === 'GENED' || rawType === 'MAJOR_ELECTIVE' || rawType === 'FREE_ELECTIVE'
          ? rawType
          : null;

      return {
        code: rawCode === 'OTH 0001' ? 'OTH 0001' : null,
        instance_id: instanceId,
        term,
        credits: Number.isFinite(rawCredits) ? Math.max(0, Math.trunc(rawCredits)) : 0,
        credit_type: creditType,
        gened_category:
          typeof entry.gened_category === 'string' && entry.gened_category.trim().length > 0
            ? entry.gened_category.trim()
            : undefined,
        program:
          typeof entry.program === 'string' && entry.program.trim().length > 0
            ? entry.program.trim()
            : undefined,
        note:
          typeof entry.note === 'string' && entry.note.trim().length > 0
            ? entry.note.trim()
            : undefined,
      };
    })
    .filter(
      (
        entry
      ): entry is ManualCreditEntry & {
        code: 'OTH 0001';
        credit_type: 'GENED' | 'MAJOR_ELECTIVE' | 'FREE_ELECTIVE';
      } =>
        entry.code === 'OTH 0001'
        && typeof entry.credit_type === 'string'
        && entry.instance_id.length > 0
        && entry.term.length > 0
        && entry.credits > 0
    );
};

const normalizeProgramSnapshotPayload = (value: unknown): ProgramSnapshotPayload => {
  const raw = value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
  const currentYear = new Date().getFullYear();
  const startSeason = raw.start_term_season === 'Spring' || raw.start_term_season === 'Fall'
    ? raw.start_term_season
    : 'Fall';
  const economicsIntermediateChoice =
    raw.economicsIntermediateChoice === 'ECO 3001' || raw.economicsIntermediateChoice === 'ECO 3002'
      ? raw.economicsIntermediateChoice
      : null;

  return {
    majors: toStringArray(raw.majors),
    minors: toStringArray(raw.minors),
    economicsIntermediateChoice,
    completedCourses: toStringArray(raw.completedCourses),
    inProgressCourses: toStringArray(raw.inProgressCourses),
    manualCredits: normalizeManualCredits(raw.manualCredits),
    completedOverrides: toStringMap(raw.completedOverrides),
    inProgressOverrides: toStringMap(raw.inProgressOverrides),
    overrides: normalizePlanOverrides(raw.overrides),
    swappedElectives: normalizeSwappedElectives(raw.swappedElectives),
    removedCourses: toStringArray(raw.removedCourses),
    start_term_season: startSeason,
    start_term_year:
      typeof raw.start_term_year === 'number' && Number.isFinite(raw.start_term_year)
        ? Math.trunc(raw.start_term_year)
        : currentYear,
    max_credits_per_semester:
      typeof raw.max_credits_per_semester === 'number' && Number.isFinite(raw.max_credits_per_semester)
        ? Math.max(1, Math.trunc(raw.max_credits_per_semester))
        : DEFAULT_MAX_CREDITS,
    waived_mat1000: raw.waived_mat1000 === true,
    waived_eng1000: raw.waived_eng1000 === true,
    strict_prereqs: raw.strict_prereqs === true,
    retakeCourses: toStringArray(raw.retakeCourses),
    current_term_label: typeof raw.current_term_label === 'string' ? raw.current_term_label : null,
    lastRolloverTermApplied:
      typeof raw.lastRolloverTermApplied === 'string' && raw.lastRolloverTermApplied.trim().length > 0
        ? raw.lastRolloverTermApplied
        : undefined,
  };
};

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('welcome');
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [isCatalogLoading, setIsCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [catalog, setCatalog] = useState<UploadCatalogResponse | null>(null);
  const [restoredSnapshot, setRestoredSnapshot] = useState<ProgramSnapshotPayload | null>(null);
  const [restoredSnapshotToken, setRestoredSnapshotToken] = useState<string | null>(null);
  const [selection, setSelection] = useState<AcademicSelection>({
    majors: [],
    minors: [],
    economicsIntermediateChoice: null,
    completedCourses: [],
    inProgressCourses: [],
    manualCredits: [],
    inProgressOverrides: {},
    completedOverrides: {},
    lastRolloverTermApplied: undefined,
    strictPrereqs: false,
    retakeCourses: [],
    maxCreditsPerSemester: DEFAULT_MAX_CREDITS,
    startTermSeason: "Fall",
    startTermYear: new Date().getFullYear(),
    waivedMat1000: false,
    waivedEng1000: false,
  });

  useEffect(() => {
    const match = window.location.pathname.match(/^\/p\/([A-Za-z0-9_-]+)$/);
    if (!match) return;

    let cancelled = false;
    const token = match[1];

    async function restoreFromToken() {
      setCatalogError(null);
      setIsCatalogLoading(true);
      let loadedCatalog: UploadCatalogResponse | null = null;

      try {
        loadedCatalog = await loadDefaultCatalog();
        if (cancelled) return;
        const snapshot = await getProgramSnapshot(token);
        if (cancelled) return;

        if (
          loadedCatalog.catalog_year
          && snapshot.catalog_year
          && loadedCatalog.catalog_year !== snapshot.catalog_year
        ) {
          console.warn(
            `Loaded snapshot for catalog year ${snapshot.catalog_year}, but the active catalog is ${loadedCatalog.catalog_year}.`
          );
        }

        const normalized = normalizeProgramSnapshotPayload(snapshot.payload);
        setCatalog(loadedCatalog);
        setSelection((prev) => ({
          ...prev,
          majors: normalized.majors,
          minors: normalized.minors,
          economicsIntermediateChoice: normalized.economicsIntermediateChoice ?? null,
          completedCourses: normalized.completedCourses,
          inProgressCourses: normalized.inProgressCourses,
          manualCredits: normalized.manualCredits,
          inProgressOverrides: normalized.inProgressOverrides,
          completedOverrides: normalized.completedOverrides,
          lastRolloverTermApplied: normalized.lastRolloverTermApplied,
          strictPrereqs: normalized.strict_prereqs,
          retakeCourses: normalized.retakeCourses,
          maxCreditsPerSemester: normalized.max_credits_per_semester,
          startTermSeason: normalized.start_term_season,
          startTermYear: normalized.start_term_year,
          waivedMat1000: normalized.waived_mat1000,
          waivedEng1000: normalized.waived_eng1000,
        }));
        setRestoredSnapshot(normalized);
        setRestoredSnapshotToken(token);
        setCurrentScreen('advisor');
      } catch (e: any) {
        if (cancelled) return;
        if (loadedCatalog) {
          setCatalog(loadedCatalog);
        }
        setCatalogError(e?.message ?? 'Failed to load saved program.');
      } finally {
        if (!cancelled) {
          setIsCatalogLoading(false);
        }
      }
    }

    restoreFromToken();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleStart = async () => {
    setCatalogError(null);
    setRestoredSnapshot(null);
    setRestoredSnapshotToken(null);
    if (catalog) {
      setCurrentScreen('setup');
      return;
    }
    setIsCatalogLoading(true);
    try {
      const resp = await loadDefaultCatalog();
      setCatalog(resp);
      setCurrentScreen('setup');
    } catch (e: any) {
      setCatalogError(e?.message ?? 'Failed to load catalog.');
    } finally {
      setIsCatalogLoading(false);
    }
  };

  const handleSetupComplete = (data: AcademicSelection) => {
    setRestoredSnapshot(null);
    setRestoredSnapshotToken(null);
    setSelection((prev) => ({ ...prev, ...data }));
    setCurrentScreen('advisor');
  };

  return (
    <>
      {currentScreen === 'welcome' && (
        <WelcomeScreen
          onStart={handleStart}
          onHowItWorks={() => setShowHowItWorks(true)}
          isLoading={isCatalogLoading}
          errorMsg={catalogError ?? undefined}
        />
      )}

      {currentScreen === 'setup' && catalog && (
        <AcademicSetupScreen
          catalogYear={catalog.catalog_year ?? undefined}
          majors={catalog.majors}
          minors={catalog.minors}
          courses={catalog.courses}
          courseMeta={catalog.course_meta}
          onComplete={handleSetupComplete}
          onBack={() => setCurrentScreen('welcome')}
        />
      )}

      {currentScreen === 'advisor' && catalog && (
        <MainAdvisorScreen
          catalog={catalog}
          selection={selection}
          initialSnapshot={restoredSnapshot}
          initialSnapshotToken={restoredSnapshotToken}
          onBack={() => setCurrentScreen('setup')}
        />
      )}

      {showHowItWorks && (
        <HowItWorksModal onClose={() => setShowHowItWorks(false)} />
      )}
    </>
  );
}

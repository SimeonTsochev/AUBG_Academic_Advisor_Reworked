import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react';
import { WelcomeScreen } from './components/WelcomeScreen';
import { NO_PROGRAM_LINK, readProgramLink } from './utils/programLink';
import { HowItWorksModal } from './components/HowItWorksModal';
import { DisclaimerModal } from './components/DisclaimerModal';
import { StudentProjectNotice } from './components/StudentProjectNotice';
import {
  getProgramSnapshot,
  loadDefaultCatalog,
  type PlanOverrides,
  type ProgramOptionSelection,
  type ProgramSnapshotPayload,
  type ProgramSnapshotSwappedElective,
  type UploadCatalogResponse,
} from './api';
import type { FailedCourse, ManualCreditEntry, RetakeEntry } from './types';
import type { GradeMap } from './utils/grades';
import { normalizeFailedCourses } from './utils/retakes';
import { describeRequestError } from './utils/requestErrors';

type Screen = 'welcome' | 'setup' | 'advisor';

// The setup and advisor screens are most of the app's code; load them as separate chunks so the
// welcome screen renders first, and prefetch them while it is shown.
const importSetupScreen = () => import('./components/AcademicSetupScreen');
const importAdvisorScreen = () => import('./components/MainAdvisorScreen');
const AcademicSetupScreen = lazy(() => importSetupScreen().then((m) => ({ default: m.AcademicSetupScreen })));
const MainAdvisorScreen = lazy(() => importAdvisorScreen().then((m) => ({ default: m.MainAdvisorScreen })));

interface AcademicSelection {
  majors: string[];       // supports multiple majors
  minors: string[];       // supports multiple minors
  businessConcentration: string | null;
  economicsIntermediateChoice: "ECO 3001" | "ECO 3002" | null;
  programOptions: ProgramOptionSelection;
  placementWaivers: string[];
  completedCourses: string[];
  inProgressCourses: string[];
  failedCourses: FailedCourse[];
  manualCredits: ManualCreditEntry[];
  inProgressOverrides?: Record<string, string>;
  completedOverrides?: Record<string, string>;
  lastRolloverTermApplied?: string;
  strictPrereqs?: boolean;
  retakeCourses?: string[];
  retakeEntries?: RetakeEntry[];
  startTermSeason: string;
  startTermYear: number;
  waivedMat1000: boolean;
  waivedEng1000: boolean;
}

type SetupResult = AcademicSelection & { grades?: GradeMap };

/** The selection a saved or current plan was made from. */
const selectionFromSnapshot = (snapshot: ProgramSnapshotPayload): AcademicSelection => ({
  majors: snapshot.majors,
  minors: snapshot.minors,
  businessConcentration: snapshot.businessConcentration,
  economicsIntermediateChoice: snapshot.economicsIntermediateChoice ?? null,
  programOptions: snapshot.programOptions ?? {},
  placementWaivers: snapshot.placementWaivers ?? [],
  completedCourses: snapshot.completedCourses,
  inProgressCourses: snapshot.inProgressCourses,
  failedCourses: snapshot.failedCourses ?? [],
  manualCredits: snapshot.manualCredits,
  inProgressOverrides: snapshot.inProgressOverrides,
  completedOverrides: snapshot.completedOverrides,
  lastRolloverTermApplied: snapshot.lastRolloverTermApplied,
  strictPrereqs: snapshot.strict_prereqs,
  retakeCourses: snapshot.retakeCourses,
  retakeEntries: snapshot.retakeEntries,
  startTermSeason: snapshot.start_term_season,
  startTermYear: snapshot.start_term_year,
  waivedMat1000: snapshot.waived_mat1000,
  waivedEng1000: snapshot.waived_eng1000,
});

const DISCLAIMER_SESSION_KEY = 'disclaimerAccepted';

const readDisclaimerAccepted = (): boolean => {
  if (typeof window === 'undefined') return false;
  try {
    return window.sessionStorage.getItem(DISCLAIMER_SESSION_KEY) === 'true';
  } catch {
    return false;
  }
};

const persistDisclaimerAccepted = () => {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(DISCLAIMER_SESSION_KEY, 'true');
  } catch {
    // Ignore session storage failures and continue with in-memory state.
  }
};

const STUDENT_NOTICE_SESSION_KEY = 'studentNoticeAcknowledged';

const readStudentNoticeAcknowledged = (): boolean => {
  if (typeof window === 'undefined') return false;
  try {
    return window.sessionStorage.getItem(STUDENT_NOTICE_SESSION_KEY) === 'true';
  } catch {
    return false;
  }
};

const persistStudentNoticeAcknowledged = () => {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(STUDENT_NOTICE_SESSION_KEY, 'true');
  } catch {
    // Ignore session storage failures and continue with in-memory state.
  }
};

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

// Per major, the chosen options; the backend ignores majors or choices it does not offer.
const toProgramOptions = (value: unknown): ProgramOptionSelection => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const out: ProgramOptionSelection = {};
  Object.entries(value as Record<string, unknown>).forEach(([major, choices]) => {
    const valid = toStringArray(choices);
    if (valid.length > 0) out[major] = valid;
  });
  return out;
};

const normalizePlanOverrides = (value: unknown): PlanOverrides => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { add: [], remove: [], move: [] };
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

type ManualCreditCandidate = Omit<ManualCreditEntry, 'code' | 'credit_type'> & {
  code: ManualCreditEntry['code'] | null;
  credit_type: ManualCreditEntry['credit_type'] | null;
};

const normalizeManualCredits = (value: unknown): ManualCreditEntry[] => {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
    .map((entry): ManualCreditCandidate => {
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
      (entry): entry is ManualCreditEntry =>
        entry.code === 'OTH 0001'
        && entry.credit_type !== null
        && entry.instance_id.length > 0
        && entry.term.length > 0
        && entry.credits > 0
    );
};

const normalizeRetakeEntries = (value: unknown): RetakeEntry[] => {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is Record<string, unknown> => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)))
    .map((entry) => {
      const instanceId = typeof entry.instance_id === 'string' ? entry.instance_id.trim() : '';
      const code = typeof entry.code === 'string' ? entry.code.trim().toUpperCase() : '';
      const term = typeof entry.term === 'string' ? entry.term.trim() : '';
      const statusRaw = typeof entry.status === 'string' ? entry.status.trim().toUpperCase() : '';
      const status: RetakeEntry['status'] =
        statusRaw === 'COMPLETED'
          ? 'COMPLETED'
          : statusRaw === 'IN_PROGRESS'
            ? 'IN_PROGRESS'
            : 'PLANNED';
      return {
        instance_id: instanceId,
        code,
        term,
        status,
        label: 'Retake' as const,
      };
    })
    .filter((entry) => entry.instance_id.length > 0 && entry.code.length > 0 && entry.term.length > 0);
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
  const majors = toStringArray(raw.majors);
  const businessConcentrationRaw =
    typeof raw.businessConcentration === 'string' && raw.businessConcentration.trim().length > 0
      ? raw.businessConcentration.trim()
      : null;

  const normalizedOverrides = normalizePlanOverrides(raw.overrides);
  const retakeEntriesFromOverrides = normalizedOverrides.add
    .filter((entry) => entry.is_retake === true)
    .map((entry) => ({
      instance_id: entry.instance_id?.trim() ?? '',
      code: typeof entry.code === 'string' ? entry.code.trim().toUpperCase() : '',
      term: typeof entry.term === 'string' ? entry.term.trim() : '',
      status: 'PLANNED' as const,
      label: 'Retake' as const,
    }))
    .filter((entry) => entry.instance_id.length > 0 && entry.code.length > 0 && entry.term.length > 0);
  const normalizedRetakeEntries = normalizeRetakeEntries(raw.retakeEntries);
  const retakeEntries = normalizedRetakeEntries.length > 0
    ? normalizedRetakeEntries
    : retakeEntriesFromOverrides;

  return {
    majors,
    minors: toStringArray(raw.minors),
    businessConcentration: majors.includes('Business Administration')
      ? (businessConcentrationRaw ?? 'General')
      : null,
    economicsIntermediateChoice,
    programOptions: toProgramOptions(raw.programOptions),
    placementWaivers: toStringArray(raw.placementWaivers),
    completedCourses: toStringArray(raw.completedCourses),
    inProgressCourses: toStringArray(raw.inProgressCourses),
    failedCourses: normalizeFailedCourses(raw.failedCourses),
    manualCredits: normalizeManualCredits(raw.manualCredits),
    completedOverrides: toStringMap(raw.completedOverrides),
    inProgressOverrides: toStringMap(raw.inProgressOverrides),
    overrides: normalizedOverrides,
    swappedElectives: normalizeSwappedElectives(raw.swappedElectives),
    removedCourses: toStringArray(raw.removedCourses),
    start_term_season: startSeason,
    start_term_year:
      typeof raw.start_term_year === 'number' && Number.isFinite(raw.start_term_year)
        ? Math.trunc(raw.start_term_year)
        : currentYear,
    waived_mat1000: raw.waived_mat1000 === true,
    waived_eng1000: raw.waived_eng1000 === true,
    strict_prereqs: raw.strict_prereqs === true,
    retakeCourses: toStringArray(raw.retakeCourses),
    retakeEntries,
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
  const [disclaimerAccepted, setDisclaimerAccepted] = useState<boolean>(() => readDisclaimerAccepted());
  const [studentNoticeAcknowledged, setStudentNoticeAcknowledged] = useState<boolean>(
    () => readStudentNoticeAcknowledged(),
  );
  const handleStudentNoticeAcknowledge = useCallback(() => {
    persistStudentNoticeAcknowledged();
    setStudentNoticeAcknowledged(true);
  }, []);

  const [catalog, setCatalog] = useState<UploadCatalogResponse | null>(null);
  // One shared catalog request: prefetched on load (which also wakes a cold backend), reused by
  // Start and by shared-link restore, and retried if it failed.
  const catalogRequestRef = useRef<Promise<UploadCatalogResponse> | null>(null);
  const requestCatalog = () => {
    if (!catalogRequestRef.current) {
      catalogRequestRef.current = loadDefaultCatalog().catch((e) => {
        catalogRequestRef.current = null;
        throw e;
      });
    }
    return catalogRequestRef.current;
  };
  const [restoredSnapshot, setRestoredSnapshot] = useState<ProgramSnapshotPayload | null>(null);
  const [restoredSnapshotToken, setRestoredSnapshotToken] = useState<string | null>(null);
  const [pendingSelection, setPendingSelection] = useState<SetupResult | null>(null);
  // Back from the advisor: setup opens with the plan's selection, and the plan's edits come back with it.
  const [setupPrefill, setSetupPrefill] = useState<SetupResult | null>(null);
  const [carriedPlanEdits, setCarriedPlanEdits] = useState<ProgramSnapshotPayload | null>(null);
  // Grades from the setup transcript import; kept apart from the selection so they never reach a snapshot.
  const [setupGrades, setSetupGrades] = useState<GradeMap>({});
  const [selection, setSelection] = useState<AcademicSelection>({
    majors: [],
    minors: [],
    businessConcentration: null,
    economicsIntermediateChoice: null,
    programOptions: {},
    placementWaivers: [],
    completedCourses: [],
    inProgressCourses: [],
    failedCourses: [],
    manualCredits: [],
    inProgressOverrides: {},
    completedOverrides: {},
    lastRolloverTermApplied: undefined,
    strictPrereqs: false,
    retakeCourses: [],
    retakeEntries: [],
    startTermSeason: "Fall",
    startTermYear: new Date().getFullYear(),
    waivedMat1000: false,
    waivedEng1000: false,
  });

  useEffect(() => {
    void importSetupScreen().catch(() => undefined);
    void importAdvisorScreen().catch(() => undefined);
    if (/^\/p\//.test(window.location.pathname)) return;
    let cancelled = false;
    requestCatalog().then(
      (resp) => {
        if (cancelled) return;
        setCatalog((prev) => prev ?? resp);
        // A requirement-page link (`/?major=...`) opens the setup screen with that program selected.
        const linked = readProgramLink(window.location.search, resp.majors, resp.minors);
        if (linked.majors.length || linked.minors.length) {
          setCurrentScreen((screen) => (screen === 'welcome' ? 'setup' : screen));
        }
      },
      () => undefined, // Start shows the error and retries.
    );
    return () => {
      cancelled = true;
    };
  }, []);

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
        loadedCatalog = await requestCatalog();
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
        setSelection((prev) => ({ ...prev, ...selectionFromSnapshot(normalized) }));
        setRestoredSnapshot(normalized);
        setRestoredSnapshotToken(token);
        setCurrentScreen('advisor');
      } catch (e: any) {
        if (cancelled) return;
        if (loadedCatalog) {
          setCatalog(loadedCatalog);
        }
        setCatalogError(describeRequestError(e, 'The saved plan could not be loaded.'));
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
      const resp = await requestCatalog();
      setCatalog(resp);
      setCurrentScreen('setup');
    } catch (e: any) {
      setCatalogError(describeRequestError(e, 'The course catalog could not be loaded.'));
    } finally {
      setIsCatalogLoading(false);
    }
  };

  const openAdvisorWithSelection = ({ grades, ...data }: SetupResult) => {
    setSetupGrades(grades ?? {});
    setRestoredSnapshot(carriedPlanEdits);
    setRestoredSnapshotToken(null);
    setSelection((prev) => ({ ...prev, ...data }));
    setCurrentScreen('advisor');
  };

  const handleBackToSetup = ({ snapshot, grades }: { snapshot: ProgramSnapshotPayload; grades: GradeMap }) => {
    setSetupPrefill({ ...selectionFromSnapshot(snapshot), grades });
    setCarriedPlanEdits(snapshot);
    setCurrentScreen('setup');
  };

  const handleSetupComplete = (data: SetupResult) => {
    if (disclaimerAccepted) {
      openAdvisorWithSelection(data);
      return;
    }
    setPendingSelection(data);
  };

  const handleDisclaimerClose = () => {
    setPendingSelection(null);
  };

  const handleDisclaimerConfirm = () => {
    if (!pendingSelection) return;
    persistDisclaimerAccepted();
    setDisclaimerAccepted(true);
    const nextSelection = pendingSelection;
    setPendingSelection(null);
    openAdvisorWithSelection(nextSelection);
  };

  const linkedPrograms = catalog
    ? readProgramLink(window.location.search, catalog.majors, catalog.minors)
    : NO_PROGRAM_LINK;

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

      <Suspense fallback={null}>
      {currentScreen === 'setup' && catalog && (
        <AcademicSetupScreen
          catalogId={catalog.catalog_id}
          catalogYear={catalog.catalog_year ?? undefined}
          majors={catalog.majors}
          minors={catalog.minors}
          programInfo={catalog.program_info}
          minorInfo={catalog.minor_info}
          courses={catalog.courses}
          courseMeta={catalog.course_meta}
          onComplete={handleSetupComplete}
          onBack={() => setCurrentScreen('welcome')}
          initialMajors={linkedPrograms.majors}
          initialMinors={linkedPrograms.minors}
          initialSelection={setupPrefill}
        />
      )}

      {currentScreen === 'advisor' && catalog && (
        <MainAdvisorScreen
          catalog={catalog}
          selection={selection}
          initialSnapshot={restoredSnapshot}
          initialSnapshotToken={restoredSnapshotToken}
          initialGrades={setupGrades}
          onBack={handleBackToSetup}
        />
      )}
      </Suspense>

      {pendingSelection && !disclaimerAccepted && (
        <DisclaimerModal
          onClose={handleDisclaimerClose}
          onConfirm={handleDisclaimerConfirm}
        />
      )}

      {showHowItWorks && (
        <HowItWorksModal
          onClose={() => setShowHowItWorks(false)}
          onGetStarted={() => {
            setShowHowItWorks(false);
            void handleStart();
          }}
        />
      )}

      {!studentNoticeAcknowledged && (
        <StudentProjectNotice onAcknowledge={handleStudentNoticeAcknowledge} />
      )}
    </>
  );
}

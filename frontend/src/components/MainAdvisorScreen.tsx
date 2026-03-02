import { useEffect, useMemo, useRef, useState } from 'react';
import { Calendar, Download, ArrowLeft, Sparkles, ChevronDown, ChevronUp, Check } from 'lucide-react';
import { ChatInterface } from './ChatInterface';
import { ProgressDashboard } from './ProgressDashboard';
import { SemesterPlanView } from './SemesterPlanView';
import { ElectiveRecommendationPanel } from './ElectiveRecommendationPanel';
import { PrereqConfirmDialog } from './PrereqConfirmDialog';
import type { ChatMessage, Course, Progress, ElectiveSuggestion } from '../types';
import type { UploadCatalogResponse, GeneratePlanResponse, PlanCourse, PlanOverrides, MinorSuggestion as ApiMinorSuggestion } from '../api';
import { downloadPlanPdf, generatePlan } from '../api';
import { getCourseAvailabilityInfo } from '../utils/courseAvailability';
import { MIN_CREDITS_PER_TERM } from '../constants/academic';

interface MainAdvisorScreenProps {
  catalog: UploadCatalogResponse;
  selection: {
    majors: string[];
    minors: string[];
    economicsIntermediateChoice: "ECO 3001" | "ECO 3002" | null;
    completedCourses: string[];
    inProgressCourses: string[];
    maxCreditsPerSemester: number;
    startTermSeason: string;
    startTermYear: number;
    waivedMat1000: boolean;
    waivedEng1000: boolean;
  };
  onBack: () => void;
}

export function MainAdvisorScreen({ catalog, selection, onBack }: MainAdvisorScreenProps) {
  const SEMESTERS_PER_YEAR = 2;
  const [activeTab, setActiveTab] = useState<'plan' | 'electives' | 'chat'>('plan');
  const [plan, setPlan] = useState<GeneratePlanResponse | null>(null);
  const [overrides, setOverrides] = useState<PlanOverrides>(() => {
    const choice = selection.economicsIntermediateChoice;
    const economicsSelected = selection.minors.includes("Economics");
    if (!economicsSelected || !choice) {
      return { add: [], remove: [], move: [] };
    }
    const unselected = choice === "ECO 3001" ? "ECO 3002" : "ECO 3001";
    return {
      add: [],
      remove: [{ code: unselected }],
      move: [],
    };
  });

  const addOverrideAdd = (
    term: string,
    code: string,
    instanceId: string,
    genEdCategory?: string | null
  ) => {
    setOverrides(prev => {
      const existing = prev.add.find(a => a.code === code);
      const filtered = prev.add.filter(a => a.code !== code);
      const resolvedCategory = genEdCategory ?? existing?.gen_ed_category ?? undefined;
      return {
        ...prev,
        add: [
          ...filtered,
          {
            term,
            code,
            instance_id: instanceId,
            gen_ed_category: resolvedCategory
          }
        ]
      };
    });
  };

  const addOverrideRemove = (term: string | null, instanceId?: string | null, code?: string) => {
    setOverrides(prev => {
      const exists = prev.remove.some(
        r => (r.term ?? null) === term && (instanceId ? r.instance_id === instanceId : (!r.instance_id && r.code === code))
      );
      if (exists) return prev;
      return { ...prev, remove: [...prev.remove, { term, code, instance_id: instanceId ?? undefined }] };
    });
  };

  const addOverrideMove = (
    fromTerm: string,
    toTerm: string,
    code: string,
    instanceId?: string | null
  ) => {
    setOverrides(prev => {
      const nextMoves = (prev.move ?? []).filter((m) => {
        if (instanceId) {
          return m.instance_id !== instanceId;
        }
        return !(m.code === code && !m.instance_id);
      });
      const exists = nextMoves.some(
        m => m.from_term === fromTerm && m.to_term === toTerm && (instanceId ? m.instance_id === instanceId : (!m.instance_id && m.code === code))
      );
      if (exists) return { ...prev, move: nextMoves };
      return {
        ...prev,
        move: [...nextMoves, { from_term: fromTerm, to_term: toTerm, code, instance_id: instanceId ?? undefined }]
      };
    });
  };

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [completedCourses, setCompletedCourses] = useState<string[]>(selection.completedCourses);
  const [inProgressCourses, setInProgressCourses] = useState<string[]>(selection.inProgressCourses ?? []);
  const [inProgressOverrides, setInProgressOverrides] = useState<Record<string, string>>({});
  const [completedOverrides, setCompletedOverrides] = useState<Record<string, string>>({});
  const [startTermSeason, setStartTermSeason] = useState<string>(selection.startTermSeason);
  const [startTermYear, setStartTermYear] = useState<number>(selection.startTermYear);
  const [dismissedImpliedStart, setDismissedImpliedStart] = useState(false);
  const [appliedImpliedStartKey, setAppliedImpliedStartKey] = useState<string | null>(null);
  const [startTermUndo, setStartTermUndo] = useState<{
    season: string;
    year: number;
    completedCourses: string[];
    inProgressCourses: string[];
    inProgressOverrides: Record<string, string>;
  } | null>(null);
  const [removedCourses, setRemovedCourses] = useState<string[]>([]);
  const lastRemovedSnapshot = useRef<string[]>([]);
  const [pendingRemoval, setPendingRemoval] = useState<{
    instanceId: string;
    code: string;
    term: string | null;
    status: Course['status'];
  } | null>(null);
  const [replacementTarget, setReplacementTarget] = useState<string | null>(null);
  const [replacementTargetCode, setReplacementTargetCode] = useState<string | null>(null);
  const [replacementTargetTerm, setReplacementTargetTerm] = useState<string | null>(null);
  const [replacementCategories, setReplacementCategories] = useState<string[]>([]);
  const [replacementCategory, setReplacementCategory] = useState<string | null>(null);
  const [replacementOptions, setReplacementOptions] = useState<string[]>([]);
  const [pendingReplacement, setPendingReplacement] = useState<{
    targetInstanceId: string;
    targetCode: string;
    nextCode: string;
    semester: string;
    category: string | null;
    prereqs: string[];
  } | null>(null);
  const [pendingReplacementImpact, setPendingReplacementImpact] = useState<{
    targetCode: string;
    nextCode: string;
    semester: string;
    dependents: { code: string; instanceId?: string; term?: string }[];
  } | null>(null);
  const [pendingAddCourse, setPendingAddCourse] = useState<{ code: string } | null>(null);
  const [pendingAddTerm, setPendingAddTerm] = useState<string | null>(null);

  const [pendingAddConfirm, setPendingAddConfirm] = useState<{
    code: string;
    term: string;
    prereqs: string[];
    unmet: string[];
    unmetCodes: string[];
    satisfied: boolean;
    replaceFreeElective?: { instanceId: string; code: string } | null;
  } | null>(null);
  const [pendingPrereqPlacement, setPendingPrereqPlacement] = useState<{
    courseCode: string;
    targetTerm: string;
    prereqs: string[];
    index: number;
    replaceFreeElective?: { instanceId: string; code: string } | null;
  } | null>(null);
  const [pendingPrereqTerm, setPendingPrereqTerm] = useState<string | null>(null);
  const [pendingSwapSourceInstanceId, setPendingSwapSourceInstanceId] = useState<string | null>(null);
  const [moveCourseWarning, setMoveCourseWarning] = useState<string | null>(null);
  const [expandedSmartMinor, setExpandedSmartMinor] = useState<string | null>(null);
  type SwappedElectiveRecord = {
    termLabel: string;
    addedCourseCode: string;
    addedCourseInstanceId: string;
    replacedPlaceholderInstanceId: string;
    placeholderCode: string;
    placeholderCredits: number;
  };
  const [swappedElectives, setSwappedElectives] = useState<SwappedElectiveRecord[]>([]);
  const pendingAtomicAddRef = useRef<{
    expectedCode: string;
    expectedTerm: string;
    previousOverrides: PlanOverrides;
    previousRemovedCourses: string[];
    previousSwappedElectives: SwappedElectiveRecord[];
  } | null>(null);
  const suppressNextSummaryRef = useRef(false);

  const minCreditsPerTerm = MIN_CREDITS_PER_TERM;
  const createInstanceId = () =>
    (globalThis.crypto && "randomUUID" in globalThis.crypto)
      ? globalThis.crypto.randomUUID()
      : `inst-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const cloneOverrides = (value: PlanOverrides): PlanOverrides => ({
    add: (value.add ?? []).map((entry) => ({ ...entry })),
    remove: (value.remove ?? []).map((entry) => ({ ...entry })),
    move: (value.move ?? []).map((entry) => ({ ...entry })),
  });
  const commitAtomicOverrideAdd = (
    term: string,
    code: string,
    opts?: { replaceFreeElective?: { instanceId: string; code: string } | null; genEdCategory?: string | null }
  ) => {
    if (pendingAtomicAddRef.current) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Please wait for the previous add operation to finish.",
          timestamp: new Date(),
        },
      ]);
      return false;
    }

    pendingAtomicAddRef.current = {
      expectedCode: code,
      expectedTerm: term,
      previousOverrides: cloneOverrides(overrides),
      previousRemovedCourses: [...removedCourses],
      previousSwappedElectives: [...swappedElectives],
    };

    const placeholder = opts?.replaceFreeElective;
    const addedInstanceId = createInstanceId();
    if (placeholder) {
      addOverrideRemove(term, placeholder.instanceId, placeholder.code);
      setRemovedCourses((prev) =>
        prev.includes(placeholder.instanceId) ? prev : [...prev, placeholder.instanceId]
      );
      upsertSwappedElective({
        termLabel: term,
        addedCourseCode: code,
        addedCourseInstanceId: addedInstanceId,
        replacedPlaceholderInstanceId: placeholder.instanceId,
        placeholderCode: placeholder.code,
        placeholderCredits: getCourseCredits(placeholder.code),
      });
    }
    addOverrideAdd(term, code, addedInstanceId, opts?.genEdCategory ?? null);
    return true;
  };
  const completedInstanceId = (code: string) => `completed:${code}`;
  const inProgressInstanceId = (code: string) => `inprogress:${code}`;
  const removedInstanceSet = useMemo(() => new Set(removedCourses), [removedCourses]);
  const removedCodeSet = useMemo(
    () =>
      new Set(
        overrides.remove
          .filter((entry) => !entry.instance_id)
          .map((entry) => entry.code)
          .filter((code): code is string => typeof code === "string" && code.trim().length > 0)
      ),
    [overrides.remove]
  );
  const isRemovedPlanCourse = (course?: { instance_id?: string; code?: string }) => {
    if (!course) return false;
    if (course.instance_id && removedInstanceSet.has(course.instance_id)) return true;
    if (course.code && removedCodeSet.has(course.code)) return true;
    return false;
  };

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Upload processed. I’m generating your degree plan based on the official catalog rules…',
      timestamp: new Date()
    }
  ]);

  const termIndex = (season: string, year: number) => year * 2 + (season === "Fall" ? 1 : 0);
  const termFromIndex = (idx: number) => {
    const year = Math.floor(idx / 2);
    const season = idx % 2 === 1 ? "Fall" : "Spring";
    return { season, year };
  };
  const currentTermLabel = useMemo(() => {
    const now = new Date();
    const season = now.getMonth() + 1 <= 5 ? "Spring" : "Fall";
    const year = now.getFullYear();
    return `${season} ${year}`;
  }, []);
  const normGenEd = (raw?: string | null) => {
    if (!raw) return "";
    return raw
      .replace(/[‐‑‒–—―]/g, "-")
      .replace(/^gen(?:eral)?\s*ed(?:ucation)?\s*:\s*/i, "")
      .replace(/\(\s*wic\s*\)/gi, " ")
      .replace(/-\s*wic\b/gi, " ")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  };
  const cleanGenEdLabel = (raw?: string | null) => {
    if (!raw) return "";
    return raw
      .replace(/[‐‑‒–—―]/g, "-")
      .replace(/^gen(?:eral)?\s*ed(?:ucation)?\s*:\s*/i, "")
      .replace(/\(\s*wic\s*\)/gi, " ")
      .replace(/-\s*wic\b/gi, " ")
      .replace(/\s+/g, " ")
      .trim();
  };
  const splitGenEdTags = (raw?: string | null) => {
    if (!raw) return [];
    return raw
      .split(/[/,;|]+/)
      .map((part) => cleanGenEdLabel(part))
      .filter(Boolean);
  };
  const getGenEdNeedByCategory = (planData?: GeneratePlanResponse | null) => {
    const needByCategory: Record<string, number> = {};
    const status = planData?.gen_ed_status;
    if (!status) return needByCategory;
    for (const [category, counts] of Object.entries(status)) {
      const normalized = normGenEd(category);
      if (!normalized || !counts) continue;
      const required = Number(counts.required ?? 0);
      const completed = Number(counts.completed ?? 0);
      const planned = Number(counts.planned ?? 0);
      needByCategory[normalized] = Math.max(0, required - (completed + planned));
    }
    return needByCategory;
  };
  const genEdNeedByCategory = useMemo(
    () => getGenEdNeedByCategory(plan),
    [plan?.gen_ed_status]
  );
  const genEdCanonicalLabelByNorm = useMemo(() => {
    const byNorm: Record<string, string> = {};
    const add = (raw?: string | null) => {
      const cleaned = cleanGenEdLabel(raw);
      const normalized = normGenEd(cleaned);
      if (!cleaned || !normalized || byNorm[normalized]) return;
      byNorm[normalized] = cleaned;
    };
    Object.keys(catalog.gen_ed?.rules ?? {}).forEach((category) => add(category));
    Object.keys(catalog.gen_ed?.categories ?? {}).forEach((category) => add(category));
    Object.keys(plan?.gen_ed_status ?? {}).forEach((category) => add(category));
    return byNorm;
  }, [catalog.gen_ed?.categories, catalog.gen_ed?.rules, plan?.gen_ed_status]);
  const canonicalGenEdLabel = (raw?: string | null) => {
    const cleaned = cleanGenEdLabel(raw);
    const normalized = normGenEd(cleaned);
    if (!cleaned || !normalized) return "";
    return genEdCanonicalLabelByNorm[normalized] ?? cleaned;
  };
  const dedupeGenEdLabels = (rawLabels: string[]) => {
    const byNorm = new Map<string, string>();
    rawLabels.forEach((raw) => {
      const label = canonicalGenEdLabel(raw);
      const normalized = normGenEd(label);
      if (!normalized || byNorm.has(normalized)) return;
      byNorm.set(normalized, label);
    });
    return Array.from(byNorm.values());
  };
  const getCategoryNeedFromMap = (
    category: string | null | undefined,
    needByCategory: Record<string, number>
  ) => {
    const normalized = normGenEd(category);
    if (!normalized) return null;
    if (Object.prototype.hasOwnProperty.call(needByCategory, normalized)) {
      return Number(needByCategory[normalized] ?? 0);
    }
    return null;
  };
  const categoryHasNeed = (
    category: string | null | undefined,
    needByCategory: Record<string, number>
  ) => {
    const need = getCategoryNeedFromMap(category, needByCategory);
    return need === null || need > 0;
  };
  const pickCategoryByNeed = (
    rawCategories: string[],
    needByCategory: Record<string, number>,
    requirePositiveNeed: boolean
  ) => {
    const deduped = dedupeGenEdLabels(rawCategories);
    const candidates = deduped
      .map((label) => ({
        label,
        need: getCategoryNeedFromMap(label, needByCategory)
      }))
      .filter((entry) => {
        if (!requirePositiveNeed) return true;
        return entry.need === null || entry.need > 0;
      })
      .sort((a, b) => {
        const aNeed = a.need === null ? 1 : a.need;
        const bNeed = b.need === null ? 1 : b.need;
        if (aNeed !== bNeed) return bNeed - aNeed;
        return a.label.localeCompare(b.label);
      });
    if (candidates.length === 0) return null;
    return candidates[0].label;
  };
  const isSameGenEdCategory = (left?: string | null, right?: string | null) => {
    const leftNorm = normGenEd(left);
    const rightNorm = normGenEd(right);
    return Boolean(leftNorm) && leftNorm === rightNorm;
  };
  const formatGenEdNeedLabel = (
    category: string,
    needByCategory: Record<string, number>
  ) => {
    const canonical = canonicalGenEdLabel(category) || category;
    const need = getCategoryNeedFromMap(canonical, needByCategory);
    if (need === null) return canonical;
    if (need === 0) return `${canonical} (Satisfied)`;
    return `${canonical} (Need ${need})`;
  };
  const COURSE_CODE_PATTERN = /\b[A-Z]{2,4}\s?\d{3,4}\b/g;
  const normalizeCourseCode = (raw: string) =>
    raw
      .toUpperCase()
      .replace(/\s+/g, " ")
      .replace(/\b([A-Z]{2,4})\s*(\d{3,4})\b/, "$1 $2")
      .trim();
  const normalizeCodeSet = (codes: Iterable<string>): Set<string> => {
    const normalized = new Set<string>();
    for (const code of codes) {
      if (typeof code !== "string") continue;
      const canonical = normalizeCourseCode(code);
      if (!canonical) continue;
      normalized.add(canonical);
    }
    return normalized;
  };
  const codeSetHas = (codes: Set<string>, code: string): boolean => {
    if (!code) return false;
    if (codes.has(code)) return true;
    const normalized = normalizeCourseCode(code);
    if (codes.has(normalized)) return true;
    const compact = normalized.replace(/\s+/g, "");
    if (compact && codes.has(compact)) return true;
    return false;
  };
  const upsertSwappedElective = (record: SwappedElectiveRecord) => {
    setSwappedElectives((prev) => {
      const next = prev.filter(
        (entry) =>
          entry.addedCourseInstanceId !== record.addedCourseInstanceId
          && !(
            entry.termLabel === record.termLabel
            && normalizeCourseCode(entry.addedCourseCode) === normalizeCourseCode(record.addedCourseCode)
          )
      );
      return [...next, record];
    });
  };
  const removeSwappedElective = (record: SwappedElectiveRecord) => {
    setSwappedElectives((prev) =>
      prev.filter(
        (entry) =>
          entry.addedCourseInstanceId !== record.addedCourseInstanceId
          && !(
            entry.termLabel === record.termLabel
            && normalizeCourseCode(entry.addedCourseCode) === normalizeCourseCode(record.addedCourseCode)
          )
      )
    );
  };
  const findSwappedElective = (
    instanceId: string,
    term: string | null,
    code: string
  ): SwappedElectiveRecord | null => {
    const byInstance = swappedElectives.find((entry) => entry.addedCourseInstanceId === instanceId);
    if (byInstance) return byInstance;
    if (!term) return null;
    const normalizedCode = normalizeCourseCode(code);
    return (
      swappedElectives.find(
        (entry) =>
          entry.termLabel === term
          && normalizeCourseCode(entry.addedCourseCode) === normalizedCode
      ) ?? null
    );
  };
  const extractCourseCodesFromText = (text: string) => {
    const matches = text.toUpperCase().match(COURSE_CODE_PATTERN) ?? [];
    const normalized = matches.map((m) => normalizeCourseCode(m));
    return Array.from(new Set(normalized));
  };
  const extractGenEdFromSatisfies = (satisfies?: string[]) => {
    if (!Array.isArray(satisfies)) return [];
    const tags: string[] = [];
    satisfies.forEach((entry) => {
      if (typeof entry !== "string") return;
      const match = entry.match(/^GenEd:\s*(.+)$/i);
      if (match && match[1]) {
        const canonical = canonicalGenEdLabel(match[1]);
        if (canonical) tags.push(canonical);
      }
    });
    return dedupeGenEdLabels(tags);
  };
  const getCourseGenEdTags = (courseCode: string) => {
    const meta = catalog.course_meta?.[courseCode];
    const tags: string[] = [];
    if (Array.isArray(meta?.gen_ed_tags)) {
      meta.gen_ed_tags.forEach((tag) => {
        if (typeof tag === "string" && tag.trim()) {
          const canonical = canonicalGenEdLabel(tag);
          if (canonical) tags.push(canonical);
        }
      });
    }
    if (tags.length === 0 && typeof meta?.gen_ed === "string" && meta.gen_ed.trim()) {
      tags.push(...splitGenEdTags(meta.gen_ed));
    }
    if (catalog.gen_ed?.categories) {
      for (const [category, codes] of Object.entries(catalog.gen_ed.categories)) {
        if (codes?.includes(courseCode)) {
          const canonical = canonicalGenEdLabel(category);
          if (canonical) tags.push(canonical);
        }
      }
    }
    if (plan?.semester_plan) {
      for (const term of plan.semester_plan) {
        const match = term.courses?.find((c) => c.code === courseCode);
        if (match?.satisfies) {
          tags.push(...extractGenEdFromSatisfies(match.satisfies));
        }
      }
    }
    const reasonText = plan?.course_reasons?.[courseCode];
    if (reasonText && typeof reasonText === "string") {
      reasonText.split(";").forEach((part) => {
        const match = part.trim().match(/^GenEd:\s*(.+)$/i);
        if (match && match[1]) {
          const canonical = canonicalGenEdLabel(match[1]);
          if (canonical) tags.push(canonical);
        }
      });
    }
    return dedupeGenEdLabels(tags);
  };
  const getPrimaryGenEdCategory = (courseCode: string, override?: string | null) => {
    if (override && override.trim()) return canonicalGenEdLabel(override);
    const tags = getCourseGenEdTags(courseCode);
    if (tags.length === 0) return null;
    return pickCategoryByNeed(tags, genEdNeedByCategory, false) ?? tags[0];
  };
  const getCanonicalCourseGenEdTags = (courseCode: string) => getCourseGenEdTags(courseCode);
  const GEN_ED_CATEGORY_PREREQS: Record<string, { categories?: string[]; courses?: string[] }> = {
    "Historical Research": {
      categories: ["Historical Sources"],
    },
    "Case Studies in Textual Analysis": {
      categories: ["Principles of Textual Analysis"],
      courses: ["ENG 1002"],
    },
  };
  const excelOnlyCodeSet = useMemo(
    () =>
      new Set(
        (catalog.excel_only_codes ?? []).filter(
          (code): code is string => typeof code === "string" && code.trim().length > 0
        )
      ),
    [catalog.excel_only_codes]
  );
  const isExcelOnlyCourse = (courseCode: string) =>
    excelOnlyCodeSet.has(courseCode) || catalog.course_meta?.[courseCode]?.is_excel_only === true;
  const getCourseCredits = (courseCode: string) =>
    catalog.course_meta?.[courseCode]?.credits ?? 3;
  const getCourseSemesterAvailability = (courseCode: string) => {
    const terms = catalog.course_meta?.[courseCode]?.semester_availability;
    if (!Array.isArray(terms)) return [];
    return terms.filter((term): term is string => typeof term === "string" && term.trim().length > 0);
  };
  const getExcelElectiveNotes = (courseCode: string) => {
    const tags = plan?.excel_elective_tags?.[courseCode] ?? [];
    if (!Array.isArray(tags)) return [] as string[];
    return tags.filter((tag): tag is string => typeof tag === "string" && tag.trim().length > 0);
  };
  const isWaivedCourse = (courseCode: string) => {
    if (courseCode === "MAT 1000") return selection.waivedMat1000 && !completedCourses.includes(courseCode);
    if (courseCode === "ENG 1000") return selection.waivedEng1000 && !completedCourses.includes(courseCode);
    return false;
  };
  const getCourseCreditsForDisplay = (courseCode: string) =>
    isWaivedCourse(courseCode) ? 0 : getCourseCredits(courseCode);
  const buildPlannedCourse = (
    courseCode: string,
    overrideCategory?: string | null,
    instanceId?: string
  ): PlanCourse => {
    const credits = getCourseCredits(courseCode);
    const categories = overrideCategory
      ? dedupeGenEdLabels([overrideCategory])
      : getCourseGenEdTags(courseCode);
    const satisfies = categories.map((cat) => `GenEd: ${cat}`);
    const type = categories.length > 0 ? "GENED" : "PROGRAM";
    return {
      code: courseCode,
      name: catalog.courses[courseCode] ?? courseCode,
      credits,
      tags: ['Planned'],
      satisfies,
      type,
      instance_id: instanceId ?? createInstanceId()
    };
  };
  type PrereqCourseBlock = { type: "course"; code: string };
  type PrereqOrBlock = { type: "or"; courses?: string[]; items?: PrereqBlock[] };
  type PrereqAndBlock = { type: "and"; items?: PrereqBlock[] };
  type PrereqBlock = PrereqCourseBlock | PrereqOrBlock | PrereqAndBlock;
  type PrereqExprNode = string | { and: PrereqExprNode[] } | { or: PrereqExprNode[] };

  const dedupePrereqCodes = (codes: string[]) => {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const raw of codes) {
      if (typeof raw !== "string" || !raw.trim()) continue;
      const code = normalizeCourseCode(raw);
      if (!code || seen.has(code)) continue;
      seen.add(code);
      out.push(code);
    }
    return out;
  };
  const dedupeLabels = (labels: string[]) => {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const label of labels) {
      if (typeof label !== "string" || !label.trim()) continue;
      if (seen.has(label)) continue;
      seen.add(label);
      out.push(label);
    }
    return out;
  };
  const parsePrereqBlocksFromText = (text: string): PrereqBlock[] => {
    const cleaned = text
      .replace(/^\s*prerequisites?\s*:?\s*/i, "")
      .trim();
    if (!cleaned) return [];

    const forceOrList = /\bone of the following\b|\beither\b/i.test(cleaned);
    const andSplitRegex = forceOrList ? /\band\b/i : /,|\band\b/i;
    const andParts = cleaned
      .split(andSplitRegex)
      .map((part) => part.trim())
      .filter(Boolean);
    const sourceParts = andParts.length > 1 ? andParts : [cleaned];

    const blocks: PrereqBlock[] = [];
    for (const part of sourceParts) {
      const codes = dedupePrereqCodes(extractCourseCodesFromText(part));
      if (!codes.length) continue;
      const forceOr = /\bone of the following\b|\beither\b/i.test(part);
      const hasOr = /(?:\bor\b|\/)/i.test(part);
      if ((forceOr || hasOr) && codes.length >= 2) {
        blocks.push({ type: "or", courses: codes });
        continue;
      }
      codes.forEach((code) => blocks.push({ type: "course", code }));
    }
    return blocks;
  };
  const normalizePrereqBlock = (raw: unknown): PrereqBlock | null => {
    if (typeof raw === "string") {
      const code = normalizeCourseCode(raw);
      return code ? { type: "course", code } : null;
    }
    if (!raw || typeof raw !== "object") return null;
    const record = raw as Record<string, unknown>;
    const type = String(record.type ?? "").toLowerCase();

    if (type === "course") {
      const code = typeof record.code === "string" ? normalizeCourseCode(record.code) : "";
      return code ? { type: "course", code } : null;
    }

    if (type === "and") {
      const candidates = Array.isArray(record.items)
        ? record.items
        : (Array.isArray(record.blocks) ? record.blocks : []);
      const items = candidates
        .map((item) => normalizePrereqBlock(item))
        .filter((item): item is PrereqBlock => Boolean(item));
      if (!items.length) return null;
      return { type: "and", items };
    }

    if (type === "or") {
      const options: PrereqBlock[] = [];
      if (Array.isArray(record.courses)) {
        record.courses.forEach((course) => {
          const normalized = normalizePrereqBlock(course);
          if (normalized) options.push(normalized);
        });
      }
      ["items", "blocks", "options", "choices"].forEach((key) => {
        const value = record[key];
        if (!Array.isArray(value)) return;
        value.forEach((item) => {
          const normalized = normalizePrereqBlock(item);
          if (normalized) options.push(normalized);
        });
      });
      if (!options.length) return null;
      return { type: "or", items: options };
    }

    return null;
  };
  const normalizePrereqExprNode = (raw: unknown): PrereqExprNode | null => {
    if (typeof raw === "string") {
      const code = normalizeCourseCode(raw);
      return code ? code : null;
    }
    if (Array.isArray(raw)) {
      const items = raw
        .map((item) => normalizePrereqExprNode(item))
        .filter((item): item is PrereqExprNode => Boolean(item));
      if (!items.length) return null;
      return { and: items };
    }
    if (!raw || typeof raw !== "object") return null;
    const record = raw as Record<string, unknown>;
    if (Array.isArray(record.and)) {
      const items = record.and
        .map((item) => normalizePrereqExprNode(item))
        .filter((item): item is PrereqExprNode => Boolean(item));
      if (!items.length) return null;
      return { and: items };
    }
    if (Array.isArray(record.or)) {
      const items = record.or
        .map((item) => normalizePrereqExprNode(item))
        .filter((item): item is PrereqExprNode => Boolean(item));
      if (!items.length) return null;
      return { or: items };
    }
    const block = normalizePrereqBlock(raw);
    if (!block) return null;
    if (block.type === "course") {
      return block.code;
    }
    if (block.type === "or") {
      const options = getPrereqBlockOptions(block)
        .map((item) => normalizePrereqExprNode(item))
        .filter((item): item is PrereqExprNode => Boolean(item));
      if (!options.length) return null;
      return { or: options };
    }
    if (block.type === "and") {
      const items = getPrereqBlockItems(block)
        .map((item) => normalizePrereqExprNode(item))
        .filter((item): item is PrereqExprNode => Boolean(item));
      if (!items.length) return null;
      return { and: items };
    }
    return null;
  };
  const prereqSatisfied = (expr: unknown, availableCodes: Set<string>): boolean => {
    const normalizedAvailable = normalizeCodeSet(availableCodes);
    const node = normalizePrereqExprNode(expr);
    if (!node) return true;
    const evalNode = (current: PrereqExprNode): boolean => {
      if (typeof current === "string") {
        return codeSetHas(normalizedAvailable, current);
      }
      if ("and" in current) {
        return current.and.every((child) => evalNode(child));
      }
      if ("or" in current) {
        return current.or.some((child) => evalNode(child));
      }
      return true;
    };
    return evalNode(node);
  };
  const prereqExprNodeToBlock = (node: PrereqExprNode): PrereqBlock | null => {
    if (typeof node === "string") {
      return { type: "course", code: node };
    }
    if ("and" in node) {
      const items = node.and
        .map((item) => prereqExprNodeToBlock(item))
        .filter((item): item is PrereqBlock => Boolean(item));
      if (!items.length) return null;
      return { type: "and", items };
    }
    if ("or" in node) {
      const items = node.or
        .map((item) => prereqExprNodeToBlock(item))
        .filter((item): item is PrereqBlock => Boolean(item));
      if (!items.length) return null;
      if (items.every((item) => item.type === "course")) {
        return {
          type: "or",
          courses: dedupePrereqCodes(
            items.map((item) => (item.type === "course" ? item.code : ""))
          )
        };
      }
      return { type: "or", items };
    }
    return null;
  };
  const prereqExprToBlocks = (expr: unknown): PrereqBlock[] => {
    const node = normalizePrereqExprNode(expr);
    if (!node) return [];
    if (typeof node === "object" && "and" in node) {
      return node.and
        .map((item) => prereqExprNodeToBlock(item))
        .filter((item): item is PrereqBlock => Boolean(item))
        .flatMap((item) =>
          item.type === "and" && Array.isArray(item.items) ? item.items : [item]
        );
    }
    const one = prereqExprNodeToBlock(node);
    if (!one) return [];
    return one.type === "and" && Array.isArray(one.items) ? one.items : [one];
  };
  const normalizePrereqBlocks = (raw: unknown): PrereqBlock[] => {
    if (Array.isArray(raw)) {
      return raw
        .map((item) => normalizePrereqBlock(item))
        .filter((item): item is PrereqBlock => Boolean(item));
    }
    const one = normalizePrereqBlock(raw);
    if (!one) return [];
    if (one.type === "and" && Array.isArray(one.items)) {
      return one.items;
    }
    return [one];
  };
  const getPrereqBlockOptions = (block: PrereqBlock): PrereqBlock[] => {
    if (block.type !== "or") return [];
    const options = Array.isArray(block.items)
      ? block.items
      : (Array.isArray(block.courses)
          ? block.courses
              .map((code) => normalizePrereqBlock(code))
              .filter((item): item is PrereqBlock => Boolean(item))
          : []);
    return options;
  };
  const getPrereqBlockItems = (block: PrereqBlock): PrereqBlock[] => {
    if (block.type !== "and") return [];
    return Array.isArray(block.items) ? block.items : [];
  };
  const getPrereqBlockDisplayLabel = (block: PrereqBlock): string => {
    if (block.type === "course") return block.code;
    if (block.type === "or") {
      const labels = getPrereqBlockOptions(block)
        .map((option) => getPrereqBlockDisplayLabel(option))
        .filter(Boolean);
      return labels.join(" OR ");
    }
    if (block.type === "and") {
      const labels = getPrereqBlockItems(block)
        .map((item) => getPrereqBlockDisplayLabel(item))
        .filter(Boolean);
      return labels.join(" AND ");
    }
    return "";
  };
  const collectPrereqCodesFromBlock = (block: PrereqBlock): string[] => {
    if (block.type === "course") return [block.code];
    if (block.type === "or") {
      return dedupePrereqCodes(
        getPrereqBlockOptions(block).flatMap((option) => collectPrereqCodesFromBlock(option))
      );
    }
    if (block.type === "and") {
      return dedupePrereqCodes(
        getPrereqBlockItems(block).flatMap((item) => collectPrereqCodesFromBlock(item))
      );
    }
    return [];
  };
  const isPrereqBlockSatisfied = (block: PrereqBlock, satisfied: Set<string>): boolean => {
    if (block.type === "course") return codeSetHas(satisfied, block.code);
    if (block.type === "or") {
      const options = getPrereqBlockOptions(block);
      if (!options.length) return true;
      return options.some((option) => isPrereqBlockSatisfied(option, satisfied));
    }
    if (block.type === "and") {
      const items = getPrereqBlockItems(block);
      if (!items.length) return true;
      return items.every((item) => isPrereqBlockSatisfied(item, satisfied));
    }
    return true;
  };
  const getUnmetPrereqLabelsForBlock = (block: PrereqBlock, satisfied: Set<string>): string[] => {
    if (isPrereqBlockSatisfied(block, satisfied)) return [];
    if (block.type === "course") return [block.code];
    if (block.type === "and") {
      return getPrereqBlockItems(block).flatMap((item) => getUnmetPrereqLabelsForBlock(item, satisfied));
    }
    if (block.type === "or") {
      const label = getPrereqBlockDisplayLabel(block);
      return label ? [label] : [];
    }
    return [];
  };
  const getNeededPrereqCodesForBlock = (
    block: PrereqBlock,
    satisfied: Set<string>,
    preferredCodes?: Set<string>
  ): string[] => {
    if (isPrereqBlockSatisfied(block, satisfied)) return [];
    if (block.type === "course") return [block.code];
    if (block.type === "and") {
      return dedupePrereqCodes(
        getPrereqBlockItems(block).flatMap((item) =>
          getNeededPrereqCodesForBlock(item, satisfied, preferredCodes)
        )
      );
    }
    if (block.type === "or") {
      const allOptions = getPrereqBlockOptions(block);
      if (!allOptions.length) return [];
      let options = allOptions;
      if (preferredCodes && preferredCodes.size > 0) {
        const preferredOptions = allOptions.filter((option) =>
          collectPrereqCodesFromBlock(option).some((code) => preferredCodes.has(code))
        );
        if (preferredOptions.length > 0) {
          options = preferredOptions;
        }
      }
      let bestNeeded: string[] | null = null;
      let bestRank: [number, string] | null = null;
      for (const option of options) {
        const needed = dedupePrereqCodes(
          getNeededPrereqCodesForBlock(option, satisfied, preferredCodes)
        );
        const rank: [number, string] = [needed.length, getPrereqBlockDisplayLabel(option)];
        if (
          bestNeeded === null
          || bestRank === null
          || rank[0] < bestRank[0]
          || (rank[0] === bestRank[0] && rank[1] < bestRank[1])
        ) {
          bestNeeded = needed;
          bestRank = rank;
        }
      }
      return bestNeeded ?? [];
    }
    return [];
  };
  const getCoursePrereqBlocks = (courseCode: string): PrereqBlock[] => {
    const meta = catalog.course_meta?.[courseCode];
    const fromExpr = prereqExprToBlocks(meta?.prereq_expr);
    if (fromExpr.length > 0) return fromExpr;

    const fromBlocks = normalizePrereqBlocks(meta?.prereq_blocks);
    if (fromBlocks.length > 0) return fromBlocks;

    const structuredPrereqs = meta?.prereqs;
    const hasStructuredPrereqs =
      !!structuredPrereqs &&
      (Array.isArray(structuredPrereqs)
        ? structuredPrereqs.some((item) => typeof item === "object" && item !== null)
        : typeof structuredPrereqs === "object");
    if (hasStructuredPrereqs) {
      const fromStructuredPrereqs = normalizePrereqBlocks(structuredPrereqs);
      if (fromStructuredPrereqs.length > 0) return fromStructuredPrereqs;
    }

    const prereqList = Array.isArray(meta?.prereq_codes)
      ? meta?.prereq_codes
      : (Array.isArray(meta?.prereqs) ? meta?.prereqs : []);
    if (prereqList.length > 0) {
      return dedupePrereqCodes(
        prereqList.filter((item): item is string => typeof item === "string")
      ).map((code) => ({ type: "course", code }));
    }

    if (typeof meta?.prereq_text === "string" && meta.prereq_text.trim()) {
      return parsePrereqBlocksFromText(meta.prereq_text);
    }
    return [];
  };
  const isCoursePrereqSatisfiedWithAvailable = (
    courseCode: string,
    availableCodes: Set<string>
  ): boolean => {
    const meta = catalog.course_meta?.[courseCode];
    if (meta?.prereq_expr) {
      return prereqSatisfied(meta.prereq_expr, availableCodes);
    }

    const normalizedBlocks = normalizePrereqBlocks(meta?.prereq_blocks);
    if (normalizedBlocks.length > 0) {
      return normalizedBlocks.every((block) => isPrereqBlockSatisfied(block, availableCodes));
    }

    const prereqList = Array.isArray(meta?.prereq_codes)
      ? meta.prereq_codes
      : (Array.isArray(meta?.prereqs) ? meta.prereqs : []);
    if (prereqList.length > 0) {
      const normalized = dedupePrereqCodes(
        prereqList.filter((item): item is string => typeof item === "string")
      );
      return normalized.every((code) => availableCodes.has(code));
    }

    const fallbackBlocks = getCoursePrereqBlocks(courseCode);
    if (!fallbackBlocks.length) return true;
    return fallbackBlocks.every((block) => isPrereqBlockSatisfied(block, availableCodes));
  };
  const buildAvailableCodesBeforeTerm = (
    targetTermIdx: number,
    options?: { removedCode: string; removedTermIdx: number; removedInstanceId?: string | null }
  ): Set<string> => {
    const available = new Set<string>();

    effectiveCompleted.forEach((code) => {
      if (!isFreeElectivePlaceholder(code)) {
        const normalized = normalizeCourseCode(code);
        if (normalized) available.add(normalized);
      }
    });
    effectiveInProgress.forEach((code) => {
      if (!isFreeElectivePlaceholder(code)) {
        const normalized = normalizeCourseCode(code);
        if (normalized) available.add(normalized);
      }
    });

    const orderedTerms = [...(plan?.semester_plan ?? [])].sort(
      (a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term)
    );

    for (const sem of orderedTerms) {
      const semIdx = termIndexFromLabel(sem.term);
      if (semIdx >= targetTermIdx) continue;
      for (const course of sem.courses ?? []) {
        if (!course?.code) continue;
        if (isRemovedPlanCourse(course)) continue;
        if (isFreeElectivePlaceholder(course.code)) continue;

        if (options) {
          const normalizedRemovedCode = normalizeCourseCode(options.removedCode);
          const normalizedCourseCode = normalizeCourseCode(course.code);
          if (
            options.removedInstanceId
            && course.instance_id
            && course.instance_id === options.removedInstanceId
          ) {
            continue;
          }
          if (
            !options.removedInstanceId
            && semIdx >= options.removedTermIdx
            && normalizedCourseCode === normalizedRemovedCode
          ) {
            continue;
          }
        }

        const normalized = normalizeCourseCode(course.code);
        if (normalized) available.add(normalized);
      }
    }

    return available;
  };
  const getCoursePrereqs = (courseCode: string) => {
    const blocks = getCoursePrereqBlocks(courseCode);
    if (!blocks.length) return [];
    return dedupePrereqCodes(blocks.flatMap((block) => collectPrereqCodesFromBlock(block)));
  };
  const getCoursePrereqItems = (courseCode: string) => {
    const blocks = getCoursePrereqBlocks(courseCode);
    if (!blocks.length) return [];
    return dedupeLabels(
      blocks
        .map((block) => getPrereqBlockDisplayLabel(block))
        .filter(Boolean)
    );
  };
  const evaluatePrereqStatus = (
    courseCode: string,
    satisfied: Set<string>,
    preferredCodes?: Set<string>
  ) => {
    const blocks = getCoursePrereqBlocks(courseCode);
    if (!blocks.length) {
      return { prereqs: [] as string[], unmet: [] as string[], unmetCodes: [] as string[], satisfied: true };
    }
    const prereqs = dedupeLabels(
      blocks
        .map((block) => getPrereqBlockDisplayLabel(block))
        .filter(Boolean)
    );
    const unmet = dedupeLabels(
      blocks.flatMap((block) => getUnmetPrereqLabelsForBlock(block, satisfied))
    );
    const unmetCodes = dedupePrereqCodes(
      blocks.flatMap((block) => getNeededPrereqCodesForBlock(block, satisfied, preferredCodes))
    );
    return { prereqs, unmet, unmetCodes, satisfied: unmet.length === 0 };
  };
  const getNeededPrereqCodes = (
    courseCode: string,
    satisfied: Set<string>,
    preferredCodes?: Set<string>
  ) => {
    return evaluatePrereqStatus(courseCode, satisfied, preferredCodes).unmetCodes;
  };
  const resolveCourseName = (code: string) => catalog.courses[code] ?? code;
  const termIndexFromLabel = (term: string) => {
    const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
    if (!m) return 999999;
    const seasonOrder: Record<string, number> = { Spring: 0, Fall: 1 };
    return Number(m[2]) * 2 + (seasonOrder[m[1]] ?? 0);
  };
  const isPrereqSatisfied = (
    courseCode: string,
    targetTermIndex: number,
    completedSet: Set<string>,
    inProgressSet: Set<string>,
    planData: GeneratePlanResponse | null,
    removedList: string[] = removedCourses,
    preferredCodes?: Set<string>
  ) => {
    const plannedEarlier = new Set<string>();
    if (planData) {
      for (const term of planData.semester_plan) {
        const idx = termIndexFromLabel(term.term);
        if (idx >= targetTermIndex) continue;
        term.courses.forEach((c) => {
          if (!removedList.includes(c.instance_id) && !removedCodeSet.has(c.code)) {
            plannedEarlier.add(c.code);
          }
        });
      }
    }
    const satisfied = new Set<string>([
      ...Array.from(completedSet),
      ...Array.from(inProgressSet),
      ...Array.from(plannedEarlier),
    ]);
    return evaluatePrereqStatus(courseCode, satisfied, preferredCodes);
  };
  const getPrereqStatusForTerm = (courseCode: string, term: string) => {
    const completedSet = new Set(effectiveCompleted);
    const inProgressSet = new Set(effectiveInProgress);
    const preferredCodes = new Set<string>([...effectiveCompleted, ...effectiveInProgress]);
    for (const sem of plan?.semester_plan ?? []) {
      for (const course of sem.courses ?? []) {
        if (!course?.code || isRemovedPlanCourse(course)) continue;
        preferredCodes.add(course.code);
      }
    }
    return isPrereqSatisfied(
      courseCode,
      termIndexFromLabel(term),
      completedSet,
      inProgressSet,
      plan,
      removedCourses,
      preferredCodes
    );
  };

  const getDownstreamDependents = (courseCode: string, term: string, removedInstanceId?: string | null) => {
    if (!plan?.semester_plan) return [] as { code: string; instanceId?: string; term?: string }[];
    const removalIdx = termIndexFromLabel(term);
    const dependents: { code: string; instanceId?: string; term?: string }[] = [];
    const orderedTerms = [...plan.semester_plan].sort(
      (a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term)
    );

    for (const sem of orderedTerms) {
      const semIdx = termIndexFromLabel(sem.term);
      const activeCourses = (sem.courses ?? []).filter((course) => {
        if (!course?.code) return false;
        if (isRemovedPlanCourse(course)) return false;
        return true;
      });

      if (semIdx > removalIdx) {
        for (const course of activeCourses) {
          if (isFreeElectivePlaceholder(course.code)) continue;
          if (effectiveCompleted.includes(course.code) || effectiveInProgress.includes(course.code)) continue;
          const baselineAvailable = buildAvailableCodesBeforeTerm(semIdx);
          const afterRemovalAvailable = buildAvailableCodesBeforeTerm(semIdx, {
            removedCode: courseCode,
            removedTermIdx: removalIdx,
            removedInstanceId
          });
          const baselineOk = isCoursePrereqSatisfiedWithAvailable(course.code, baselineAvailable);
          const afterOk = isCoursePrereqSatisfiedWithAvailable(course.code, afterRemovalAvailable);
          if (baselineOk && !afterOk) {
            dependents.push({ code: course.code, instanceId: course.instance_id, term: sem.term });
          }
        }
      }
    }

    const seen = new Set<string>();
    return dependents.filter((d) => {
      if (seen.has(d.code)) return false;
      seen.add(d.code);
      return true;
    });
  };
  const shiftTerm = (season: string, year: number, deltaTerms: number) => {
    const idx = termIndex(season, year);
    return termFromIndex(idx + deltaTerms);
  };
  const buildTermLabels = (baseSeason: string, baseYear: number, count: number) => {
    const labels: string[] = [];
    const baseIdx = termIndex(baseSeason, baseYear);
    for (let i = 0; i < count; i += 1) {
      const idx = baseIdx + i;
      const season = idx % 2 === 1 ? "Fall" : "Spring";
      const year = Math.floor(idx / 2);
      labels.push(`${season} ${year}`);
    }
    return labels;
  };
  const termsCompleted = useMemo(() => {
    const now = new Date();
    const currentSeason = now.getMonth() + 1 <= 5 ? "Spring" : "Fall";
    const currentYear = now.getFullYear();
    const startIdx = termIndex(startTermSeason, startTermYear);
    const currentIdx = termIndex(currentSeason, currentYear);
    return Math.max(0, currentIdx - startIdx);
  }, [startTermSeason, startTermYear]);
  const MAX_TOTAL_TERMS = 8;
  const maxPlanTerms = MAX_TOTAL_TERMS;

  const { effectiveCompleted, effectiveInProgress } = useMemo(() => {
    if (inProgressCourses.length > 0) {
      const completed = completedCourses.filter((c) => !inProgressCourses.includes(c));
      const impliedCompleted = new Set<string>();
      if (selection.waivedMat1000) impliedCompleted.add("MAT 1000");
      if (selection.waivedEng1000) impliedCompleted.add("ENG 1000");
      impliedCompleted.forEach((code) => {
        if (!completed.includes(code)) completed.push(code);
      });
      return { effectiveCompleted: completed, effectiveInProgress: inProgressCourses };
    }
    const threshold = selection.maxCreditsPerSemester * termsCompleted;
    let running = 0;
    const completed: string[] = [];
    const inProgress: string[] = [];
    const impliedCompleted = new Set<string>();
    if (selection.waivedMat1000) impliedCompleted.add("MAT 1000");
    if (selection.waivedEng1000) impliedCompleted.add("ENG 1000");
    for (const code of completedCourses) {
      const credits = getCourseCreditsForDisplay(code);
      if (running + credits <= threshold) {
        completed.push(code);
        running += credits;
      } else {
        inProgress.push(code);
      }
    }
    impliedCompleted.forEach((code) => {
      if (!completed.includes(code) && !inProgress.includes(code)) {
        completed.push(code);
      }
    });
    return { effectiveCompleted: completed, effectiveInProgress: inProgress };
  }, [completedCourses, inProgressCourses, selection.maxCreditsPerSemester, termsCompleted, catalog.course_meta, selection.waivedMat1000, selection.waivedEng1000]);

  const inProgressCredits = useMemo(() => {
    return effectiveInProgress.reduce((sum, code) => {
      return sum + getCourseCreditsForDisplay(code);
    }, 0);
  }, [effectiveInProgress, catalog.course_meta, selection.waivedMat1000, selection.waivedEng1000, completedCourses]);

  const planningStartTerm = useMemo(() => {
    const now = new Date();
    const currentSeason = now.getMonth() + 1 <= 5 ? "Spring" : "Fall";
    const currentYear = now.getFullYear();
    const startIdx = termIndex(startTermSeason, startTermYear);
    const currentIdx = termIndex(currentSeason, currentYear);
    let season = startTermSeason;
    let year = startTermYear;
    if (startIdx < currentIdx) {
      season = currentSeason;
      year = currentYear;
    }
    return { season, year };
  }, [startTermSeason, startTermYear]);

  const effectiveStartForPlanning = useMemo(() => {
    const startLabel = `${planningStartTerm.season} ${planningStartTerm.year}`;
    const hasInProgressInStartTerm = effectiveInProgress.some((code) => {
      const term = inProgressOverrides[code] ?? startLabel;
      return term === startLabel;
    });
    if (!hasInProgressInStartTerm) return planningStartTerm;
    return shiftTerm(planningStartTerm.season, planningStartTerm.year, 1);
  }, [planningStartTerm, effectiveInProgress, inProgressOverrides]);

  const planningCompleted = useMemo(
    () => Array.from(new Set([...effectiveCompleted, ...effectiveInProgress])),
    [effectiveCompleted, effectiveInProgress]
  );

  const prereqWarnings = useMemo(() => {
    if (!plan) return {} as Record<string, { unmet: string[] }>;
    const warnings: Record<string, { unmet: string[] }> = {};
    const satisfied = new Set([...effectiveCompleted, ...effectiveInProgress]);
    const orderedTerms = [...plan.semester_plan].sort(
      (a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term)
    );
    for (const term of orderedTerms) {
      for (const course of term.courses) {
        if (isRemovedPlanCourse(course)) continue;
        if (satisfied.has(course.code)) continue;
        const status = evaluatePrereqStatus(course.code, satisfied);
        if (status.unmet.length > 0) {
          warnings[course.code] = { unmet: status.unmet };
        }
      }
      term.courses.forEach((course) => {
        if (!isRemovedPlanCourse(course)) {
          satisfied.add(course.code);
        }
      });
    }
    for (const warning of plan.warnings ?? []) {
      if (warning.type !== "PREREQ_UNMET") continue;
      if (!warning.course || !warning.unmet?.length) continue;
      if (!warnings[warning.course]) {
        warnings[warning.course] = { unmet: warning.unmet };
      }
    }
    return warnings;
  }, [plan, effectiveCompleted, effectiveInProgress, removedCourses, removedCodeSet, catalog.course_meta]);

  const creditsDone = useMemo(() => {
    const unique = new Set([...completedCourses, ...inProgressCourses]);
    let total = 0;
    unique.forEach((code) => {
      total += getCourseCreditsForDisplay(code);
    });
    return total;
  }, [completedCourses, inProgressCourses, catalog.course_meta, selection.waivedMat1000, selection.waivedEng1000]);

  const impliedStart = useMemo(() => {
    const creditsPerTerm = Math.max(1, selection.maxCreditsPerSemester);
    const completedTerms = Math.floor(creditsDone / creditsPerTerm);
    const implied = shiftTerm(selection.startTermSeason, selection.startTermYear, -completedTerms);
    return {
      ...implied,
      completedTerms,
      creditsPerTerm
    };
  }, [creditsDone, selection.startTermSeason, selection.startTermYear, selection.maxCreditsPerSemester]);

  const impliedStartKey = `${impliedStart.season}-${impliedStart.year}-${impliedStart.completedTerms}`;

  const applyHighCreditGenEdDefaults = (resp: GeneratePlanResponse) => {
    const orderedTerms = [...(resp.semester_plan ?? [])].sort(
      (a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term)
    );
    const responseNeedByCategory = getGenEdNeedByCategory(resp);

    const prereqDependentCodes = new Set<string>();
    for (const term of orderedTerms) {
      for (const course of term.courses ?? []) {
        const prereqs = getCoursePrereqs(course.code);
        prereqs.forEach((p) => prereqDependentCodes.add(p));
      }
    }

    const userAddedInstanceIds = new Set<string>(
      (overrides.add ?? [])
        .map((entry) => entry.instance_id)
        .filter((id): id is string => typeof id === "string" && id.trim().length > 0)
    );
    const userAddedCodes = new Set<string>(
      (overrides.add ?? [])
        .map((entry) => entry.code)
        .filter((code): code is string => typeof code === "string" && code.trim().length > 0)
    );
    const userAddedByTerm = new Map<string, Set<string>>();
    (overrides.add ?? []).forEach((entry) => {
      if (!entry.term || typeof entry.term !== "string") return;
      if (!entry.code || typeof entry.code !== "string") return;
      if (!userAddedByTerm.has(entry.term)) {
        userAddedByTerm.set(entry.term, new Set<string>());
      }
      userAddedByTerm.get(entry.term)?.add(entry.code);
    });
    const userRemovedCodes = new Set<string>(
      (overrides.remove ?? [])
        .map((entry) => entry.code)
        .filter((code): code is string => typeof code === "string" && code.trim().length > 0)
    );
    const userAddedGenEdCodes = new Set<string>();
    (overrides.add ?? []).forEach((entry) => {
      if (!entry.code || typeof entry.code !== "string") return;
      if (entry.gen_ed_category) {
        userAddedGenEdCodes.add(entry.code);
        return;
      }
      if (getCourseGenEdTags(entry.code).length > 0) {
        userAddedGenEdCodes.add(entry.code);
      }
    });

    const blockedCodes = new Set<string>([
      ...planningCompleted,
      ...effectiveInProgress,
      ...userRemovedCodes,
      ...removedCodeSet
    ]);
    const fixedCodes = new Set<string>([...userAddedCodes]);
    orderedTerms.forEach((term) =>
      term.courses?.forEach((course) => {
        if (!course.code) return;
        if (course.type && course.type !== "GENED") {
          fixedCodes.add(course.code);
        }
      })
    );
    const assignedGenEdCodes = new Set<string>([...userAddedGenEdCodes]);

    const electiveCourseCodes = new Set<string>(
      (resp.elective_course_codes ?? []).filter(
        (code) => typeof code === "string" && code.trim().length > 0
      )
    );
    const getCourseNumberValue = (code: string) => {
      const match = code.match(/(\d{3,4})/);
      return match ? Number(match[1]) : Number.POSITIVE_INFINITY;
    };
    const pickBestByCredits = (codes: string[]) =>
      [...codes].sort((a, b) => {
        const aCredits = catalog.course_meta?.[a]?.credits ?? 3;
        const bCredits = catalog.course_meta?.[b]?.credits ?? 3;
        if (aCredits != bCredits) return bCredits - aCredits;
        return a.localeCompare(b);
      })[0];
    const pickBestByPrereqs = (codes: string[]) =>
      [...codes].sort((a, b) => {
        const aCount = getCoursePrereqs(a).length;
        const bCount = getCoursePrereqs(b).length;
        if (aCount != bCount) return aCount - bCount;
        const aCredits = catalog.course_meta?.[a]?.credits ?? 3;
        const bCredits = catalog.course_meta?.[b]?.credits ?? 3;
        if (aCredits != bCredits) return aCredits - bCredits;
        return a.localeCompare(b);
      })[0];
    const pickBestByHistoricalResearch = (codes: string[]) =>
      [...codes].sort((a, b) => {
        const aLevel = getCourseNumberValue(a);
        const bLevel = getCourseNumberValue(b);
        if (aLevel != bLevel) return aLevel - bLevel;
        const aCount = getCoursePrereqs(a).length;
        const bCount = getCoursePrereqs(b).length;
        if (aCount != bCount) return aCount - bCount;
        const aCredits = catalog.course_meta?.[a]?.credits ?? 3;
        const bCredits = catalog.course_meta?.[b]?.credits ?? 3;
        if (aCredits != bCredits) return aCredits - bCredits;
        return a.localeCompare(b);
      })[0];
    const pickBestForCategory = (category: string | undefined | null, codes: string[]) => {
      if (isSameGenEdCategory(category, "historical research")) {
        return pickBestByHistoricalResearch(codes);
      }
      return pickBestByCredits(codes);
    };

    const updatedTerms = (resp.semester_plan ?? []).map((term) => {
      const nextCourses = (term.courses ?? []).map((course) => {
        if (course.type !== "GENED") return course;

        // Respect manual GenEd overrides: never auto-replace a user-confirmed GenEd.
        const userAddedInTerm = userAddedByTerm.get(term.term);
        if (course.instance_id && userAddedInstanceIds.has(course.instance_id)) {
          return course;
        }
        if (userAddedInTerm && userAddedInTerm.has(course.code)) {
          return course;
        }

        const categories = dedupeGenEdLabels([
          ...extractGenEdFromSatisfies(course.satisfies),
          ...getCourseGenEdTags(course.code)
        ]);
        const category =
          pickCategoryByNeed(categories, responseNeedByCategory, true)
          ?? pickCategoryByNeed(categories, responseNeedByCategory, false);
        if (!category) return course;
        if (!categoryHasNeed(category, responseNeedByCategory)) return course;

        const categoryCodes = getGenEdCategoryCourses(category)
          .filter((code) => code && !blockedCodes.has(code));
        if (categoryCodes.length === 0) return course;

        const pickCandidate = (codes: string[]) => {
          const avoid = new Set([...fixedCodes, ...assignedGenEdCodes]);
          const primary = codes.filter((code) => !avoid.has(code));
          if (primary.length > 0) return pickBestForCategory(category, primary);
          const secondary = codes.filter((code) => !assignedGenEdCodes.has(code));
          if (secondary.length > 0) return pickBestForCategory(category, secondary);
          return pickBestForCategory(category, codes);
        };

        const importantCandidates = categoryCodes.filter((code) => prereqDependentCodes.has(code));
        let bestCode: string | undefined;
        if (importantCandidates.length > 0) {
          bestCode = pickCandidate(importantCandidates);
        } else {
          const electiveCandidates = categoryCodes.filter((code) => electiveCourseCodes.has(code));
          if (electiveCandidates.length > 0) {
            bestCode = pickCandidate(electiveCandidates);
          } else {
            bestCode = pickCandidate(categoryCodes);
          }
        }
        if (!bestCode) return course;

        assignedGenEdCodes.add(bestCode);
        if (bestCode === course.code) return course;

        const replacement = buildPlannedCourse(bestCode, category, course.instance_id ?? createInstanceId());
        return {
          ...course,
          ...replacement,
          instance_id: course.instance_id ?? replacement.instance_id,
          source_reason: course.source_reason
        };
      });

      const credits = nextCourses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
      return { ...term, courses: nextCourses, credits };
    });


    const termLabels = buildTermLabels(startTermSeason, startTermYear, maxPlanTerms);
    if (termLabels.length === 0) {
      return { ...resp, semester_plan: updatedTerms };
    }

    const termMap = new Map<string, { term: string; courses: PlanCourse[]; credits: number }>();
    updatedTerms.forEach((term) => {
      termMap.set(term.term, {
        ...term,
        courses: [...(term.courses ?? [])],
        credits: term.courses?.reduce((sum, c) => sum + (c.credits ?? 3), 0) ?? 0
      });
    });
    termLabels.forEach((label) => {
      if (!termMap.has(label)) {
        termMap.set(label, { term: label, courses: [], credits: 0 });
      }
    });

    const usedPlaceholderCodes = new Set<string>();
    let maxIndex = 0;
    termMap.forEach((term) => {
      term.courses.forEach((course) => {
        if (!course.code) return;
        usedPlaceholderCodes.add(course.code);
        const match = course.code.toUpperCase().match(/^FREE ELECTIVE\s+(\d+)$/);
        if (match) {
          maxIndex = Math.max(maxIndex, Number(match[1]));
        }
      });
    });

    const occupiedInProgressByTerm = new Map<string, number>();
    for (const code of effectiveInProgress) {
      if (!code || !code.trim()) continue;
      const term = inProgressOverrides[code] ?? currentTermLabel;
      const credits = getCourseCreditsForDisplay(code);
      occupiedInProgressByTerm.set(term, (occupiedInProgressByTerm.get(term) ?? 0) + credits);
    }

    const currentIdx = termIndexFromLabel(currentTermLabel);
    for (const label of termLabels) {
      const entry = termMap.get(label);
      if (!entry) continue;
      let termCredits = entry.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
      if (termIndexFromLabel(label) < currentIdx) {
        entry.credits = termCredits;
        continue;
      }

      const occupiedCredits = occupiedInProgressByTerm.get(label) ?? 0;
      const availableMin = Math.max(0, minCreditsPerTerm - occupiedCredits);
      const availableMax = Math.max(0, selection.maxCreditsPerSemester - occupiedCredits);

      if (termCredits >= availableMin) {
        entry.credits = termCredits;
        continue;
      }
      while (termCredits < availableMin && termCredits + 3 <= availableMax) {
        maxIndex += 1;
        let placeholderCode = `FREE ELECTIVE ${maxIndex}`;
        while (usedPlaceholderCodes.has(placeholderCode)) {
          maxIndex += 1;
          placeholderCode = `FREE ELECTIVE ${maxIndex}`;
        }
        usedPlaceholderCodes.add(placeholderCode);
        entry.courses.push({
          code: placeholderCode,
          name: 'Free Elective',
          credits: 3,
          tags: ['Planned'],
          satisfies: [],
          type: 'FREE_ELECTIVE',
          instance_id: createInstanceId()
        });
        termCredits += 3;
      }
      entry.credits = termCredits;
    }

    const finalTerms = termLabels
      .map((label) => termMap.get(label))
      .filter((term): term is { term: string; courses: PlanCourse[]; credits: number } => Boolean(term));

    const dedupedTerms: { term: string; courses: PlanCourse[]; credits: number }[] = [];
    const seenCodes = new Set<string>();
    for (const term of finalTerms) {
      const filtered: PlanCourse[] = [];
      for (const course of term.courses ?? []) {
        if (!course?.code) continue;
        if (!seenCodes.has(course.code)) {
          seenCodes.add(course.code);
          filtered.push(course);
          continue;
        }

        const categories = dedupeGenEdLabels([
          ...extractGenEdFromSatisfies(course.satisfies),
          ...getCourseGenEdTags(course.code)
        ]);
        const category =
          pickCategoryByNeed(categories, responseNeedByCategory, true)
          ?? pickCategoryByNeed(categories, responseNeedByCategory, false);
        if (!category) {
          continue;
        }
        if (!categoryHasNeed(category, responseNeedByCategory)) {
          continue;
        }

        const categoryCodes = getGenEdCategoryCourses(category)
          .filter((code) => code && !blockedCodes.has(code));
        if (categoryCodes.length == 0) {
          continue;
        }

        const avoid = new Set([...seenCodes, ...fixedCodes, ...assignedGenEdCodes]);
        const candidates = categoryCodes.filter((code) => !avoid.has(code));
        if (candidates.length == 0) {
          continue;
        }

        let replacementCode: string | undefined;
        const important = candidates.filter((code) => prereqDependentCodes.has(code));
        if (important.length > 0) {
          replacementCode = pickBestForCategory(category, important);
        } else {
          const elective = candidates.filter((code) => electiveCourseCodes.has(code));
          if (elective.length > 0) {
            replacementCode = pickBestForCategory(category, elective);
          } else {
            replacementCode = pickBestForCategory(category, candidates);
          }
        }

        if (!replacementCode) {
          continue;
        }

        assignedGenEdCodes.add(replacementCode);
        seenCodes.add(replacementCode);
        const replacement = buildPlannedCourse(
          replacementCode,
          category,
          course.instance_id ?? createInstanceId()
        );
        filtered.push({
          ...course,
          ...replacement,
          instance_id: course.instance_id ?? replacement.instance_id,
          source_reason: course.source_reason
        });
      }
      const credits = filtered.reduce((sum, c) => sum + (c.credits ?? 3), 0);
      dedupedTerms.push({ ...term, courses: filtered, credits });
    }

    return { ...resp, semester_plan: dedupedTerms };
  };


  useEffect(() => {
    if (appliedImpliedStartKey === impliedStartKey) return;
    setDismissedImpliedStart(false);
  }, [appliedImpliedStartKey, impliedStartKey]);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      setLoading(true);
      setError(null);
      lastRemovedSnapshot.current = removedCourses;
      try {
        const resp = await generatePlan({
          catalog_id: catalog.catalog_id,
          majors: selection.majors,
          minors: selection.minors,
          completed_courses: planningCompleted,
          in_progress_courses: effectiveInProgress,
          in_progress_terms: inProgressOverrides,
          current_term_label: currentTermLabel,
          max_credits_per_semester: selection.maxCreditsPerSemester,
          start_term_season: effectiveStartForPlanning.season,
          start_term_year: effectiveStartForPlanning.year,
          waived_mat1000: selection.waivedMat1000,
          waived_eng1000: selection.waivedEng1000,
          overrides
        });
        if (cancelled) return;
        const pendingAtomicAdd = pendingAtomicAddRef.current;
        if (pendingAtomicAdd) {
          const addedInExpectedTerm = (resp.semester_plan ?? []).some(
            (term) =>
              term.term === pendingAtomicAdd.expectedTerm &&
              (term.courses ?? []).some((course) => course.code === pendingAtomicAdd.expectedCode)
          );
          if (!addedInExpectedTerm) {
            const availabilityWarning = (resp.warnings ?? []).find(
              (warning) =>
                warning?.type === "OVERRIDE_ADD_TERM_UNAVAILABLE" &&
                warning?.course === pendingAtomicAdd.expectedCode &&
                warning?.term === pendingAtomicAdd.expectedTerm
            );
            const offeredTerms = Array.isArray(availabilityWarning?.offered_terms)
              ? availabilityWarning.offered_terms.filter(
                  (value): value is string => typeof value === "string" && value.trim().length > 0
                )
              : [];
            pendingAtomicAddRef.current = null;
            suppressNextSummaryRef.current = true;
            setOverrides(pendingAtomicAdd.previousOverrides);
            setRemovedCourses(pendingAtomicAdd.previousRemovedCourses);
            setSwappedElectives(pendingAtomicAdd.previousSwappedElectives);
            const reasonText =
              offeredTerms.length > 0
                ? `Offered only in: ${offeredTerms.join(", ")}.`
                : "The backend rejected the add operation.";
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: `Could not add ${pendingAtomicAdd.expectedCode} to ${pendingAtomicAdd.expectedTerm}. ${reasonText} No changes were applied.`,
                timestamp: new Date(),
              },
            ]);
            return;
          }
          pendingAtomicAddRef.current = null;
        }
        setPlan(applyHighCreditGenEdDefaults(resp));
        setRemovedCourses([]);
        lastRemovedSnapshot.current = [];
        setPendingRemoval(null);
        setReplacementTarget(null);
        setReplacementCategories([]);
        setReplacementCategory(null);
        setReplacementOptions([]);
        setPendingReplacement(null);
        setPendingAddCourse(null);
        setPendingAddTerm(null);

        const summary = resp.summary ?? {};
        if (suppressNextSummaryRef.current) {
          suppressNextSummaryRef.current = false;
        } else {
          setMessages([
            {
              role: 'assistant',
              content:
                `Done. I found requirements referenced in the catalog for your selected programs.\n\n` +
                `Required courses detected: ${summary.total_required ?? 0}\n` +
                `Already completed (counting toward requirements): ${summary.completed ?? 0}\n` +
                `Remaining courses: ${summary.remaining ?? 0}\n\n` +
                `You can download a PDF once you review the plan.`,
              timestamp: new Date()
            }
          ]);
        }
      } catch (e: any) {
        if (cancelled) return;
        const pendingAtomicAdd = pendingAtomicAddRef.current;
        if (pendingAtomicAdd) {
          pendingAtomicAddRef.current = null;
          suppressNextSummaryRef.current = true;
          setOverrides(pendingAtomicAdd.previousOverrides);
          setRemovedCourses(pendingAtomicAdd.previousRemovedCourses);
          setSwappedElectives(pendingAtomicAdd.previousSwappedElectives);
        } else {
          setRemovedCourses(lastRemovedSnapshot.current);
        }
        setError(e?.message ?? 'Failed to generate plan.');
        setMessages([
          {
            role: 'assistant',
            content:
              `I couldn’t generate the plan. ${e?.message ?? ''}\n\n` +
              `Tip: make sure the backend API is running at ${import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'}.`,
            timestamp: new Date()
          }
        ]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [
    catalog.catalog_id,
    selection.majors,
    selection.minors,
    planningCompleted,
    selection.maxCreditsPerSemester,
    effectiveStartForPlanning.season,
    effectiveStartForPlanning.year,
    selection.waivedMat1000,
    selection.waivedEng1000,
    effectiveInProgress,
    inProgressOverrides,
    currentTermLabel,
    overrides
  ]);

  useEffect(() => {
    if (!plan?.semester_plan?.length) return;
    const maxCredits = selection.maxCreditsPerSemester;
    if (!maxCredits) return;

    const removedInstanceIds = new Set<string>(removedCourses);
    (overrides.remove ?? []).forEach((entry) => {
      if (entry.instance_id && entry.instance_id.trim()) {
        removedInstanceIds.add(entry.instance_id);
      }
    });

    const userAddedInstanceIds = new Set<string>(
      (overrides.add ?? [])
        .map((entry) => entry.instance_id)
        .filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
    );
    const userAddedByTerm = new Map<string, Set<string>>();
    (overrides.add ?? []).forEach((entry) => {
      if (!entry.term || typeof entry.term !== 'string') return;
      if (!entry.code || typeof entry.code !== 'string') return;
      if (!userAddedByTerm.has(entry.term)) {
        userAddedByTerm.set(entry.term, new Set<string>());
      }
      userAddedByTerm.get(entry.term)?.add(entry.code);
    });

    const additions: string[] = [];
    plan.semester_plan.forEach((term) => {
      const courses = term.courses ?? [];
      let termCredits = 0;
      for (const course of courses) {
        if (!course?.code) continue;
        const instanceId = course.instance_id;
        if (instanceId && removedInstanceIds.has(instanceId)) continue;
        if (removedCodeSet.has(course.code)) continue;
        const credits = course.credits ?? catalog.course_meta?.[course.code]?.credits ?? 3;
        termCredits += credits;
      }

      if (termCredits <= maxCredits) return;

      const isFreeLike = (course: any) =>
        course.type === 'FREE' ||
        course.type === 'FREE_ELECTIVE' ||
        isFreeElectivePlaceholder(course.code);

      const candidates = courses
        .filter((course) => {
          if (!course?.code) return false;
          const instanceId = course.instance_id;
          if (instanceId && removedInstanceIds.has(instanceId)) return false;
          if (removedCodeSet.has(course.code)) return false;
          if (effectiveInProgress.includes(course.code)) return false;
          if (effectiveCompleted.includes(course.code)) return false;
          if (instanceId && userAddedInstanceIds.has(instanceId)) return false;
          const termAdded = userAddedByTerm.get(term.term);
          if (termAdded && termAdded.has(course.code)) return false;
          return (
            isFreeLike(course) ||
            course.type === 'GENED'
          );
        })
        .sort((a, b) => {
          const rank = (course: any) => {
            if (isFreeLike(course)) return 0;
            if (course.type === 'GENED') return 1;
            return 99;
          };
          const rankDiff = rank(a) - rank(b);
          if (rankDiff != 0) return rankDiff;
          const aCredits = a.credits ?? catalog.course_meta?.[a.code]?.credits ?? 3;
          const bCredits = b.credits ?? catalog.course_meta?.[b.code]?.credits ?? 3;
          return bCredits - aCredits;
        });

      for (const course of candidates) {
        if (termCredits <= maxCredits) break;
        const credits = course.credits ?? catalog.course_meta?.[course.code]?.credits ?? 3;
        const instanceId = course.instance_id ?? null;
        addOverrideRemove(term.term, instanceId, course.code);
        if (instanceId) {
          removedInstanceIds.add(instanceId);
          additions.push(instanceId);
        }
        termCredits -= credits;
      }
    });

    if (additions.length > 0) {
      setRemovedCourses((prev) => {
        const next = new Set(prev);
        additions.forEach((id) => next.add(id));
        return Array.from(next);
      });
    }
  }, [
    plan?.semester_plan,
    selection.maxCreditsPerSemester,
    catalog.course_meta,
    overrides.add,
    overrides.remove,
    removedCourses,
    removedCodeSet,
    effectiveInProgress,
    effectiveCompleted
  ]);

  const courseObjects: Course[] = useMemo(() => {
    const out: Course[] = [];
    const addedCodes = new Set<string>();
    const addedInstances = new Set<string>();
    const plannedCodes = new Set<string>();
    const inProgressSet = new Set(effectiveInProgress);
    for (const sem of plan?.semester_plan ?? []) {
      for (const course of sem.courses) {
        plannedCodes.add(course.code);
      }
    }
    const selectedStartTermLabel = `${startTermSeason} ${startTermYear}`;

    // Completed courses bucket (shown as the student's first semester)
    for (const code of effectiveCompleted) {
      if (!code || !code.trim()) continue;
      const meta = catalog.course_meta?.[code];
      const overrideTerm = completedOverrides[code];
      const targetTerm = overrideTerm ?? selectedStartTermLabel;
      const instanceId = completedInstanceId(code);
      out.push({
        instanceId,
        code,
        name: catalog.courses[code] ?? code,
        credits: getCourseCreditsForDisplay(code),
        tags: ['Completed'],
        electiveNotes: getExcelElectiveNotes(code),
        semester: targetTerm,
        status: 'completed',
        prerequisites: getCoursePrereqItems(code),
        prereqText: meta?.prereq_text ?? null,
        reason: plan?.course_reasons?.[code]
      });
      addedCodes.add(code);
    }

    // In-progress courses not already in the plan/completed list
    for (const code of effectiveInProgress) {
      if (!code || !code.trim()) continue;
      if (addedCodes.has(code)) continue;
      if (plannedCodes.has(code)) continue;
      const meta = catalog.course_meta?.[code];
      const overrideTerm = inProgressOverrides[code];
      const targetTerm = overrideTerm ?? currentTermLabel;
      const instanceId = inProgressInstanceId(code);
      out.push({
        instanceId,
        code,
        name: catalog.courses[code] ?? code,
        credits: getCourseCreditsForDisplay(code),
        tags: ['In Progress'],
        electiveNotes: getExcelElectiveNotes(code),
        semester: targetTerm,
        status: 'in-progress',
        prerequisites: getCoursePrereqItems(code),
        prereqText: meta?.prereq_text ?? null,
        reason: plan?.course_reasons?.[code]
      });
      addedCodes.add(code);
    }

    const plannedCoursesByTerm = new Map<string, PlanCourse[]>();
    const plannedCourseTermMap = new Map<string, string>();

    for (const sem of plan?.semester_plan ?? []) {
      plannedCoursesByTerm.set(sem.term, sem.courses);
      for (const course of sem.courses) {
        plannedCourseTermMap.set(course.code, sem.term);
      }
    }

    const termOrder = (term: string) => {
      const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
      if (!m) return 999999;
      const seasonOrder: Record<string, number> = { Spring: 0, Fall: 1 };
      return Number(m[2]) * 2 + (seasonOrder[m[1]] ?? 0);
    };

    const maxTerms = maxPlanTerms;
    let allPlanTerms = Array.from(plannedCoursesByTerm.keys()).sort((a, b) => termOrder(a) - termOrder(b));
    const pruneFreeElectivesToFitTerms = () => {
      let terms = [...allPlanTerms];
      while (terms.length > maxTerms) {
        const lastTerm = terms[terms.length - 1];
        const courses = plannedCoursesByTerm.get(lastTerm) ?? [];
        const remaining = courses.filter((c) => c.type !== "FREE");

        // No free electives to trim in the last term; stop pruning.
        if (remaining.length === courses.length) {
          break;
        }

        plannedCoursesByTerm.set(lastTerm, remaining);
        if (remaining.length === 0) {
          plannedCoursesByTerm.delete(lastTerm);
          terms.pop();
        } else {
          // Still has required courses, so term stays; move to earlier term next pass.
          terms[terms.length - 1] = lastTerm;
          break;
        }
      }

      while (terms.length > maxTerms) {
        const lastTerm = terms[terms.length - 1];
        const courses = plannedCoursesByTerm.get(lastTerm) ?? [];
        const remaining = courses.filter((c) => c.type !== "FREE");
        plannedCoursesByTerm.set(lastTerm, remaining);
        if (remaining.length === 0) {
          plannedCoursesByTerm.delete(lastTerm);
          terms.pop();
        } else {
          break;
        }
      }

      // If we still exceed max terms, keep trimming free electives from the tail.
      for (let i = terms.length - 1; i >= maxTerms; i -= 1) {
        const term = terms[i];
        const courses = plannedCoursesByTerm.get(term) ?? [];
        const remaining = courses.filter((c) => c.type !== "FREE");
        plannedCoursesByTerm.set(term, remaining);
        if (remaining.length === 0) {
          plannedCoursesByTerm.delete(term);
        }
      }

      terms = terms.filter((term) => plannedCoursesByTerm.has(term));
      allPlanTerms = terms.slice(0, maxTerms);
    };

    pruneFreeElectivesToFitTerms();

    for (const term of allPlanTerms) {
      let courses = plannedCoursesByTerm.get(term) ?? [];
      const maxCredits = selection.maxCreditsPerSemester;
      const inProgressCodes = new Set(courses.filter((c) => inProgressSet.has(c.code)).map((c) => c.code));
      const extraInProgressCredits = Array.from(inProgressSet).reduce((sum, code) => {
        if (courses.some((c) => c.code === code)) return sum;
        const overrideTerm = inProgressOverrides[code];
        const plannedTerm = plannedCourseTermMap.get(code);
        const targetTerm = overrideTerm ?? plannedTerm ?? currentTermLabel;
        if (targetTerm !== term) return sum;
        return sum + (catalog.course_meta?.[code]?.credits ?? 3);
      }, 0);

      const totalCredits =
        courses.reduce((sum, c) => sum + (c.credits ?? catalog.course_meta?.[c.code]?.credits ?? 3), 0) +
        extraInProgressCredits;

      // NOTE: Do not trim courses for display. The UI must reflect the backend plan
      // (even if it exceeds max credits), so warnings match what the user sees.
      for (const course of courses) {
        const code = course.code;
        if (!code || typeof code !== "string" || !code.trim()) {
          continue;
        }
        const instanceId = course.instance_id ?? `${term}:${code}`;
        if (addedCodes.has(code) || removedCodeSet.has(code) || removedInstanceSet.has(instanceId) || addedInstances.has(instanceId)) {
          continue;
        }
        const meta = catalog.course_meta?.[code];
        const isCompleted = effectiveCompleted.includes(code);
        const isInProgress = inProgressSet.has(code);
        const courseCredits = course.credits ?? meta?.credits ?? 3;
        const hasGenEdSatisfies = (course.satisfies ?? []).some(
          (s) => typeof s === "string" && s.startsWith("GenEd:")
        );
        const hasGenEdReason = (course.reason ?? "").includes("GenEd:");
        const inferredGenEd = hasGenEdSatisfies || hasGenEdReason;
        let typeLabel =
          course.type === "GENED"
            ? "GEN ED"
            : course.type === "FREE" || course.type === "FREE_ELECTIVE"
              ? "FREE ELECTIVE"
              : course.type === "FOUNDATION"
                ? "FOUNDATION"
                : "PROGRAM";
        if (inferredGenEd && (course.type === "FREE" || course.type === "FREE_ELECTIVE")) {
          typeLabel = "GEN ED";
        }
        const tags = [...(course.tags ?? ['Planned'])];
        if (!tags.includes(typeLabel)) tags.push(typeLabel);
        if (inferredGenEd && !tags.includes('GEN ED')) tags.push('GEN ED');
        if (meta?.wic && !tags.includes('Writing Intensive Course')) {
          tags.push('Writing Intensive Course');
        }
        if (isCompleted && !tags.includes('Completed')) tags.push('Completed');
        if (isInProgress && !tags.includes('In Progress')) tags.push('In Progress');

        const displayCourseType =
          inferredGenEd && (course.type === "FREE" || course.type === "FREE_ELECTIVE")
            ? "GENED"
            : course.type;
        const plannedExcelNotes = Array.isArray(course.excel_elective_tags)
          ? course.excel_elective_tags.filter(
              (tag): tag is string => typeof tag === "string" && tag.trim().length > 0
            )
          : [];
        out.push({
          instanceId,
          code,
          name: course.name ?? catalog.courses[code] ?? code,
          credits: courseCredits,
          tags,
          electiveNotes: plannedExcelNotes.length > 0 ? plannedExcelNotes : getExcelElectiveNotes(code),
          semester: isInProgress ? (inProgressOverrides[code] ?? currentTermLabel) : term,
          status: isCompleted ? 'completed' : isInProgress ? 'in-progress' : 'remaining',
          prerequisites: getCoursePrereqItems(code),
          prereqText: meta?.prereq_text ?? null,
          reason: course.satisfies?.join("; ") ?? plan?.course_reasons?.[code],
          satisfies: course.satisfies,
          courseType: displayCourseType,
          sourceReason: course.source_reason,
          prereqWarning: prereqWarnings[code]
        });
        addedInstances.add(instanceId);
        addedCodes.add(code);
      }
    }
    return out;
  }, [
    catalog.courses,
    catalog.course_meta,
    plan?.semester_plan,
    effectiveCompleted,
    effectiveInProgress,
    inProgressOverrides,
    removedCourses,
    removedCodeSet,
    completedOverrides,
    plan?.course_reasons,
    plan?.excel_elective_tags,
    prereqWarnings,
    startTermSeason,
    startTermYear,
    currentTermLabel,
    selection.maxCreditsPerSemester,
    inProgressCredits
  ]);

  const pendingSwapSourceCourse = useMemo(
    () =>
      pendingSwapSourceInstanceId
        ? courseObjects.find(
            (course) => course.instanceId === pendingSwapSourceInstanceId
          ) ?? null
        : null,
    [courseObjects, pendingSwapSourceInstanceId]
  );

  useEffect(() => {
    if (!pendingSwapSourceInstanceId) return;
    if (!pendingSwapSourceCourse || pendingSwapSourceCourse.status !== "remaining") {
      setPendingSwapSourceInstanceId(null);
    }
  }, [pendingSwapSourceInstanceId, pendingSwapSourceCourse]);

  const existingCourseCodes = useMemo(
    () => new Set(courseObjects.map((course) => course.code)),
    [courseObjects]
  );

  const majorPrefixMap: Record<string, string> = {
    "Business Administration": "BUS",
    "Computer Science": "CS",
    "Economics": "ECO",
    "European Studies": "EUR",
    "History and Civilizations": "HTY",
    "Information Systems": "ISM",
    "Journalism and Mass Communication": "JMC",
    "Literature": "ENG",
    "Mathematics": "MAT",
    "Modern Languages and Cultures": "MLC",
    "Physics": "PHY",
    "Political Science and International Relations": "POS",
    "Psychology": "PSY",
    "Film and Creative Media": "FIL",
  };

  const preferredPrefixes = new Set(
    [...selection.majors, ...selection.minors]
      .map((m) => majorPrefixMap[m])
      .filter(Boolean)
  );

  const termKey = (term: string) => {
    const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
    if (!m) return { year: 9999, season: 9 };
    const seasonOrder: Record<string, number> = { Spring: 0, Fall: 1 };
    return { year: Number(m[2]), season: seasonOrder[m[1]] ?? 9 };
  };

  const compareTerms = (a: string, b: string) => {
    const ka = termKey(a);
    const kb = termKey(b);
    if (ka.year !== kb.year) return ka.year - kb.year;
    if (ka.season !== kb.season) return ka.season - kb.season;
    return a.localeCompare(b);
  };

  function nextTermName(term: string) {
    const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
    if (!m) return term;
    const season = m[1];
    const year = Number(m[2]);
    if (season === "Fall") return `Spring ${year + 1}`;
    return `Fall ${year}`;
  }

  const minTermIndexForCourse = (code: string) => {
    const meta = catalog.course_meta?.[code];
    const text = (meta?.prereq_text ?? "").toLowerCase();
    let minTerm = 0;
    if (text.includes("declared major")) minTerm = Math.max(minTerm, 1 * SEMESTERS_PER_YEAR);
    if (text.includes("junior standing")) minTerm = Math.max(minTerm, 2 * SEMESTERS_PER_YEAR + 1);
    if (text.includes("sophomore standing")) minTerm = Math.max(minTerm, 1 * SEMESTERS_PER_YEAR);
    const m = code.match(/^[A-Z]{3}\s?(\d{3,4})$/);
    if (m) {
      const level = Number(m[1]);
      if (level >= 4000) minTerm = Math.max(minTerm, 2 * SEMESTERS_PER_YEAR);
      else if (level >= 3000) minTerm = Math.max(minTerm, 1 * SEMESTERS_PER_YEAR);
    }
    return minTerm;
  };

  const getGenEdCategoryCourses = (category: string) => {
    const matches = new Set<string>();
    const normalizedCategory = normGenEd(category);
    for (const [catalogCategory, codes] of Object.entries(catalog.gen_ed?.categories ?? {})) {
      if (!isSameGenEdCategory(catalogCategory, normalizedCategory)) continue;
      (codes ?? []).forEach((code) => {
        if (typeof code === "string" && code.trim()) {
          matches.add(code);
        }
      });
    }
    for (const [code, meta] of Object.entries(catalog.course_meta ?? {})) {
      const metaTags: string[] = [];
      if (Array.isArray(meta?.gen_ed_tags)) {
        meta.gen_ed_tags.forEach((tag) => {
          if (typeof tag === "string" && tag.trim()) metaTags.push(canonicalGenEdLabel(tag));
        });
      }
      if (metaTags.length === 0 && typeof meta?.gen_ed === "string" && meta.gen_ed.trim()) {
        metaTags.push(...splitGenEdTags(meta.gen_ed));
      }
      if (metaTags.some((tag) => isSameGenEdCategory(tag, normalizedCategory))) {
        matches.add(code);
      }
    }
    if (plan?.semester_plan) {
      for (const term of plan.semester_plan) {
        for (const course of term.courses ?? []) {
          const courseTags = extractGenEdFromSatisfies(course.satisfies);
          if (courseTags.some((tag) => isSameGenEdCategory(tag, normalizedCategory))) {
            matches.add(course.code);
          }
        }
      }
    }
    const isCaseStudiesTextualAnalysis =
      normalizedCategory === normGenEd("Case Studies in Textual Analysis");
    if (isCaseStudiesTextualAnalysis) {
      const discovered = plan?.gened_discovery?.case_studies_textual_analysis ?? [];
      discovered.forEach((course) => {
        if (course?.code && typeof course.code === "string") {
          matches.add(course.code);
        }
      });
    }
    return Array.from(matches);
  };

  const buildReplacementOptions = (category: string, targetCode: string) => {
    const effectiveCategory = canonicalGenEdLabel(category);
    const taken = new Set([
      ...planningCompleted,
      ...Array.from(removedCodeSet),
      ...courseObjects.map(c => c.code)
    ]);
    const categoryCourses = new Set(getGenEdCategoryCourses(effectiveCategory));
    categoryCourses.add(targetCode);
    const candidates = Array.from(categoryCourses).filter(
      (c) => c === targetCode || !taken.has(c)
    );
    return candidates.sort((a, b) => {
      if (a === targetCode) return -1;
      if (b === targetCode) return 1;
      const aPref = preferredPrefixes.has(a.split(" ")[0]) ? 1 : 0;
      const bPref = preferredPrefixes.has(b.split(" ")[0]) ? 1 : 0;
      if (aPref !== bPref) return bPref - aPref;
      const aPrereq = getCoursePrereqs(a).length;
      const bPrereq = getCoursePrereqs(b).length;
      if (aPrereq !== bPrereq) return aPrereq - bPrereq;
      return a.localeCompare(b);
    });
  };

  const openReplacementDialog = (instanceId: string, code: string, semester: string) => {
    const categories = getCourseGenEdTags(code);
    if (categories.length === 0) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `No GenEd category found for ${code}, so I can’t suggest a category-matched replacement.`,
          timestamp: new Date()
        }
      ]);
      return;
    }
    const eligibleCategories = categories.filter((entry) => categoryHasNeed(entry, genEdNeedByCategory));
    const selectableCategories = eligibleCategories.length > 0 ? eligibleCategories : categories;
    const category =
      pickCategoryByNeed(selectableCategories, genEdNeedByCategory, true)
      ?? pickCategoryByNeed(selectableCategories, genEdNeedByCategory, false)
      ?? selectableCategories[0];
    const sorted = buildReplacementOptions(category, code);
    setReplacementTarget(instanceId);
    setReplacementTargetCode(code);
    setReplacementTargetTerm(semester);
    setReplacementCategories(selectableCategories);
    setReplacementCategory(category);
    setReplacementOptions(sorted);
    setPendingReplacement(null);
  };

  const resetReplacementState = () => {
    setReplacementTarget(null);
    setReplacementTargetCode(null);
    setReplacementTargetTerm(null);
    setReplacementCategories([]);
    setReplacementCategory(null);
    setReplacementOptions([]);
    setPendingReplacement(null);
    setPendingReplacementImpact(null);
  };

  const confirmReplacement = (skipImpactCheck: boolean = false) => {
    if (!pendingReplacement) return;
    const { targetInstanceId, targetCode, nextCode, semester } = pendingReplacement;
    if (!semester) return;

    if (!skipImpactCheck) {
      const downstream = getDownstreamDependents(
        targetCode,
        replacementTargetTerm ?? semester,
        targetInstanceId
      );
      if (downstream.length > 0) {
        setPendingReplacementImpact({
          targetCode,
          nextCode,
          semester,
          dependents: downstream
        });
        return;
      }
    }

    if (targetCode === nextCode) {
      const targetTerm = replacementTargetTerm ?? semester;
      const downstream = getDownstreamDependents(targetCode, targetTerm, targetInstanceId);
      setOverrides((prev) => {
        const filteredRemove = (prev.remove ?? []).filter((entry) => {
          if (entry.instance_id && entry.instance_id === targetInstanceId) return false;
          if (
            (entry.term ?? null) === targetTerm
            && !entry.instance_id
            && normalizeCourseCode(entry.code ?? "") === normalizeCourseCode(targetCode)
          ) {
            return false;
          }
          for (const dep of downstream) {
            if (dep.instanceId && entry.instance_id === dep.instanceId) return false;
            if (
              (entry.term ?? null) === (dep.term ?? null)
              && !entry.instance_id
              && normalizeCourseCode(entry.code ?? "") === normalizeCourseCode(dep.code)
            ) {
              return false;
            }
          }
          return true;
        });
        return { ...prev, remove: filteredRemove };
      });
      setRemovedCourses(prev => {
        const blocked = new Set<string>([targetInstanceId]);
        downstream.forEach((dep) => {
          if (dep.instanceId) blocked.add(dep.instanceId);
        });
        return prev.filter((id) => !blocked.has(id));
      });
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Kept ${targetCode} in ${semester}.`,
          timestamp: new Date()
        }
      ]);
      resetReplacementState();
      return;
    }

    const removeTerm = replacementTargetTerm ?? semester;
    const newInstanceId = createInstanceId();
    const genEdCategory =
      pendingReplacement.category ??
      replacementCategory ??
      getPrimaryGenEdCategory(targetCode) ??
      getPrimaryGenEdCategory(nextCode);
    addOverrideRemove(removeTerm, targetInstanceId, targetCode);
    addOverrideAdd(semester, nextCode, newInstanceId, genEdCategory);

    const dependentsToRemove = skipImpactCheck && pendingReplacementImpact ? pendingReplacementImpact.dependents : [];
    if (dependentsToRemove.length > 0) {
      dependentsToRemove.forEach((dep) => {
        addOverrideRemove(dep.term ?? null, dep.instanceId ?? null, dep.code);
      });
      setRemovedCourses(prev => {
        const next = new Set(prev);
        dependentsToRemove.forEach((dep) => {
          if (dep.instanceId) next.add(dep.instanceId);
        });
        return Array.from(next);
      });
    }

    const wasInProgress = inProgressCourses.includes(targetCode);
    const wasCompleted = completedCourses.includes(targetCode);

    if (wasInProgress) {
      setInProgressCourses(prev => Array.from(new Set([...prev.filter(c => c !== targetCode), nextCode])));
      setInProgressOverrides(prev => {
        const next = { ...prev };
        if (next[targetCode]) {
          next[nextCode] = next[targetCode];
          delete next[targetCode];
        }
        return next;
      });
    }
    if (wasCompleted) {
      setCompletedCourses(prev => Array.from(new Set([...prev.filter(c => c !== targetCode), nextCode])));
      setCompletedOverrides(prev => {
        const next = { ...prev };
        if (next[targetCode]) {
          next[nextCode] = next[targetCode];
          delete next[targetCode];
        }
        return next;
      });
    }

    setPlan(prevPlan => {
      if (!prevPlan) return prevPlan;
      const updated = {
        ...prevPlan,
        semester_plan: prevPlan.semester_plan.map((s) => ({
          ...s,
          courses: s.courses.map((c) => ({ ...c }))
        })),
        course_reasons: { ...(prevPlan.course_reasons ?? {}) }
      };
      const targetTerm = removeTerm;
      const termEntry = updated.semester_plan.find((t) => t.term === semester);
      if (!termEntry) return updated;

      if (targetTerm) {
        const removeEntry = updated.semester_plan.find((t) => t.term === targetTerm);
        if (removeEntry) {
          removeEntry.courses = removeEntry.courses.filter((c) => {
            if (targetInstanceId && c.instance_id === targetInstanceId) return false;
            if (c.code === targetCode) return false;
            return true;
          });
          removeEntry.credits = removeEntry.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        }
      }

      // remove dependents from plan immediately
      if (dependentsToRemove.length > 0) {
        updated.semester_plan.forEach((t) => {
          const removals = new Set(dependentsToRemove.map((d) => d.code));
          t.courses = t.courses.filter((c) => !removals.has(c.code));
          t.credits = t.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        });
      }

      // remove nextCode from any other term to avoid duplicates
      updated.semester_plan.forEach((t) => {
        if (t.term === semester) return;
        t.courses = t.courses.filter((c) => c.code !== nextCode);
        t.credits = t.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
      });

      termEntry.courses = termEntry.courses.filter((c) => c.code !== nextCode);
      termEntry.courses.push(buildPlannedCourse(nextCode, genEdCategory, newInstanceId));
      termEntry.credits = termEntry.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);

      if (genEdCategory) {
        updated.course_reasons[nextCode] = `GenEd: ${genEdCategory}`;
      }

      return updated;
    });

    setRemovedCourses(prev => {
      const next = prev.includes(targetInstanceId) ? prev : [...prev, targetInstanceId];
      return next;
    });

    setMessages(prev => [
      ...prev,
      {
        role: 'assistant',
        content: `Replaced ${targetCode} with ${nextCode} in ${semester}.`,
        timestamp: new Date()
      }
    ]);
    resetReplacementState();
  };

  const isFreeElectivePlaceholder = (code: string) => {
    const upper = code.toUpperCase();
    return upper.startsWith("FREE ELECTIVE") || upper.startsWith("FREE_ELECTIVE");
  };

  const nextFreeElectiveCode = () => {
    const used = new Set<string>();
    for (const term of plan?.semester_plan ?? []) {
      for (const course of term.courses ?? []) {
        if (course.code) used.add(course.code);
      }
    }
    overrides.add.forEach((entry) => used.add(entry.code));
    overrides.remove.forEach((entry) => {
      if (entry.code) used.add(entry.code);
    });
    removedCodeSet.forEach((entry) => used.add(entry));
    effectiveCompleted.forEach((entry) => used.add(entry));
    effectiveInProgress.forEach((entry) => used.add(entry));
    let maxIndex = 0;
    used.forEach((code) => {
      const match = code.toUpperCase().match(/^FREE ELECTIVE\s+(\d+)$/);
      if (match) {
        maxIndex = Math.max(maxIndex, Number(match[1]));
      }
    });
    return `FREE ELECTIVE ${maxIndex + 1}`;
  };

  const freeElectiveSlotsByTerm = useMemo(() => {
    const map: Record<string, { code: string; credits?: number; instance_id?: string }[]> = {};
    for (const course of courseObjects) {
      if (!course.code) continue;
      if (course.status === 'completed') continue;
      if (course.courseType === "FREE_ELECTIVE" || isFreeElectivePlaceholder(course.code)) {
        if (!map[course.semester]) map[course.semester] = [];
        map[course.semester].push({
          code: course.code,
          credits: course.credits,
          instance_id: course.instanceId
        });
      }
    }
    Object.keys(map).forEach((term) => {
      map[term].sort((a, b) => {
        const aMatch = a.code.toUpperCase().match(/^FREE ELECTIVE\s+(\d+)$/);
        const bMatch = b.code.toUpperCase().match(/^FREE ELECTIVE\s+(\d+)$/);
        const aNum = aMatch ? Number(aMatch[1]) : 0;
        const bNum = bMatch ? Number(bMatch[1]) : 0;
        return aNum - bNum;
      });
    });
    return map;
  }, [courseObjects, isFreeElectivePlaceholder]);

  const confirmRemoveCourse = () => {
    if (!pendingRemoval) return;
    const { instanceId, code } = pendingRemoval;
    setPendingRemoval(null);
    const targetCourse =
      courseObjects.find(c => c.instanceId === instanceId) ??
      courseObjects.find(c => c.code === code) ??
      null;
    if (!targetCourse) return;

    if (targetCourse.status === 'completed') {
      setCompletedCourses(prev => prev.filter(c => c !== code));
      setInProgressCourses(prev => prev.filter(c => c !== code));
      setInProgressOverrides(prev => {
        if (!prev[code]) return prev;
        const next = { ...prev };
        delete next[code];
        return next;
      });
      setCompletedOverrides(prev => {
        if (!prev[code]) return prev;
        const next = { ...prev };
        delete next[code];
        return next;
      });
      setRemovedCourses(prev => prev.filter(c => c !== instanceId));
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `Removed ${code} from completed courses and returned it to the plan.`,
          timestamp: new Date()
        }
      ]);
      return;
    }

    const semester = targetCourse.semester ?? null;
    if (!semester) return;
    const swappedElective = findSwappedElective(instanceId, semester, code);
    const downstreamDependents = getDownstreamDependents(code, semester, instanceId);
    const applyDownstreamDependentRemovals = () => {
      if (downstreamDependents.length === 0) return;
      setOverrides((prev) => {
        const nextRemove = [...(prev.remove ?? [])];
        downstreamDependents.forEach((dep) => {
          const depTerm = dep.term ?? null;
          const depInstanceId = dep.instanceId ?? null;
          const exists = nextRemove.some(
            (entry) =>
              (entry.term ?? null) === depTerm
              && (
                depInstanceId
                  ? entry.instance_id === depInstanceId
                  : (!entry.instance_id && normalizeCourseCode(entry.code ?? "") === normalizeCourseCode(dep.code))
              )
          );
          if (!exists) {
            nextRemove.push({
              term: depTerm,
              code: dep.code,
              instance_id: depInstanceId ?? undefined,
            });
          }
        });
        return { ...prev, remove: nextRemove };
      });
      setRemovedCourses((prev) => {
        const next = new Set(prev);
        downstreamDependents.forEach((dep) => {
          if (dep.instanceId) next.add(dep.instanceId);
        });
        return Array.from(next);
      });
      downstreamDependents.forEach((dep) => {
        const swapped = findSwappedElective(dep.instanceId ?? "", dep.term ?? null, dep.code);
        if (swapped) removeSwappedElective(swapped);
      });
      const labels = Array.from(new Set(downstreamDependents.map((dep) => dep.code)));
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Also removed dependent courses: ${labels.join(', ')}.`,
          timestamp: new Date()
        }
      ]);
    };
    addOverrideRemove(semester, instanceId, code);
    setRemovedCourses(prev => (prev.includes(instanceId) ? prev : [...prev, instanceId]));

    const removedCredits = targetCourse.credits ?? getCourseCredits(code);
    const afterCredits = (termCreditsMap[semester] ?? 0) - removedCredits;
    const isGenEdCourse =
      targetCourse.courseType === 'GENED' ||
      (targetCourse.tags ?? []).includes('GEN ED') ||
      (targetCourse.reason ?? '').includes('GenEd:') ||
      getCourseGenEdTags(code).length > 0;

    const attemptPullFromNextTerm = () => {
      if (!plan?.semester_plan) return null;
      if (afterCredits >= minCreditsPerTerm) return null;

      const orderedTerms = [...plan.semester_plan].sort(
        (a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term)
      );
      const currentIdx = orderedTerms.findIndex((t) => t.term === semester);
      if (currentIdx < 0 || currentIdx + 1 >= orderedTerms.length) return null;

      const nextTerm = orderedTerms[currentIdx + 1];
      const removedInstances = new Set<string>(removedCourses);
      removedInstances.add(instanceId);

      const userAddedInstanceIds = new Set<string>(
        (overrides.add ?? [])
          .map((entry) => entry.instance_id)
          .filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
      );
      const userAddedCodesInNext = new Set<string>(
        (overrides.add ?? [])
          .filter((entry) => entry.term === nextTerm.term)
          .map((entry) => entry.code)
          .filter((c): c is string => typeof c === 'string' && c.trim().length > 0)
      );

      const isEligibleCandidate = (course: PlanCourse) => {
        if (!course?.code) return false;
        if (removedCodeSet.has(course.code)) return false;
        if (course.instance_id && removedInstances.has(course.instance_id)) return false;
        if (effectiveCompleted.includes(course.code) || effectiveInProgress.includes(course.code)) return false;
        if (course.instance_id && userAddedInstanceIds.has(course.instance_id)) return false;
        if (userAddedCodesInNext.has(course.code)) return false;
        return true;
      };

      const isFreeLike = (course: PlanCourse) =>
        course.type === 'FREE' ||
        course.type === 'FREE_ELECTIVE' ||
        isFreeElectivePlaceholder(course.code);

      const candidates = (nextTerm.courses ?? []).filter(isEligibleCandidate).sort((a, b) => {
        return Number(isFreeLike(b)) - Number(isFreeLike(a));
      });

      for (const candidate of candidates) {
        const candidateCredits = candidate.credits ?? getCourseCredits(candidate.code);
        if (afterCredits + candidateCredits > selection.maxCreditsPerSemester) continue;
        const prereqs = getCoursePrereqs(candidate.code);
        if (prereqs.includes(code)) continue;
        if (!isFreeLike(candidate)) {
          const prereqStatus = isPrereqSatisfied(
            candidate.code,
            termIndexFromLabel(semester),
            new Set(effectiveCompleted),
            new Set(effectiveInProgress),
            plan,
            Array.from(removedInstances)
          );
          if (!prereqStatus.satisfied) continue;
        }

        addOverrideMove(nextTerm.term, semester, candidate.code, candidate.instance_id);
        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: `Moved ${candidate.code} from ${nextTerm.term} to ${semester} to keep at least ${minCreditsPerTerm} credits.`,
            timestamp: new Date()
          }
        ]);
        return candidate.code;
      }
      return null;
    };

    const isElectiveType = targetCourse.courseType === 'FREE' || targetCourse.courseType === 'FREE_ELECTIVE';
    const isPlaceholder = isFreeElectivePlaceholder(code);
    if (isElectiveType) {
      if (!isPlaceholder) {
        if (swappedElective) {
          setOverrides((prev) => {
            const filteredAdd = (prev.add ?? []).filter((entry) => {
              if (
                entry.instance_id
                && entry.instance_id === swappedElective.addedCourseInstanceId
              ) {
                return false;
              }
              if (
                entry.term === swappedElective.termLabel
                && normalizeCourseCode(entry.code) === normalizeCourseCode(swappedElective.addedCourseCode)
              ) {
                return false;
              }
              return true;
            });
            const filteredRemove = (prev.remove ?? []).filter((entry) => {
              if (entry.instance_id && entry.instance_id === instanceId) {
                return false;
              }
              if (
                entry.instance_id
                && entry.instance_id === swappedElective.replacedPlaceholderInstanceId
              ) {
                return false;
              }
              if (
                (entry.term ?? null) === swappedElective.termLabel
                && !entry.instance_id
                && entry.code === swappedElective.placeholderCode
              ) {
                return false;
              }
              return true;
            });
            const nextRemove = [
              ...filteredRemove,
              {
                term: semester,
                instance_id: instanceId,
              },
            ];
            const hasPlaceholderAdd = filteredAdd.some(
              (entry) =>
                entry.instance_id === swappedElective.replacedPlaceholderInstanceId
                || (
                  entry.term === swappedElective.termLabel
                  && entry.code === swappedElective.placeholderCode
                )
            );
            const nextAdd = hasPlaceholderAdd
              ? filteredAdd
              : [
                  ...filteredAdd,
                  {
                    term: swappedElective.termLabel,
                    code: swappedElective.placeholderCode,
                    instance_id: swappedElective.replacedPlaceholderInstanceId,
                  },
                ];
            return { ...prev, add: nextAdd, remove: nextRemove };
          });
          removeSwappedElective(swappedElective);
          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              content: `Restored ${swappedElective.placeholderCode} in ${swappedElective.termLabel} after removing ${code}.`,
              timestamp: new Date()
            }
          ]);
        } else {
          const placeholder = nextFreeElectiveCode();
          addOverrideAdd(semester, placeholder, createInstanceId());
          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              content: `Replaced ${code} with ${placeholder} in ${semester}.`,
              timestamp: new Date()
            }
          ]);
        }
      } else {
        setMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: `Removed ${code} from ${semester}.`,
            timestamp: new Date()
          }
        ]);
      }
      applyDownstreamDependentRemovals();
      return;
    }

    if (!isGenEdCourse) {
      attemptPullFromNextTerm();
    }
    applyDownstreamDependentRemovals();
    openReplacementDialog(instanceId, code, semester);
  };

  const requestRemoveCourse = (instanceId: string) => {
    const targetCourse = courseObjects.find(c => c.instanceId === instanceId) ?? null;
    if (!targetCourse) return;
    setPendingRemoval({
      instanceId,
      code: targetCourse.code,
      term: targetCourse.semester ?? null,
      status: targetCourse.status
    });
  };

  const handleMoveCourse = (instanceId: string) => {
    const picked = courseObjects.find((course) => course.instanceId === instanceId) ?? null;
    if (!picked || picked.status !== 'remaining') return;

    if (!pendingSwapSourceInstanceId) {
      setMoveCourseWarning(null);
      setPendingSwapSourceInstanceId(instanceId);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Selected ${picked.code} (${picked.semester}). Click "Move course" on another planned course to swap positions.`,
          timestamp: new Date()
        }
      ]);
      return;
    }

    if (pendingSwapSourceInstanceId === instanceId) {
      setMoveCourseWarning(null);
      setPendingSwapSourceInstanceId(null);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Move course canceled for ${picked.code}.`,
          timestamp: new Date()
        }
      ]);
      return;
    }

    const source = courseObjects.find((course) => course.instanceId === pendingSwapSourceInstanceId) ?? null;
    if (!source || source.status !== 'remaining') {
      setMoveCourseWarning(null);
      setPendingSwapSourceInstanceId(instanceId);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Selected ${picked.code} (${picked.semester}). Click "Move course" on another planned course to swap positions.`,
          timestamp: new Date()
        }
      ]);
      return;
    }

    if (source.semester === picked.semester) {
      const warning = `${source.code} and ${picked.code} are already in ${source.semester}. Pick a course from a different term.`;
      setMoveCourseWarning(warning);
      setPendingSwapSourceInstanceId(instanceId);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: warning,
          timestamp: new Date()
        }
      ]);
      return;
    }

    const swapTargetByInstance = new Map<string, string>([
      [source.instanceId, picked.semester],
      [picked.instanceId, source.semester],
    ]);

    const getStandingRequirementText = (code: string): string | null => {
      const meta = catalog.course_meta?.[code];
      const text = (meta?.prereq_text ?? '').toLowerCase();
      const reasons: string[] = [];
      if (text.includes('junior standing')) reasons.push('junior standing');
      if (text.includes('sophomore standing')) reasons.push('sophomore standing');
      if (text.includes('declared major')) reasons.push('declared major');
      return reasons.length > 0 ? reasons.join(' and ') : null;
    };

    const validateCoursePlacement = (course: Course, targetTerm: string): string | null => {
      const targetIdx = termIndexFromLabel(targetTerm);
      if (targetIdx === 999999) {
        return `Cannot move ${course.code} to ${targetTerm}. The target term is invalid.`;
      }

      const minTermOffset = minTermIndexForCourse(course.code);
      if (minTermOffset > 0) {
        const baseIdx = termIndex(effectiveStartForPlanning.season, effectiveStartForPlanning.year);
        const minAllowedIdx = baseIdx + minTermOffset;
        if (targetIdx < minAllowedIdx) {
          const earliest = termFromIndex(minAllowedIdx);
          const earliestLabel = `${earliest.season} ${earliest.year}`;
          const standingReason = getStandingRequirementText(course.code);
          if (standingReason) {
            return `Cannot move ${course.code} to ${targetTerm}. This course requires ${standingReason}; earliest allowed term is ${earliestLabel}.`;
          }
          return `Cannot move ${course.code} to ${targetTerm}. This course cannot be scheduled that early; earliest allowed term is ${earliestLabel}.`;
        }
      }

      const satisfiedBeforeTarget = new Set<string>();
      const preferredCodes = new Set<string>();
      const satisfiedGenEdBeforeTarget = new Set<string>();
      const addSatisfiedGenEdCategories = (code: string) => {
        getCanonicalCourseGenEdTags(code).forEach((category) => {
          const key = normGenEd(category);
          if (key) satisfiedGenEdBeforeTarget.add(key);
        });
      };

      for (const code of [...effectiveCompleted, ...effectiveInProgress]) {
        const normalized = normalizeCourseCode(code);
        if (!normalized || isFreeElectivePlaceholder(normalized)) continue;
        satisfiedBeforeTarget.add(normalized);
        preferredCodes.add(normalized);
        addSatisfiedGenEdCategories(normalized);
      }

      for (const sem of plan?.semester_plan ?? []) {
        for (const c of sem.courses ?? []) {
          if (!c?.code) continue;
          if (isRemovedPlanCourse(c)) continue;
          if (isFreeElectivePlaceholder(c.code)) continue;
          const instance = c.instance_id ?? `${sem.term}:${c.code}`;
          const effectiveTerm = swapTargetByInstance.get(instance) ?? sem.term;
          const normalizedCode = normalizeCourseCode(c.code);
          if (!normalizedCode) continue;
          preferredCodes.add(normalizedCode);
          if (termIndexFromLabel(effectiveTerm) < targetIdx) {
            satisfiedBeforeTarget.add(normalizedCode);
            addSatisfiedGenEdCategories(normalizedCode);
          }
        }
      }

      const targetCategories = getCanonicalCourseGenEdTags(course.code);
      for (const category of targetCategories) {
        const rule = GEN_ED_CATEGORY_PREREQS[category];
        if (!rule) continue;
        const missingCategories = (rule.categories ?? []).filter(
          (requiredCategory) => !satisfiedGenEdBeforeTarget.has(normGenEd(requiredCategory))
        );
        if (missingCategories.length > 0) {
          return `Cannot move ${course.code} to ${targetTerm}. ${category} requires ${missingCategories.join(" and ")} to be completed before that term.`;
        }
        const missingCourses = (rule.courses ?? [])
          .map((requiredCode) => normalizeCourseCode(requiredCode))
          .filter((requiredCode) => !codeSetHas(satisfiedBeforeTarget, requiredCode));
        if (missingCourses.length > 0) {
          return `Cannot move ${course.code} to ${targetTerm}. ${category} requires ${missingCourses.join(" and ")} to be completed before that term.`;
        }
      }

      const prereqStatus = evaluatePrereqStatus(course.code, satisfiedBeforeTarget, preferredCodes);
      if (!prereqStatus.satisfied) {
        return `Cannot move ${course.code} to ${targetTerm}. Prerequisites not met by that term: ${prereqStatus.unmet.join(', ')}.`;
      }

      return null;
    };

    const sourcePlacementIssue = validateCoursePlacement(source, picked.semester);
    if (sourcePlacementIssue) {
      setMoveCourseWarning(sourcePlacementIssue);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: sourcePlacementIssue,
          timestamp: new Date()
        }
      ]);
      return;
    }

    const pickedPlacementIssue = validateCoursePlacement(picked, source.semester);
    if (pickedPlacementIssue) {
      setMoveCourseWarning(pickedPlacementIssue);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: pickedPlacementIssue,
          timestamp: new Date()
        }
      ]);
      return;
    }

    addOverrideMove(source.semester, picked.semester, source.code, source.instanceId);
    addOverrideMove(picked.semester, source.semester, picked.code, picked.instanceId);
    setMoveCourseWarning(null);
    setPendingSwapSourceInstanceId(null);
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: `Swapped ${source.code} (${source.semester}) with ${picked.code} (${picked.semester}).`,
        timestamp: new Date()
      }
    ]);
  };

  const pendingReplacementStatus = pendingReplacement
    ? (pendingReplacement.nextCode === pendingReplacement.targetCode
        ? { prereqs: [], unmet: [], satisfied: true }
        : getPrereqStatusForTerm(pendingReplacement.nextCode, pendingReplacement.semester))
    : null;
  const pendingReplacementDownstreamPreview = useMemo(() => {
    if (!pendingReplacement) return [] as { code: string; instanceId?: string; term?: string }[];
    if (pendingReplacement.nextCode === pendingReplacement.targetCode) {
      return [] as { code: string; instanceId?: string; term?: string }[];
    }
    const targetTerm = replacementTargetTerm ?? pendingReplacement.semester;
    return getDownstreamDependents(
      pendingReplacement.targetCode,
      targetTerm,
      pendingReplacement.targetInstanceId
    );
  }, [
    pendingReplacement,
    replacementTargetTerm,
    plan,
    effectiveCompleted,
    effectiveInProgress,
    removedCourses,
    removedCodeSet
  ]);

  const handleAddCourse = (code: string) => {
    if (!plan) return;

    if (effectiveCompleted.includes(code)) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `${code} is already marked as completed.`, timestamp: new Date() }
      ]);
      return;
    }
    if (effectiveInProgress.includes(code)) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `${code} is already marked as in progress.`, timestamp: new Date() }
      ]);
      return;
    }

    setActiveTab('plan');
    setPendingAddCourse({ code });
    setPendingAddTerm(null);
  };

  const runAddCourseWithPrereqs = (
    code: string,
    preferredTerm?: string | null,
    options?: { genEdCategory?: string | null; suppressMessages?: boolean }
  ) => {
    if (!plan) return false;

    const notify = (content: string) => {
      if (options?.suppressMessages) return;
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content, timestamp: new Date() }
      ]);
    };

    const primaryGenEdCategory = getPrimaryGenEdCategory(code, options?.genEdCategory);

    const deepCopyPlan = (input: GeneratePlanResponse) => ({
      ...input,
      semester_plan: input.semester_plan.map((s) => ({
        ...s,
        courses: s.courses.map((c) => ({ ...c }))
      })),
      course_reasons: { ...(input.course_reasons ?? {}) }
    });

    const planHasCourse = (workingPlan: GeneratePlanResponse, courseCode: string) =>
      workingPlan.semester_plan.some((s) => s.courses.some((c) => c.code === courseCode));

    const addCourseToPlan = (
      workingPlan: GeneratePlanResponse,
      courseCode: string,
      preferredTargetTerm?: string | null
    ) => {
      const alreadyInPlan = planHasCourse(workingPlan, courseCode);
      if (alreadyInPlan) {
        return {
          plan: workingPlan,
          term: null,
          appendedTerm: false,
          restored: removedCodeSet.has(courseCode)
        };
      }

      const courseCredits = getCourseCredits(courseCode);
      const prereqSatisfiedInSet = (satisfiedSet: Set<string>) =>
        evaluatePrereqStatus(courseCode, satisfiedSet).satisfied;
      const minIdx = minTermIndexForCourse(courseCode);
      const maxTerms = maxPlanTerms;
      const minCreditsThreshold = minCreditsPerTerm;

      const activeTerms = workingPlan.semester_plan
        .map((s) => ({
          term: s.term,
          courses: s.courses.filter((c) => !isRemovedPlanCourse(c))
        }))
        .sort((a, b) => compareTerms(a.term, b.term));

      if (preferredTargetTerm) {
        const termOrder = (term: string) => {
          const m = term.match(/^(Spring|Fall)\s+(\d{4})$/);
          if (!m) return 999999;
          const seasonOrder: Record<string, number> = { Spring: 0, Fall: 1 };
          return Number(m[2]) * 2 + (seasonOrder[m[1]] ?? 0);
        };
        const baseIdx = termOrder(effectiveStartForPlanning.season + " " + effectiveStartForPlanning.year);
        const targetIdx = termOrder(preferredTargetTerm);
        if (targetIdx < baseIdx || targetIdx - baseIdx < minIdx) {
          return {
            plan: workingPlan,
            term: null,
            appendedTerm: false,
            restored: false,
            blockedReason: `${preferredTargetTerm} is too early for this course`
          };
        }

        const newTerms: { term: string; courses: PlanCourse[]; credits: number }[] = [];
        let lastTerm = activeTerms[activeTerms.length - 1]?.term ?? preferredTargetTerm;
        let termCount = activeTerms.length;
        while (termCount < maxTerms && compareTerms(lastTerm, preferredTargetTerm) < 0) {
          lastTerm = nextTermName(lastTerm);
          newTerms.push({ term: lastTerm, courses: [], credits: 0 });
          termCount += 1;
        }
        const withNewTerms = newTerms.length
          ? [...workingPlan.semester_plan, ...newTerms]
          : workingPlan.semester_plan.slice();
        const termEntry = withNewTerms.find((s) => s.term === preferredTargetTerm);
        if (!termEntry) {
          return {
            plan: workingPlan,
            term: null,
            appendedTerm: false,
            restored: false,
            blockedReason: `Cannot place ${courseCode} in ${preferredTargetTerm}`
          };
        }
        const termCredits = termEntry.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        if (termCredits + courseCredits > selection.maxCreditsPerSemester) {
          return {
            plan: workingPlan,
            term: null,
            appendedTerm: false,
            restored: false,
            blockedReason: `${preferredTargetTerm} would exceed your max credits`
          };
        }
        termEntry.courses = [
          ...termEntry.courses,
          buildPlannedCourse(courseCode, courseCode === code ? primaryGenEdCategory : null)
        ];
        termEntry.credits = termEntry.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        return {
          plan: {
            ...workingPlan,
            semester_plan: withNewTerms
          },
          term: preferredTargetTerm,
          appendedTerm: newTerms.length > 0,
          restored: false
        };
      }

      const computeFreeElectiveRemoval = (courses: PlanCourse[], allowBelowMin: boolean) => {
        const freeCourses = courses.filter((c) => c.type === "FREE" || c.type === "FREE_ELECTIVE");
        if (freeCourses.length === 0) return null;

        let credits = courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        const removed: string[] = [];
        for (let i = freeCourses.length - 1; i >= 0; i -= 1) {
          if (credits + courseCredits <= selection.maxCreditsPerSemester) {
            break;
          }
          const free = freeCourses[i];
          const nextCredits = credits - (free.credits ?? 3);
          if (!allowBelowMin && nextCredits < minCreditsThreshold) {
            continue;
          }
          const freeId = free.instance_id ?? free.code;
          removed.push(freeId);
          credits = nextCredits;
        }

        if (credits + courseCredits <= selection.maxCreditsPerSemester) {
          return removed;
        }
        return null;
      };

      const findTargetTerm = (allowBelowMin: boolean) => {
        let completedSoFar = new Set(planningCompleted);
        for (let i = 0; i < activeTerms.length; i += 1) {
          const term = activeTerms[i];
          const termCredits = term.courses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
          const prereqMet = prereqSatisfiedInSet(completedSoFar);
          if (i >= minIdx && prereqMet) {
            if (termCredits + courseCredits <= selection.maxCreditsPerSemester) {
              return { term: term.term, removedFree: [] as string[] };
            }
            const removedFree = computeFreeElectiveRemoval(term.courses, allowBelowMin);
            if (removedFree) {
              return { term: term.term, removedFree };
            }
          }
          term.courses.forEach((c) => completedSoFar.add(c.code));
        }
        return null;
      };

      const strictTarget = findTargetTerm(false);
      const relaxedTarget = strictTarget ?? findTargetTerm(true);

      let targetTerm: string | null = relaxedTarget?.term ?? null;
      let removedFreeCourses = relaxedTarget?.removedFree ?? [];

      const newTerms: { term: string; courses: PlanCourse[]; credits: number }[] = [];
      if (!targetTerm) {
        if (!activeTerms.length) {
          return { plan: workingPlan, term: null, appendedTerm: false, restored: false };
        }
        if (activeTerms.length < maxTerms) {
          const lastTerm = activeTerms[activeTerms.length - 1].term;
          let termName = lastTerm;
          let termCount = activeTerms.length;
          const desiredIndex = Math.min(Math.max(minIdx, termCount), maxTerms - 1);
          while (termCount <= desiredIndex) {
            termName = nextTermName(termName);
            newTerms.push({ term: termName, courses: [], credits: 0 });
            termCount += 1;
          }
          targetTerm = newTerms.length ? newTerms[newTerms.length - 1].term : lastTerm;
        } else {
          let completedSoFar = new Set(planningCompleted);
          let fallbackTerm = activeTerms[activeTerms.length - 1].term;
          for (let i = 0; i < activeTerms.length; i += 1) {
            const term = activeTerms[i];
            const prereqMet = prereqSatisfiedInSet(completedSoFar);
            if (i >= minIdx && prereqMet) {
              fallbackTerm = term.term;
            }
            term.courses.forEach((c) => completedSoFar.add(c.code));
          }
          targetTerm = fallbackTerm;
        }
      }

      const updated = workingPlan.semester_plan.map((s) => s);
      const withNewTerms = newTerms.length ? [...updated, ...newTerms] : updated;
      const termEntry = withNewTerms.find((s) => s.term === targetTerm);
      if (termEntry) {
        const filteredCourses = removedFreeCourses.length
          ? termEntry.courses.filter((c) => !removedFreeCourses.includes(c.instance_id ?? c.code))
          : termEntry.courses;
        const termCredits = filteredCourses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        if (termCredits + courseCredits > selection.maxCreditsPerSemester) {
          return {
            plan: workingPlan,
            term: null,
            appendedTerm: false,
            restored: false,
            blockedReason: `${targetTerm} would exceed your max credits`
          };
        }
      }
      const finalTerms = withNewTerms.map((s) => {
        if (s.term !== targetTerm) return s;
        const filteredCourses = removedFreeCourses.length
          ? s.courses.filter((c) => !removedFreeCourses.includes(c.instance_id ?? c.code))
          : s.courses;
        const nextCourses = filteredCourses.some((c) => c.code === courseCode)
          ? filteredCourses
          : [...filteredCourses, buildPlannedCourse(courseCode, courseCode === code ? primaryGenEdCategory : null)];
        const credits = nextCourses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
        return { ...s, courses: nextCourses, credits };
      });

      const reasons = workingPlan.course_reasons ?? {};
      if (!reasons[courseCode]) {
        const newReasons: string[] = [];
        const categories = courseCode === code && primaryGenEdCategory
          ? [primaryGenEdCategory]
          : getCourseGenEdTags(courseCode);
        if (categories.length > 0) {
          newReasons.push(`General Education: ${categories.join(", ")}`);
        }
        newReasons.push('Added to plan');
        reasons[courseCode] = newReasons.join('; ');
      }

      return {
        plan: {
          ...workingPlan,
          semester_plan: finalTerms,
          course_reasons: reasons
        },
        term: targetTerm,
        appendedTerm: newTerms.length > 0,
        restored: false
      };
    };

    if (preferredTerm) {
      const workingPlan = deepCopyPlan(plan);
      const baseTerm = `${effectiveStartForPlanning.season} ${effectiveStartForPlanning.year}`;
      const baseIdx = termIndexFromLabel(baseTerm);
      const targetIdx = termIndexFromLabel(preferredTerm);
      const maxTerms = maxPlanTerms;

      const sortTerms = (terms: typeof workingPlan.semester_plan) =>
        [...terms].sort((a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term));

      let orderedTerms = sortTerms(workingPlan.semester_plan);
      if (orderedTerms.length === 0) {
        orderedTerms = [{ term: baseTerm, courses: [], credits: 0 }];
      }
      if (!orderedTerms.some((t) => t.term === preferredTerm)) {
        let lastTerm = orderedTerms[orderedTerms.length - 1]?.term ?? baseTerm;
        while (orderedTerms.length < maxTerms && termIndexFromLabel(lastTerm) < targetIdx) {
          lastTerm = nextTermName(lastTerm);
          orderedTerms.push({ term: lastTerm, courses: [], credits: 0 });
        }
      }
      workingPlan.semester_plan = orderedTerms;

      const termCredits = new Map<string, number>();
      const courseTermMap = new Map<string, string>();
      const restoredPrereqs = new Set<string>();

      const courseCredits = (courseCode: string) => getCourseCredits(courseCode);

      for (const term of workingPlan.semester_plan) {
        const credits = term.courses.reduce((sum, c) => {
          if (isRemovedPlanCourse(c)) return sum;
          return sum + (c.credits ?? catalog.course_meta?.[c.code]?.credits ?? 3);
        }, 0);
        term.credits = credits;
        termCredits.set(term.term, credits);
        for (const course of term.courses) {
          if (!course.code || isRemovedPlanCourse(course)) continue;
          courseTermMap.set(course.code, term.term);
        }
      }
      const preferredProgramCodes = new Set<string>([...effectiveCompleted, ...effectiveInProgress]);
      for (const codeInPlan of courseTermMap.keys()) {
        preferredProgramCodes.add(codeInPlan);
      }

      const removeFromTerm = (courseCode: string, termName: string) => {
        const term = workingPlan.semester_plan.find((t) => t.term === termName);
        if (!term) return;
        term.courses = term.courses.filter((c) => c.code !== courseCode);
        const credits = term.courses.reduce((sum, c) => {
          if (isRemovedPlanCourse(c)) return sum;
          return sum + (c.credits ?? catalog.course_meta?.[c.code]?.credits ?? 3);
        }, 0);
        term.credits = credits;
        termCredits.set(termName, credits);
        courseTermMap.delete(courseCode);
      };

      const addToTerm = (courseCode: string, termName: string) => {
        const term = workingPlan.semester_plan.find((t) => t.term === termName);
        if (!term) return false;
        const existingIndex = term.courses.findIndex((c) => c.code === courseCode);
        if (existingIndex >= 0) {
          const existingInstanceId = term.courses[existingIndex]?.instance_id;
          const removedByInstance = existingInstanceId ? removedInstanceSet.has(existingInstanceId) : false;
          const removedByCode = removedCodeSet.has(courseCode);
          if (!removedByInstance && !removedByCode) return true;
          if (existingInstanceId) {
            term.courses = term.courses.filter((c) => c.instance_id !== existingInstanceId);
          } else {
            term.courses = term.courses.filter((c) => c.code !== courseCode);
          }
        }
        const credits = courseCredits(courseCode);
        const currentCredits = termCredits.get(termName) ?? 0;
        if (currentCredits + credits > selection.maxCreditsPerSemester) return false;
        const plannedCourse = buildPlannedCourse(
          courseCode,
          courseCode === code ? primaryGenEdCategory : null
        );
        term.courses = [
          ...term.courses,
          plannedCourse
        ];
        term.credits = currentCredits + credits;
        termCredits.set(termName, term.credits);
        courseTermMap.set(courseCode, termName);
        restoredPrereqs.add(courseCode);
        return true;
      };

      const placing = new Set<string>();
      const unplacedPrereqs = new Set<string>();

      const placePrereq = (courseCode: string): number | null => {
        if (effectiveCompleted.includes(courseCode) || effectiveInProgress.includes(courseCode)) {
          return baseIdx - 1;
        }
        const existingTerm = courseTermMap.get(courseCode);
        if (existingTerm) {
          const existingIdx = termIndexFromLabel(existingTerm);
          if (existingIdx < targetIdx) {
            return existingIdx;
          }
          removeFromTerm(courseCode, existingTerm);
        }
        if (placing.has(courseCode)) return null;
        placing.add(courseCode);

        const satisfiedForChoice = new Set<string>([
          ...effectiveCompleted,
          ...effectiveInProgress,
        ]);
        for (const [scheduledCode, scheduledTerm] of courseTermMap.entries()) {
          if (termIndexFromLabel(scheduledTerm) < targetIdx) {
            satisfiedForChoice.add(scheduledCode);
          }
        }
        const prereqs = getNeededPrereqCodes(courseCode, satisfiedForChoice, preferredProgramCodes);
        let latestIdx = baseIdx - 1;
        for (const prereq of prereqs) {
          const idx = placePrereq(prereq);
          if (idx === null) {
            unplacedPrereqs.add(prereq);
          } else if (idx > latestIdx) {
            latestIdx = idx;
          }
        }

        const minIdx = baseIdx + minTermIndexForCourse(courseCode);
        const earliestIdx = Math.max(minIdx, latestIdx + 1);
        const candidates = workingPlan.semester_plan
          .filter((t) => {
            const idx = termIndexFromLabel(t.term);
            return idx < targetIdx && idx >= earliestIdx;
          })
          .sort((a, b) => termIndexFromLabel(a.term) - termIndexFromLabel(b.term));

        let placedIdx: number | null = null;
        for (const term of candidates) {
          if (addToTerm(courseCode, term.term)) {
            placedIdx = termIndexFromLabel(term.term);
            break;
          }
        }

        if (placedIdx === null) {
          unplacedPrereqs.add(courseCode);
          if (existingTerm) {
            addToTerm(courseCode, existingTerm);
          }
          placing.delete(courseCode);
          return null;
        }
        placing.delete(courseCode);
        return placedIdx;
      };

      const satisfiedBeforeTarget = new Set<string>([
        ...effectiveCompleted,
        ...effectiveInProgress,
      ]);
      for (const [scheduledCode, scheduledTerm] of courseTermMap.entries()) {
        if (termIndexFromLabel(scheduledTerm) < targetIdx) {
          satisfiedBeforeTarget.add(scheduledCode);
        }
      }
      const prereqs = getNeededPrereqCodes(code, satisfiedBeforeTarget, preferredProgramCodes);
      for (const prereq of prereqs) {
        placePrereq(prereq);
      }

      const placement = addCourseToPlan(workingPlan, code, preferredTerm);
      if (!placement.term && !placement.restored) {
        const blockedReason = (placement as { blockedReason?: string }).blockedReason;
        notify(
          blockedReason
            ? `Cannot add ${code}. ${blockedReason}.`
            : 'No semesters found to place this course.'
        );
        return false;
      }

      setPlan(placement.plan);
      const restoredCodes = new Set<string>(restoredPrereqs);
      if (placement.restored) {
        restoredCodes.add(code);
      }
      let nextRemoved = removedCourses;
      if (restoredCodes.size > 0) {
        const restoredInstanceIds = new Set<string>();
        for (const term of placement.plan.semester_plan ?? []) {
          for (const course of term.courses ?? []) {
            if (restoredCodes.has(course.code) && course.instance_id) {
              restoredInstanceIds.add(course.instance_id);
            }
          }
        }
        nextRemoved = removedCourses.filter((id) => !restoredInstanceIds.has(id));
        setRemovedCourses(nextRemoved);
      }

      const prereqStatus = isPrereqSatisfied(
        code,
        targetIdx,
        new Set(effectiveCompleted),
        new Set(effectiveInProgress),
        placement.plan,
        nextRemoved
      );

      if (unplacedPrereqs.size > 0 || prereqStatus.unmet.length > 0) {
        const unmetList = prereqStatus.unmet.length > 0
          ? prereqStatus.unmet
          : Array.from(unplacedPrereqs);
        notify(`Added ${code} to ${preferredTerm}, but prerequisites are still unmet before that term: ${unmetList.join(", ")}.`);
      }

      if (placement.term) {
        notify(`Added ${code} to ${placement.term}.`);
      }
      return true;
    }

    const workingPlan = deepCopyPlan(plan);
    const preferredProgramCodes = new Set<string>(planningCompleted);
    for (const sem of plan?.semester_plan ?? []) {
      for (const course of sem.courses ?? []) {
        if (!course?.code || isRemovedPlanCourse(course)) continue;
        preferredProgramCodes.add(course.code);
      }
    }
    const initialNeededPrereqs = getNeededPrereqCodes(
      code,
      new Set(planningCompleted),
      preferredProgramCodes
    );

    const getCourseTerm = (planData: GeneratePlanResponse, courseCode: string) => {
      for (const term of planData.semester_plan) {
        if (term.courses.some((c) => c.code === courseCode)) {
          return term.term;
        }
      }
      return null;
    };

    let preferredTargetTerm: string | null | undefined = preferredTerm;
    if (initialNeededPrereqs.length > 0) {
      let latestPrereqTerm: string | null = null;
      for (const prereq of initialNeededPrereqs) {
        if (effectiveCompleted.includes(prereq) || effectiveInProgress.includes(prereq)) {
          continue;
        }
        const term = getCourseTerm(workingPlan, prereq);
        if (!term) continue;
        if (!latestPrereqTerm || compareTerms(term, latestPrereqTerm) > 0) {
          latestPrereqTerm = term;
        }
      }
      if (latestPrereqTerm && !preferredTerm) {
        const requiredTerm = nextTermName(latestPrereqTerm);
        if (!preferredTargetTerm || compareTerms(preferredTargetTerm, requiredTerm) < 0) {
          preferredTargetTerm = requiredTerm;
        }
      }
    }

    const targetGenEd = (primaryGenEdCategory && categoryHasNeed(primaryGenEdCategory, genEdNeedByCategory))
      ? primaryGenEdCategory
      : null;
    if (targetGenEd) {
      const minIdx = minTermIndexForCourse(code);
      const activeTerms = workingPlan.semester_plan
        .map((s) => ({
          term: s.term,
          courses: s.courses
            .filter((c) => !isRemovedPlanCourse(c))
            .map((c) => c.code)
        }))
        .sort((a, b) => compareTerms(a.term, b.term));

      let completedSoFar = new Set(planningCompleted);
      let replaced = false;
      let replacedTerm: string | null = null;
      let replacedCode: string | null = null;

      for (let i = 0; i < activeTerms.length; i += 1) {
        const term = activeTerms[i];
        const prereqMet = evaluatePrereqStatus(code, completedSoFar).satisfied;
        if (!prereqMet || i < minIdx) {
          term.courses.forEach((c) => completedSoFar.add(c));
          continue;
        }
        const replaceable = term.courses.find((c) =>
          getCourseGenEdTags(c).some((tag) => isSameGenEdCategory(tag, targetGenEd)) &&
          !effectiveCompleted.includes(c) &&
          !effectiveInProgress.includes(c)
        );
        if (replaceable) {
          replaced = true;
          replacedTerm = term.term;
          replacedCode = replaceable;
          break;
        }
        term.courses.forEach((c) => completedSoFar.add(c));
      }

      if (replaced && replacedTerm && replacedCode && !preferredTerm) {
        const updated = workingPlan.semester_plan.map((s) => {
          if (s.term !== replacedTerm) return s;
          const nextCourses = s.courses.map((c) => {
            if (c.code !== replacedCode) return c;
            return buildPlannedCourse(code, targetGenEd);
          });
          const credits = nextCourses.reduce((sum, c) => sum + (c.credits ?? 3), 0);
          return { ...s, courses: nextCourses, credits };
        });
        workingPlan.semester_plan = updated;

        setPlan(workingPlan);
        {
          const restoredInstanceIds = new Set<string>();
          for (const term of workingPlan.semester_plan ?? []) {
            for (const course of term.courses ?? []) {
              if (course.code === code && course.instance_id) {
                restoredInstanceIds.add(course.instance_id);
              }
            }
          }
          if (restoredInstanceIds.size > 0) {
            setRemovedCourses(prev => prev.filter((id) => !restoredInstanceIds.has(id)));
          }
        }
        notify(`Replaced a ${targetGenEd} GenEd course with ${code} in ${replacedTerm}.`);
        return true;
      }
    }

    const placement = addCourseToPlan(workingPlan, code, preferredTargetTerm);
    if (!placement.term && !placement.restored) {
      const blockedReason = (placement as { blockedReason?: string }).blockedReason;
      notify(
        blockedReason
          ? `Cannot add ${code}. ${blockedReason}.`
          : 'No semesters found to place this course.'
      );
      return false;
    }

    setPlan(placement.plan);
    if (placement.restored) {
      const restoredInstanceIds = new Set<string>();
      for (const term of placement.plan.semester_plan ?? []) {
        for (const course of term.courses ?? []) {
          if (course.code === code && course.instance_id) {
            restoredInstanceIds.add(course.instance_id);
          }
        }
      }
      if (restoredInstanceIds.size > 0) {
        setRemovedCourses(prev => prev.filter((id) => !restoredInstanceIds.has(id)));
      }
    }

    if (placement.term) {
      notify(
        placement.appendedTerm
          ? `Added ${code} to ${placement.term}. (Created a new term because existing semesters were full.)`
          : `Added ${code} to ${placement.term}.`
      );
    }
    return true;
  };

  const progress: Progress[] = useMemo(() => {
    const items: Progress[] = [];
    const majors = (plan?.majors?.length ? plan.majors : selection.majors) ?? [];
    const majorProgress = plan?.category_progress?.majors ?? {};

    majors.forEach((major, idx) => {
      const data = majorProgress[major];
      if (!data) return;
      const label = majors.length > 1 ? `Major ${idx + 1}: ${major}` : `Major: ${major}`;
      items.push({
        category: label,
        completed: data.completed ?? 0,
        total: Math.max(data.required ?? 0, 1)
      });
    });

    const minorProgress = plan?.category_progress?.minors ?? {};
    const selectedMinors = (plan?.minors?.length ? plan.minors : selection.minors) ?? [];
    selectedMinors.forEach((minor) => {
      const data = minorProgress[minor];
      if (!data) return;
      items.push({
        category: `Minor: ${minor}`,
        completed: data.completed ?? 0,
        total: Math.max(data.required ?? 0, 1)
      });
    });

    const genEd = plan?.category_progress?.gen_ed;
    if (genEd) {
      items.push({
        category: 'GenEd',
        completed: genEd.completed ?? 0,
        total: Math.max(genEd.required ?? 0, 1)
      });
    }

    if (items.length > 0) return items;

    const fallbackTotal = plan?.summary?.total_required ?? 0;
    const fallbackCompleted = plan?.summary?.completed ?? 0;
    return [
      { category: 'Majors', completed: fallbackCompleted, total: Math.max(fallbackTotal, 1) },
      { category: 'Minors/GenEd', completed: fallbackCompleted, total: Math.max(fallbackTotal, 1) }
    ];
  }, [plan?.category_progress, plan?.majors, plan?.summary, selection.majors]);

  const genEdCategoryNeeds = useMemo(() => {
    const labelByNorm = new Map<string, string>();
    const requiredByNorm = new Map<string, number>();
    const courseCodesByCategory = new Map<string, Set<string>>();

    const registerCategory = (raw?: string | null, requiredValue?: number | null) => {
      const label = canonicalGenEdLabel(raw) || cleanGenEdLabel(raw);
      const normalized = normGenEd(label);
      if (!label || !normalized) return;
      if (!labelByNorm.has(normalized)) {
        labelByNorm.set(normalized, label);
      }
      if (requiredValue !== null && requiredValue !== undefined) {
        const numericRequired = Math.max(0, Number(requiredValue) || 0);
        const existing = requiredByNorm.get(normalized) ?? 0;
        if (numericRequired > existing) {
          requiredByNorm.set(normalized, numericRequired);
        }
      }
    };

    Object.entries(catalog.gen_ed?.rules ?? {}).forEach(([category, required]) => {
      registerCategory(category, Number(required ?? 0));
    });
    Object.keys(catalog.gen_ed?.categories ?? {}).forEach((category) => {
      registerCategory(category, null);
    });
    Object.entries(plan?.gen_ed_status ?? {}).forEach(([category, counts]) => {
      registerCategory(category, Number(counts?.required ?? 0));
    });

    for (const course of courseObjects) {
      const code = typeof course.code === 'string' ? normalizeCourseCode(course.code) : '';
      if (!code) continue;
      const categories = dedupeGenEdLabels([
        ...extractGenEdFromSatisfies(course.satisfies),
        ...getCourseGenEdTags(code),
      ]);
      for (const category of categories) {
        const label = canonicalGenEdLabel(category) || category;
        const normalized = normGenEd(label);
        if (!normalized) continue;
        registerCategory(label, null);
        if (!courseCodesByCategory.has(normalized)) {
          courseCodesByCategory.set(normalized, new Set<string>());
        }
        courseCodesByCategory.get(normalized)?.add(code);
      }
    }

    return Array.from(labelByNorm.entries())
      .map(([normalized, label]) => {
        const required = Math.max(1, requiredByNorm.get(normalized) ?? 1);
        const actualCount = courseCodesByCategory.get(normalized)?.size ?? 0;
        return {
          label,
          need: Math.max(0, required - actualCount),
        };
      })
      .sort((a, b) => {
        if (a.need !== b.need) return b.need - a.need;
        return a.label.localeCompare(b.label);
      });
  }, [catalog.gen_ed?.categories, catalog.gen_ed?.rules, plan?.gen_ed_status, courseObjects]);

  const wicRequirementStatus = useMemo(() => {
    const uniqueWicCodes = new Set<string>();
    for (const course of courseObjects) {
      const code = typeof course.code === 'string' ? course.code.trim() : '';
      if (!code) continue;
      if (code === 'ENG 1001' || code === 'ENG 1002') continue;
      if (catalog.course_meta?.[code]?.wic === true) {
        uniqueWicCodes.add(code);
      }
    }
    const required = 3;
    const completed = uniqueWicCodes.size;
    const need = Math.max(0, required - completed);
    return { required, completed, need };
  }, [courseObjects, catalog.course_meta]);

  const totalCredits = useMemo(() => {
    const unique = new Set([...effectiveCompleted, ...effectiveInProgress]);
    const completed = Array.from(unique).reduce((sum, code) => {
      return sum + (catalog.course_meta?.[code]?.credits ?? 3);
    }, 0);
    const total = plan?.summary?.total_required_credits ?? (plan?.summary?.total_required ?? 0) * 3;
    return { completed, total: total || 1 };
  }, [catalog.course_meta, effectiveCompleted, effectiveInProgress, plan?.summary]);

  const smartMinorSuggestions: ApiMinorSuggestion[] = useMemo(() => {
    if (!plan?.minor_suggestions?.length) return [];
    return plan.minor_suggestions.slice(0, 5);
  }, [plan?.minor_suggestions]);

  useEffect(() => {
    if (smartMinorSuggestions.length === 0) {
      setExpandedSmartMinor(null);
      return;
    }
    setExpandedSmartMinor((prev) => {
      if (prev && smartMinorSuggestions.some((entry) => entry.minor === prev)) {
        return prev;
      }
      return smartMinorSuggestions[0].minor;
    });
  }, [smartMinorSuggestions]);

  const electiveSuggestions: ElectiveSuggestion[] = useMemo(() => {
    if (plan?.elective_recommendations && plan.elective_recommendations.length > 0) {
      return plan.elective_recommendations.map((rec) => ({
        code: rec.code,
        name: rec.name,
        credits: rec.credits,
        requirementsSatisfied: rec.requirementsSatisfied,
        tags: rec.tags ?? [],
        explanation: rec.explanation
      }));
    }
    if (!plan?.minor_alerts?.length) return [];
    const suggestions: ElectiveSuggestion[] = [];
    for (const alert of plan.minor_alerts) {
      for (const code of alert.remaining_courses) {
        suggestions.push({
          code,
          name: catalog.courses[code] ?? code,
          credits: 3,
          requirementsSatisfied: 1,
          tags: [`Minor - ${alert.minor}`],
          explanation:
            `This course helps you complete the ${alert.minor} minor with minimal extra credits.`
        });
      }
    }
    // Deduplicate by code
    const seen = new Set<string>();
    return suggestions.filter(s => {
      if (seen.has(s.code)) return false;
      seen.add(s.code);
      return true;
    });
  }, [catalog.courses, plan?.minor_alerts, plan?.elective_recommendations]);

  const handleDownloadPdf = async () => {
    if (!plan) return;
    const blob = await downloadPlanPdf({
      catalog_id: catalog.catalog_id,
      majors: selection.majors,
      minors: selection.minors,
      completed_courses: planningCompleted,
      in_progress_courses: effectiveInProgress,
      in_progress_terms: inProgressOverrides,
      current_term_label: currentTermLabel,
      max_credits_per_semester: selection.maxCreditsPerSemester,
      start_term_season: effectiveStartForPlanning.season,
      start_term_year: effectiveStartForPlanning.year,
      waived_mat1000: selection.waivedMat1000,
      waived_eng1000: selection.waivedEng1000,
      overrides
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'degree-plan.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const handleDownloadJson = () => {
    if (!plan) return;
    const data = JSON.stringify({ ...plan, overrides }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'degree-plan.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const termPickerOptions = useMemo(() => {
    return buildTermLabels(startTermSeason, startTermYear, 8);
  }, [startTermSeason, startTermYear]);

  const termCreditsMap = useMemo(() => {
    const map: Record<string, number> = {};
    termPickerOptions.forEach((term) => {
      const credits = courseObjects
        .filter((c) => c.semester === term && c.status !== 'completed')
        .reduce((sum, c) => sum + Number(c.credits ?? 0), 0);
      map[term] = credits;
    });
    return map;
  }, [courseObjects, termPickerOptions]);

  const addableTermOptions = useMemo(() => {
    return termPickerOptions.filter((term) => (freeElectiveSlotsByTerm[term]?.length ?? 0) > 0);
  }, [termPickerOptions, freeElectiveSlotsByTerm]);

  const prereqTermOptions = useMemo(() => {
    if (!pendingPrereqPlacement) return [];
    const targetIdx = termIndexFromLabel(pendingPrereqPlacement.targetTerm);
    return termPickerOptions.filter((term) => {
      if ((freeElectiveSlotsByTerm[term]?.length ?? 0) === 0) return false;
      return termIndexFromLabel(term) < targetIdx;
    });
  }, [pendingPrereqPlacement, termPickerOptions, freeElectiveSlotsByTerm]);

  const pendingRemovalDetails = useMemo(() => {
    if (!pendingRemoval) return null;
    const target = courseObjects.find(c => c.instanceId === pendingRemoval.instanceId);
    if (!target) return null;
    const term = target.semester ?? pendingRemoval.term ?? null;
    const credits = target.credits ?? getCourseCredits(target.code);
    const termCredits = term ? (termCreditsMap[term] ?? 0) : 0;
    const afterCredits = Math.max(0, termCredits - credits);
    const belowMin = term && target.status !== 'completed' && afterCredits < minCreditsPerTerm;
    const genEdTags = getCourseGenEdTags(target.code);
    const downstream: string[] = [];
    if (term && plan?.semester_plan) {
      const removalIdx = termIndexFromLabel(term);
      for (const sem of plan.semester_plan) {
        const semIdx = termIndexFromLabel(sem.term);
        if (semIdx <= removalIdx) continue;
        for (const course of sem.courses ?? []) {
          if (!course.code || isRemovedPlanCourse(course)) continue;
          if (isFreeElectivePlaceholder(course.code)) continue;
          const baselineAvailable = buildAvailableCodesBeforeTerm(semIdx);
          const afterRemovalAvailable = buildAvailableCodesBeforeTerm(semIdx, {
            removedCode: target.code,
            removedTermIdx: removalIdx,
            removedInstanceId: pendingRemoval.instanceId
          });
          const baselineOk = isCoursePrereqSatisfiedWithAvailable(course.code, baselineAvailable);
          const afterOk = isCoursePrereqSatisfiedWithAvailable(course.code, afterRemovalAvailable);
          if (baselineOk && !afterOk) {
            downstream.push(course.code);
          }
        }
      }
    }
    return {
      target,
      term,
      credits,
      termCredits,
      afterCredits,
      belowMin,
      genEdTags,
      downstream: Array.from(new Set(downstream))
    };
  }, [pendingRemoval, courseObjects, termCreditsMap, minCreditsPerTerm, removedCourses, removedCodeSet]);

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--neutral-gray)' }}>
      {/* Top bar */}
      <div className="px-6 py-4 border-b flex items-center justify-between" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border"
          style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={handleDownloadJson}
            disabled={!plan}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border"
            style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
            title="Download JSON (re-upload later)"
          >
            <Download className="w-4 h-4" />
            JSON
          </button>

          <button
            onClick={handleDownloadPdf}
            disabled={!plan}
            className="flex items-center gap-2 px-4 py-2 rounded-lg"
            style={{
              background: plan ? 'var(--academic-gold)' : 'var(--neutral-border)',
              color: plan ? 'var(--navy-dark)' : 'var(--neutral-dark)'
            }}
            title="Download PDF"
          >
            <Download className="w-4 h-4" />
            PDF
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 grid lg:grid-cols-[1fr_420px] gap-6 p-6">
        {/* Left: Plan / Chat */}
        <div className="rounded-2xl border overflow-hidden" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
          <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--neutral-border)' }}>
            <div className="flex items-center gap-2">
              <Calendar className="w-5 h-5" style={{ color: 'var(--academic-gold)' }} />
              <h3 className="m-0">Your Plan</h3>
            </div>

            <div className="flex gap-2">
              <button
                className="px-4 py-2 rounded-lg text-sm font-medium"
                onClick={() => setActiveTab('plan')}
                style={{
                  backgroundColor: activeTab === 'plan' ? 'var(--academic-gold)' : 'transparent',
                  color: activeTab === 'plan' ? 'var(--navy-dark)' : 'var(--neutral-dark)'
                }}
              >
                Semester Plan
              </button>
              <button
                className="px-4 py-2 rounded-lg text-sm font-medium"
                onClick={() => setActiveTab('electives')}
                style={{
                  backgroundColor: activeTab === 'electives' ? 'var(--academic-gold)' : 'transparent',
                  color: activeTab === 'electives' ? 'var(--navy-dark)' : 'var(--neutral-dark)'
                }}
              >
                Recommended Electives
              </button>
              <button
                className="px-4 py-2 rounded-lg text-sm font-medium"
                onClick={() => setActiveTab('chat')}
                style={{
                  backgroundColor: activeTab === 'chat' ? 'var(--academic-gold)' : 'transparent',
                  color: activeTab === 'chat' ? 'var(--navy-dark)' : 'var(--neutral-dark)'
                }}
              >
                Advisor Chat
              </button>
            </div>
          </div>

          <div className="h-[calc(100vh-180px)]">
            {activeTab === 'plan' && (
              <div className="h-full">
                {!dismissedImpliedStart &&
                  creditsDone > selection.maxCreditsPerSemester &&
                  impliedStart.completedTerms >= 1 &&
                  (impliedStart.season !== startTermSeason || impliedStart.year !== startTermYear) && (
                    <div
                      className="mx-6 mt-6 mb-4 p-4 rounded-xl border"
                      style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-cream)' }}
                    >
                      <div className="flex flex-col gap-3">
                        <div>
                          <div className="font-medium">
                            Based on your completed/in-progress credits (~{creditsDone} credits), you likely started around{" "}
                            {impliedStart.season} {impliedStart.year}.
                          </div>
                          <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                            Adjust start term?
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="px-3 py-2 rounded-lg text-sm font-medium"
                            style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                            onClick={() => {
                              setStartTermUndo({
                                season: startTermSeason,
                                year: startTermYear,
                                completedCourses: [...completedCourses],
                                inProgressCourses: [...inProgressCourses],
                                inProgressOverrides: { ...inProgressOverrides }
                              });
                              setStartTermSeason(impliedStart.season);
                              setStartTermYear(impliedStart.year);
                              setCompletedCourses(prev => {
                                const merged = new Set([...prev, ...inProgressCourses]);
                                return Array.from(merged);
                              });
                              setInProgressCourses([]);
                              setInProgressOverrides({});
                              setAppliedImpliedStartKey(impliedStartKey);
                              setDismissedImpliedStart(true);
                            }}
                          >
                            Set start to {impliedStart.season} {impliedStart.year}
                          </button>
                          <button
                            type="button"
                            className="px-3 py-2 rounded-lg text-sm font-medium border"
                            style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                            onClick={() => {
                              setAppliedImpliedStartKey(impliedStartKey);
                              setDismissedImpliedStart(true);
                            }}
                          >
                            Keep {startTermSeason} {startTermYear}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                {startTermUndo && (
                  <div
                    className="mx-6 mt-4 mb-4 p-4 rounded-xl border"
                    style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                  >
                    <div className="flex flex-col gap-3">
                      <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                        Start term updated to {startTermSeason} {startTermYear}. Undo if this was a mistake.
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium border"
                          style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                          onClick={() => {
                            setStartTermSeason(startTermUndo.season);
                            setStartTermYear(startTermUndo.year);
                            setCompletedCourses(startTermUndo.completedCourses);
                            setInProgressCourses(startTermUndo.inProgressCourses);
                            setInProgressOverrides(startTermUndo.inProgressOverrides);
                            setAppliedImpliedStartKey(null);
                            setDismissedImpliedStart(false);
                            setStartTermUndo(null);
                          }}
                        >
                          Undo change
                        </button>
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium"
                          style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                          onClick={() => setStartTermUndo(null)}
                        >
                          Keep changes
                        </button>
                      </div>
                    </div>
                  </div>
                )}
                {loading && !plan && (
                  <div className="h-full flex items-center justify-center">
                    <div className="spinner" />
                  </div>
                )}
                {!loading && error && (
                  <div className="p-6">
                    <h4 className="mb-2">Error</h4>
                    <p style={{ color: 'var(--neutral-dark)' }}>{error}</p>
                  </div>
                )}
                {plan && (
                  <>
                    {plan.is_valid === false && plan.validation_errors && plan.validation_errors.length > 0 && (
                      <div className="mb-4 p-3 rounded-lg border" style={{ background: 'var(--neutral-cream)', borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}>
                        <div className="font-medium">Plan needs attention</div>
                        <div className="text-sm mt-1">
                          {plan.validation_errors.slice(0, 3).join(' · ')}
                          {plan.validation_errors.length > 3 ? ` · (+${plan.validation_errors.length - 3} more)` : ''}
                        </div>
                        <div className="text-xs mt-1" style={{ color: 'var(--neutral-dark)' }}>
                          You can still view and edit the plan, but graduation rules may not be fully satisfied yet.
                        </div>
                      </div>
                    )}
                    <SemesterPlanView
                    courses={courseObjects}
                    catalogCourses={catalog.courses}
                    startTermSeason={startTermSeason}
                    startTermYear={startTermYear}
                    totalTerms={maxPlanTerms}
                    electivePlaceholders={plan.elective_placeholders ?? []}
                    onToggleCompleted={(instanceId) => {
                      const target = courseObjects.find(c => c.instanceId === instanceId);
                      const code = target?.code;
                      if (!code) return;
                      const isCurrentlyCompleted = completedCourses.includes(code);
                      setCompletedCourses(prev => {
                        const next = prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code];
                        return next;
                      });
                      setInProgressCourses(prev => prev.filter(c => c !== code));
                      setInProgressOverrides(prev => {
                        if (!prev[code]) return prev;
                        const next = { ...prev };
                        delete next[code];
                        return next;
                      });
                      setCompletedOverrides(prev => {
                        const next = { ...prev };
                        if (isCurrentlyCompleted) {
                          delete next[code];
                        } else {
                          next[code] = target?.semester ?? `${startTermSeason} ${startTermYear}`;
                        }
                        return next;
                      });
                    }}
                    onToggleInProgress={(instanceId) => {
                      const target = courseObjects.find(c => c.instanceId === instanceId);
                      const code = target?.code;
                      const isCurrentlyInProgress = inProgressCourses.includes(code);
                      if (!target || !code) return;

                      if (!isCurrentlyInProgress) {
                        const availability = getCourseAvailabilityInfo(
                          { semester_availability: getCourseSemesterAvailability(code) },
                          { mode: "in_progress", isExcelOnly: isExcelOnlyCourse(code), currentTermLabel }
                        );
                        if (availability.isSelectionBlocked) {
                          setMessages(prev => [
                            ...prev,
                            {
                              role: 'assistant',
                              content: `${availability.warningLabel}. ${availability.detailsLabel}.`,
                              timestamp: new Date()
                            }
                          ]);
                          return;
                        }

                        const targetTerm = currentTermLabel;
                        const termCourses = courseObjects.filter(c => c.semester === targetTerm);
                        const termCredits = termCourses.reduce((sum, c) => sum + Number(c.credits ?? 0), 0);
                        const alreadyInCurrentTerm = target.semester === currentTermLabel;
                        const nextCredits = alreadyInCurrentTerm ? termCredits : termCredits + Number(target.credits ?? 0);
                        if (nextCredits > selection.maxCreditsPerSemester) {
                          setMessages(prev => [
                            ...prev,
                            {
                              role: 'assistant',
                              content: `${code} marked as in progress in ${targetTerm}. Note: this term is now above your max of ${selection.maxCreditsPerSemester} credits.`,
                              timestamp: new Date()
                            }
                          ]);
                        }
                      }

                      setInProgressCourses(prev => {
                        const next = prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code];
                        return next;
                      });
                      setInProgressOverrides(prev => {
                        const next = { ...prev };
                        if (isCurrentlyInProgress) {
                          delete next[code];
                          return next;
                        }
                        next[code] = currentTermLabel;
                        return next;
                      });
                      setCompletedCourses(prev => prev.filter(c => c !== code));
                      setCompletedOverrides(prev => {
                        if (!prev[code]) return prev;
                        const next = { ...prev };
                        delete next[code];
                        return next;
                      });
                    }}
                    onMoveCompleted={(instanceId, term) => {
                      const target = courseObjects.find(c => c.instanceId === instanceId);
                      const code = target?.code;
                      if (!code) return;
                      if (term === currentTermLabel) {
                        // Move to In Progress if user selects the current term.
                        setInProgressCourses(prev => (prev.includes(code) ? prev : [...prev, code]));
                        setInProgressOverrides(prev => ({ ...prev, [code]: term }));
                        setCompletedCourses(prev => prev.filter(c => c !== code));
                        setCompletedOverrides(prev => {
                          const next = { ...prev };
                          delete next[code];
                          return next;
                        });
                        return;
                      }
                      // Keep completed, just update the completed term.
                      setCompletedOverrides(prev => ({ ...prev, [code]: term }));
                      setInProgressCourses(prev => prev.filter(c => c !== code));
                      setInProgressOverrides(prev => {
                        if (!prev[code]) return prev;
                        const next = { ...prev };
                        delete next[code];
                        return next;
                      });
                    }}
                    onAddCourse={handleAddCourse}
                    onRemoveCourse={requestRemoveCourse}
                    onMoveCourse={handleMoveCourse}
                    movingCourseInstanceId={pendingSwapSourceInstanceId}
                    onChangeGenEd={(instanceId, term) => {
                      const target = courseObjects.find(c => c.instanceId === instanceId);
                      if (!target) return;
                      const hasGenEdSignal =
                        target.courseType === 'GENED' ||
                        (target.tags ?? []).includes('GEN ED') ||
                        (target.satisfies ?? []).some((s) => typeof s === 'string' && s.startsWith('GenEd:')) ||
                        (target.reason ?? '').includes('GenEd:');
                      const isProgramRequired =
                        target.courseType === 'PROGRAM' ||
                        (target.tags ?? []).includes('PROGRAM');
                      if (!hasGenEdSignal || isProgramRequired) return;
                      openReplacementDialog(instanceId, target.code, term);
                    }}
                  />
                  </>
                )}

                {pendingRemoval && pendingRemovalDetails && (
                  <div
                    style={{
                      position: 'fixed',
                      inset: 0,
                      background: 'rgba(0,0,0,0.45)',
                      zIndex: 1100,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '24px'
                    }}
                    onClick={() => setPendingRemoval(null)}
                  >
                    <div
                      style={{
                        background: 'var(--white)',
                        borderRadius: '12px',
                        maxWidth: '520px',
                        width: '100%',
                        padding: '20px',
                        border: '1px solid var(--neutral-border)'
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h4 className="mb-1">Remove {pendingRemovalDetails.target.code}?</h4>
                          <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                            {pendingRemovalDetails.target.status === 'completed'
                              ? 'This will remove it from your completed courses.'
                              : `This will remove it from ${pendingRemovalDetails.term ?? 'the plan'} and ask for a replacement if it is GenEd.`}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="text-sm"
                          style={{ color: 'var(--neutral-dark)' }}
                          onClick={() => setPendingRemoval(null)}
                        >
                          X
                        </button>
                      </div>

                      {pendingRemovalDetails.genEdTags.length > 0 && (
                        <div className="mt-3 text-xs" style={{ color: 'var(--neutral-dark)' }}>
                          GenEd categories: {pendingRemovalDetails.genEdTags.join(', ')}
                        </div>
                      )}

                      {pendingRemovalDetails.belowMin && pendingRemovalDetails.term && (
                        <div
                          className="mt-3 text-sm p-3 rounded-lg border"
                          style={{ background: 'var(--neutral-cream)', borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        >
                          {pendingRemovalDetails.term} would drop to {pendingRemovalDetails.afterCredits} credits, below the
                          {` ${minCreditsPerTerm}`} credit minimum.
                        </div>
                      )}
                      {pendingRemovalDetails.downstream.length > 0 && (
                        <div
                          className="mt-3 text-sm p-3 rounded-lg border"
                          style={{ background: 'var(--neutral-cream)', borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        >
                          Removing {pendingRemovalDetails.target.code} affects these later courses:
                          <div className="flex flex-wrap gap-2 mt-2">
                            {pendingRemovalDetails.downstream.map((code) => (
                              <span
                                key={code}
                                className="px-2 py-1 rounded text-xs"
                                style={{ backgroundColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                              >
                                {code}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2 mt-4">
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium"
                          style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                          onClick={confirmRemoveCourse}
                        >
                          Remove
                        </button>
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium border"
                          style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                          onClick={() => setPendingRemoval(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {moveCourseWarning && (
                  <div
                    style={{
                      position: 'fixed',
                      inset: 0,
                      background: 'rgba(0,0,0,0.45)',
                      zIndex: 1150,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '24px'
                    }}
                    onClick={() => setMoveCourseWarning(null)}
                  >
                    <div
                      style={{
                        background: 'var(--white)',
                        borderRadius: '12px',
                        maxWidth: '560px',
                        width: '100%',
                        padding: '20px',
                        border: '1px solid #fdba74'
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h4 className="mb-1" style={{ color: '#9a3412' }}>Cannot Move Course</h4>
                          <p className="text-sm" style={{ color: '#9a3412' }}>
                            {moveCourseWarning}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="text-sm"
                          style={{ color: '#9a3412' }}
                          onClick={() => setMoveCourseWarning(null)}
                        >
                          X
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-2 mt-4">
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium border"
                          style={{ borderColor: '#fdba74', background: '#fff7ed', color: '#9a3412' }}
                          onClick={() => setMoveCourseWarning(null)}
                        >
                          OK
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {pendingAddCourse && (
                  <div
                    style={{
                      position: 'fixed',
                      inset: 0,
                      background: 'rgba(0,0,0,0.45)',
                      zIndex: 1000,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '24px'
                    }}
                    onClick={() => {
                      setPendingAddCourse(null);
                      setPendingAddTerm(null);
                    }}
                  >
                    <div
                      style={{
                        background: 'var(--white)',
                        borderRadius: '12px',
                        maxWidth: '520px',
                        width: '100%',
                        padding: '20px',
                        border: '1px solid var(--neutral-border)',
                        maxHeight: '80vh',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column'
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h4 className="mb-1">Choose a term</h4>
                          <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                            Replace a FREE ELECTIVE slot with {pendingAddCourse.code}.
                          </p>
                        </div>
                        <button
                          type="button"
                          className="text-sm"
                          style={{ color: 'var(--neutral-dark)' }}
                          onClick={() => {
                            setPendingAddCourse(null);
                            setPendingAddTerm(null);
                          }}
                        >
                          X
                        </button>
                      </div>

                      <div className="grid gap-2 mt-4 overflow-y-auto" style={{ flex: 1, minHeight: 0 }}>
                        {addableTermOptions.length === 0 && (
                          <div
                            className="text-sm p-3 rounded-lg border"
                            style={{ color: 'var(--neutral-dark)', borderColor: 'var(--neutral-border)' }}
                          >
                            No FREE ELECTIVE slots are available to replace. Remove a free elective placeholder first.
                          </div>
                        )}
                        {addableTermOptions.map((term) => {
                          const placeholders = freeElectiveSlotsByTerm[term] ?? [];
                          const placeholder = placeholders[0];
                          const placeholderCredits = placeholder?.credits ?? 3;
                          const courseCredits = getCourseCredits(pendingAddCourse.code);
                          const termCredits = termCreditsMap[term] ?? 0;
                          const adjustedCredits = termCredits - placeholderCredits + courseCredits;
                          const willExceed = adjustedCredits > selection.maxCreditsPerSemester;
                          const availability = getCourseAvailabilityInfo(
                            { semester_availability: getCourseSemesterAvailability(pendingAddCourse.code) },
                            {
                              mode: "plan_add",
                              isExcelOnly: isExcelOnlyCourse(pendingAddCourse.code),
                              currentTermLabel,
                              targetTermLabel: term
                            }
                          );
                          const blockedByAvailability = availability.isSelectionBlocked;
                          const hasAvailabilityWarning = Boolean(availability.warningLabel);
                          const disabled = willExceed || blockedByAvailability;
                          const isSelected = pendingAddTerm === term;
                          return (
                            <button
                              key={term}
                              type="button"
                              disabled={disabled}
                              className="text-left p-3 rounded-lg border hover:shadow-sm"
                              style={{
                                borderColor: isSelected ? 'var(--navy-blue)' : 'var(--neutral-border)',
                                background: blockedByAvailability
                                  ? 'var(--neutral-gray)'
                                  : isSelected
                                    ? 'var(--neutral-gray)'
                                    : 'var(--white)',
                                opacity: disabled ? 0.6 : 1,
                                cursor: disabled ? 'not-allowed' : 'pointer'
                              }}
                              title={
                                hasAvailabilityWarning
                                  ? `${availability.warningLabel}.${availability.detailsLabel ? ` ${availability.detailsLabel}` : ""}`
                                  : undefined
                              }
                              onClick={() => setPendingAddTerm(term)}
                            >
                              <div className="font-medium">{term}</div>
                              <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                                {termCredits} credits now → {adjustedCredits} after swap
                                {" "}({placeholders.length} FREE ELECTIVE slot{placeholders.length === 1 ? "" : "s"})
                              </div>
                              {hasAvailabilityWarning && availability.warningLabel && availability.detailsLabel && (
                                <div className="text-xs mt-1" style={{ color: 'var(--neutral-dark)', fontStyle: 'italic' }}>
                                  {availability.warningLabel}. {availability.detailsLabel}
                                </div>
                              )}
                            </button>
                          );
                        })}
                      </div>

                      <div className="flex flex-wrap gap-2 mt-4">
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium"
                          style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                          disabled={!pendingAddTerm || addableTermOptions.length === 0}
                          onClick={() => {
                            const term = pendingAddTerm;
                            if (!term) return;
                            const code = pendingAddCourse.code;
                            const placeholders = freeElectiveSlotsByTerm[term] ?? [];
                            const placeholder = placeholders[0];
                            if (!placeholder) {
                              setMessages(prev => [
                                ...prev,
                                {
                                  role: 'assistant',
                                  content: `No FREE ELECTIVE slot found in ${term}.`,
                                  timestamp: new Date()
                                }
                              ]);
                              return;
                            }
                            const placeholderId = placeholder.instance_id ?? `${term}:${placeholder.code}`;
                            const availability = getCourseAvailabilityInfo(
                              { semester_availability: getCourseSemesterAvailability(code) },
                              {
                                mode: "plan_add",
                                isExcelOnly: isExcelOnlyCourse(code),
                                currentTermLabel,
                                targetTermLabel: term
                              }
                            );
                            if (availability.isSelectionBlocked) {
                              setMessages(prev => [
                                ...prev,
                                {
                                  role: 'assistant',
                                  content: `${availability.warningLabel}. ${availability.detailsLabel}.`,
                                  timestamp: new Date()
                                }
                              ]);
                              return;
                            }
                            const status = getPrereqStatusForTerm(code, term);

                            setPendingAddCourse(null);
                            setPendingAddTerm(null);

                            if (status.prereqs.length > 0) {
                              setPendingAddConfirm({
                                code,
                                term,
                                prereqs: status.prereqs,
                                unmet: status.unmet,
                                unmetCodes: status.unmetCodes,
                                satisfied: status.satisfied,
                                replaceFreeElective: { instanceId: placeholderId, code: placeholder.code }
                              });
                              return;
                            }

                            const committed = commitAtomicOverrideAdd(term, code, {
                              replaceFreeElective: { instanceId: placeholderId, code: placeholder.code },
                            });
                            if (!committed) return;
                            setMessages(prev => [
                              ...prev,
                              { role: 'assistant', content: `Replaced ${placeholder.code} with ${code} in ${term}.`, timestamp: new Date() }
                            ]);
                          }}
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium border"
                          style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                          onClick={() => {
                            setPendingAddCourse(null);
                            setPendingAddTerm(null);
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                
                {pendingAddConfirm && (
                  <div
                    style={{
                      position: 'fixed',
                      inset: 0,
                      background: 'rgba(0,0,0,0.45)',
                      zIndex: 1000,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '24px'
                    }}
                    onClick={() => setPendingAddConfirm(null)}
                  >
                    <div
                      style={{
                        background: 'var(--white)',
                        borderRadius: '12px',
                        maxWidth: '520px',
                        width: '100%',
                        padding: '20px',
                        border: '1px solid var(--neutral-border)',
                        maxHeight: '80vh',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column'
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <PrereqConfirmDialog
                        courseToAdd={{
                          code: pendingAddConfirm.code,
                          name: resolveCourseName(pendingAddConfirm.code),
                          term: pendingAddConfirm.term
                        }}
                        title={`Add ${pendingAddConfirm.code} to ${pendingAddConfirm.term}?`}
                        prereqs={pendingAddConfirm.prereqs}
                        unmetPrereqs={pendingAddConfirm.unmet}
                        prereqsSatisfied={pendingAddConfirm.satisfied}
                        resolvePrereqName={(code) => resolveCourseName(code)}
                        onConfirm={() => {
                          const { code, term } = pendingAddConfirm;
                          const unmetCodes = pendingAddConfirm.unmetCodes;
                          const placeholder = pendingAddConfirm.replaceFreeElective;
                          setPendingAddConfirm(null);
                          if (unmetCodes.length > 0) {
                            setPendingPrereqPlacement({
                              courseCode: code,
                              targetTerm: term,
                              prereqs: unmetCodes,
                              index: 0,
                              replaceFreeElective: placeholder
                            });
                            setPendingPrereqTerm(null);
                            return;
                          }
                          if (placeholder) {
                            const committed = commitAtomicOverrideAdd(term, code, {
                              replaceFreeElective: placeholder,
                            });
                            if (!committed) return;
                          } else {
                            const committed = commitAtomicOverrideAdd(term, code);
                            if (!committed) return;
                          }
                          setMessages(prev => [
                            ...prev,
                            {
                              role: 'assistant',
                              content: placeholder
                                ? `Replaced ${placeholder.code} with ${code} in ${term}.`
                                : `Added ${code} to ${term}.`,
                              timestamp: new Date()
                            }
                          ]);
                        }}
                        onCancel={() => setPendingAddConfirm(null)}
                      />
                    </div>
                  </div>
                )}
                {pendingPrereqPlacement && (
                  <div
                    style={{
                      position: 'fixed',
                      inset: 0,
                      background: 'rgba(0,0,0,0.45)',
                      zIndex: 1000,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '24px'
                    }}
                    onClick={() => {
                      setPendingPrereqPlacement(null);
                      setPendingPrereqTerm(null);
                    }}
                  >
                    <div
                      style={{
                        background: 'var(--white)',
                        borderRadius: '12px',
                        maxWidth: '520px',
                        width: '100%',
                        padding: '20px',
                        border: '1px solid var(--neutral-border)',
                        maxHeight: '80vh',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column'
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h4 className="mb-1">Schedule prerequisite</h4>
                          <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                            Choose a term for {pendingPrereqPlacement.prereqs[pendingPrereqPlacement.index]} before{" "}
                            {pendingPrereqPlacement.targetTerm}.
                          </p>
                        </div>
                        <button
                          type="button"
                          className="text-sm"
                          style={{ color: 'var(--neutral-dark)' }}
                          onClick={() => {
                            setPendingPrereqPlacement(null);
                            setPendingPrereqTerm(null);
                          }}
                        >
                          X
                        </button>
                      </div>

                      <div className="grid gap-2 mt-4 overflow-y-auto" style={{ flex: 1, minHeight: 0 }}>
                        {prereqTermOptions.length === 0 && (
                          <div
                            className="text-sm p-3 rounded-lg border"
                            style={{ color: 'var(--neutral-dark)', borderColor: 'var(--neutral-border)' }}
                          >
                            No FREE ELECTIVE slots are available before {pendingPrereqPlacement.targetTerm}.
                          </div>
                        )}
                        {prereqTermOptions.map((term) => {
                          const placeholders = freeElectiveSlotsByTerm[term] ?? [];
                          const placeholder = placeholders[0];
                          const placeholderCredits = placeholder?.credits ?? 3;
                          const prereqCode = pendingPrereqPlacement.prereqs[pendingPrereqPlacement.index];
                          const courseCredits = getCourseCredits(prereqCode);
                          const termCredits = termCreditsMap[term] ?? 0;
                          const adjustedCredits = termCredits - placeholderCredits + courseCredits;
                          const willExceed = adjustedCredits > selection.maxCreditsPerSemester;
                          const isSelected = pendingPrereqTerm === term;
                          return (
                            <button
                              key={term}
                              type="button"
                              disabled={willExceed}
                              className="text-left p-3 rounded-lg border hover:shadow-sm"
                              style={{
                                borderColor: isSelected ? 'var(--navy-blue)' : 'var(--neutral-border)',
                                background: isSelected ? 'var(--neutral-gray)' : 'var(--white)',
                                opacity: willExceed ? 0.5 : 1,
                                cursor: willExceed ? 'not-allowed' : 'pointer'
                              }}
                              onClick={() => setPendingPrereqTerm(term)}
                            >
                              <div className="font-medium">{term}</div>
                              <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                                {termCredits} credits now → {adjustedCredits} after swap
                              </div>
                            </button>
                          );
                        })}
                      </div>

                      <div className="flex flex-wrap gap-2 mt-4">
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium"
                          style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                          disabled={!pendingPrereqTerm || prereqTermOptions.length === 0}
                          onClick={() => {
                            if (!pendingPrereqPlacement) return;
                            const prereqCode = pendingPrereqPlacement.prereqs[pendingPrereqPlacement.index];
                            const term = pendingPrereqTerm;
                            if (!term) return;
                            const placeholders = freeElectiveSlotsByTerm[term] ?? [];
                            const placeholder = placeholders[0];
                            if (!placeholder) {
                              setMessages(prev => [
                                ...prev,
                                {
                                  role: 'assistant',
                                  content: `No FREE ELECTIVE slot found in ${term}.`,
                                  timestamp: new Date()
                                }
                              ]);
                              return;
                            }
                            const placeholderId = placeholder.instance_id ?? `${term}:${placeholder.code}`;
                            addOverrideRemove(term, placeholderId, placeholder.code);
                            setRemovedCourses(prev =>
                              prev.includes(placeholderId) ? prev : [...prev, placeholderId]
                            );
                            addOverrideAdd(term, prereqCode, createInstanceId());
                            setMessages(prev => [
                              ...prev,
                              { role: 'assistant', content: `Scheduled prerequisite ${prereqCode} in ${term}.`, timestamp: new Date() }
                            ]);

                            const nextIndex = pendingPrereqPlacement.index + 1;
                            if (nextIndex < pendingPrereqPlacement.prereqs.length) {
                              setPendingPrereqPlacement({
                                ...pendingPrereqPlacement,
                                index: nextIndex
                              });
                              setPendingPrereqTerm(null);
                              return;
                            }

                            const targetTerm = pendingPrereqPlacement.targetTerm;
                            const targetPlaceholder = pendingPrereqPlacement.replaceFreeElective;
                            if (targetPlaceholder) {
                              addOverrideRemove(targetTerm, targetPlaceholder.instanceId, targetPlaceholder.code);
                              setRemovedCourses(prev =>
                                prev.includes(targetPlaceholder.instanceId)
                                  ? prev
                                  : [...prev, targetPlaceholder.instanceId]
                              );
                            }
                            const addedTargetInstanceId = createInstanceId();
                            addOverrideAdd(targetTerm, pendingPrereqPlacement.courseCode, addedTargetInstanceId);
                            if (targetPlaceholder) {
                              upsertSwappedElective({
                                termLabel: targetTerm,
                                addedCourseCode: pendingPrereqPlacement.courseCode,
                                addedCourseInstanceId: addedTargetInstanceId,
                                replacedPlaceholderInstanceId: targetPlaceholder.instanceId,
                                placeholderCode: targetPlaceholder.code,
                                placeholderCredits: getCourseCredits(targetPlaceholder.code),
                              });
                            }
                            setMessages(prev => [
                              ...prev,
                              {
                                role: 'assistant',
                                content: targetPlaceholder
                                  ? `Replaced ${targetPlaceholder.code} with ${pendingPrereqPlacement.courseCode} in ${targetTerm}.`
                                  : `Added ${pendingPrereqPlacement.courseCode} to ${targetTerm}.`,
                                timestamp: new Date()
                              }
                            ]);
                            setPendingPrereqPlacement(null);
                            setPendingPrereqTerm(null);
                          }}
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          className="px-3 py-2 rounded-lg text-sm font-medium border"
                          style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                          onClick={() => {
                            setPendingPrereqPlacement(null);
                            setPendingPrereqTerm(null);
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}
{replacementTarget && replacementTargetCode && (
                  <div
                    style={{
                      position: 'fixed',
                      inset: 0,
                      background: 'rgba(0,0,0,0.45)',
                      zIndex: 1000,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '24px'
                    }}
                    onClick={resetReplacementState}
                  >
                    <div
                      style={{
                        background: 'var(--white)',
                        borderRadius: '12px',
                        maxWidth: '640px',
                        width: '100%',
                        padding: '20px',
                        border: '1px solid var(--neutral-border)',
                        maxHeight: '80vh',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column'
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h4 className="mb-1">Choose a GenEd replacement</h4>
                          <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                            {replacementCategories.length > 1
                              ? 'Multiple GenEd categories available.'
                              : (
                                replacementCategory
                                  ? `Category: ${formatGenEdNeedLabel(replacementCategory, genEdNeedByCategory)}`
                                  : "No category"
                              )}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="text-sm"
                          style={{ color: 'var(--neutral-dark)' }}
                          onClick={resetReplacementState}
                        >
                          X
                        </button>
                      </div>

                      <div className="grid gap-3 mt-3">
                        {replacementCategories.length > 1 && (
                          <div>
                            <label className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
                              GenEd category
                            </label>
                            <select
                              className="w-full mt-1 px-3 py-2 rounded-lg border text-sm"
                              style={{ borderColor: 'var(--neutral-border)' }}
                              value={replacementCategory ?? ''}
                              onChange={(e) => {
                                const nextCategory = e.target.value;
                                setReplacementCategory(nextCategory);
                                if (replacementTargetCode) {
                                  setReplacementOptions(buildReplacementOptions(nextCategory, replacementTargetCode));
                                }
                                setPendingReplacement(null);
                              }}
                            >
                              {replacementCategories.map((cat) => (
                                <option key={cat} value={cat}>
                                  {formatGenEdNeedLabel(cat, genEdNeedByCategory)}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>

                      {replacementOptions.length === 0 && (
                        <p className="text-sm mt-4" style={{ color: 'var(--neutral-dark)' }}>
                          No available courses found for this GenEd category.
                        </p>
                      )}

                      <div
                        className="grid gap-2 mt-4 overflow-y-auto"
                        style={{ flex: 1, minHeight: 0 }}
                      >
                        {replacementOptions.map((code) => {
                          const replacementTerm = replacementTargetTerm;
                          const isCurrent = code === replacementTargetCode;
                          const isSelected = pendingReplacement?.nextCode === code;
                          const courseCredits = getCourseCredits(code);
                          const termCredits = replacementTerm ? (termCreditsMap[replacementTerm] ?? 0) : 0;
                          const targetCourse = replacementTarget
                            ? courseObjects.find((c) => c.instanceId === replacementTarget)
                            : null;
                          const targetCredits = targetCourse
                            ? Number(targetCourse.credits ?? getCourseCredits(targetCourse.code))
                            : replacementTargetCode
                              ? Number(getCourseCredits(replacementTargetCode))
                              : 0;
                          const targetTerm = replacementTargetTerm;
                          const effectiveCredits = replacementTerm
                            ? termCredits - ((targetCourse && targetTerm === replacementTerm) ? targetCredits : 0)
                            : termCredits;
                          const willExceed = !isCurrent && replacementTerm
                            ? effectiveCredits + courseCredits > selection.maxCreditsPerSemester
                            : false;
                          const disabled = !replacementTerm || willExceed;
                          return (
                            <button
                              key={code}
                              type="button"
                              disabled={disabled}
                              className="text-left p-3 rounded-lg border hover:shadow-sm"
                              style={{
                                borderColor: isSelected ? 'var(--navy-blue)' : 'var(--neutral-border)',
                                background: isSelected ? 'var(--neutral-gray)' : 'var(--white)',
                                opacity: disabled ? 0.55 : 1,
                                cursor: disabled ? 'not-allowed' : 'pointer'
                              }}
                              onClick={() => {
                                if (disabled) return;
                                const targetInstanceId = replacementTarget;
                                const targetCode = replacementTargetCode;
                                if (!targetInstanceId || !targetCode || !replacementTerm) return;
                                setPendingReplacement({
                                  targetInstanceId,
                                  targetCode,
                                  nextCode: code,
                                  semester: replacementTerm,
                                  category: replacementCategory,
                                  prereqs: getCoursePrereqs(code)
                                });
                              }}
                            >
                              <div className="font-medium">
                                {isCurrent ? `Keep current: ${code}` : code}
                              </div>
                              <div className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                                {catalog.courses[code] ?? code}
                              </div>
                              {!isCurrent && replacementTerm && (
                                <div className="text-xs mt-1" style={{ color: 'var(--neutral-dark)' }}>
                                  {effectiveCredits} credits now - {courseCredits} credits added
                                  {willExceed ? ' (over max)' : ''}
                                </div>
                              )}
                            </button>
                          );
                        })}
                      </div>

                      {pendingReplacementImpact && (
                        <div
                          style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(0,0,0,0.45)',
                            zIndex: 1200,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '24px'
                          }}
                          onClick={() => setPendingReplacementImpact(null)}
                        >
                          <div
                            style={{
                              background: 'var(--white)',
                              borderRadius: '12px',
                              maxWidth: '520px',
                              width: '100%',
                              padding: '20px',
                              border: '1px solid var(--neutral-border)'
                            }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <h4 className="mb-1">{pendingReplacementImpact.targetCode} is a prerequisite</h4>
                                <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                                  Replacing it will remove these dependent courses from your plan.
                                </p>
                              </div>
                              <button
                                type="button"
                                className="text-sm"
                                style={{ color: 'var(--neutral-dark)' }}
                                onClick={() => setPendingReplacementImpact(null)}
                              >
                                X
                              </button>
                            </div>
                            <div
                              className="mt-3 text-sm p-3 rounded-lg border"
                              style={{ background: 'var(--neutral-cream)', borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                            >
                              Dependent courses:
                              <div className="flex flex-wrap gap-2 mt-2">
                                {pendingReplacementImpact.dependents.map((dep) => (
                                  <span
                                    key={dep.code}
                                    className="px-2 py-1 rounded text-xs"
                                    style={{ backgroundColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                                  >
                                    {dep.code}
                                  </span>
                                ))}
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-2 mt-4">
                              <button
                                type="button"
                                className="px-3 py-2 rounded-lg text-sm font-medium"
                                style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                                onClick={() => {
                                  confirmReplacement(true);
                                  setPendingReplacementImpact(null);
                                }}
                              >
                                Replace & remove dependents
                              </button>
                              <button
                                type="button"
                                className="px-3 py-2 rounded-lg text-sm font-medium border"
                                style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
                                onClick={() => setPendingReplacementImpact(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      {pendingReplacement && pendingReplacementDownstreamPreview.length > 0 && (
                        <div
                          className="mt-3 text-sm p-3 rounded-lg border"
                          style={{ background: 'var(--neutral-cream)', borderColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                        >
                          Warning: changing {pendingReplacement.targetCode} affects these later courses:
                          <div className="flex flex-wrap gap-2 mt-2">
                            {pendingReplacementDownstreamPreview.map((dep) => (
                              <span
                                key={`${dep.code}:${dep.term ?? ''}:${dep.instanceId ?? ''}`}
                                className="px-2 py-1 rounded text-xs"
                                style={{ backgroundColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                              >
                                {dep.code}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {pendingReplacement && pendingReplacementStatus && (
                        <PrereqConfirmDialog
                          courseToAdd={{
                            code: pendingReplacement.nextCode,
                            name: resolveCourseName(pendingReplacement.nextCode),
                            term: pendingReplacement.semester
                          }}
                          title={
                            pendingReplacement.nextCode === pendingReplacement.targetCode
                              ? `Keep ${pendingReplacement.targetCode}?`
                              : `Replace ${pendingReplacement.targetCode} with ${pendingReplacement.nextCode}?`
                          }
                          prereqs={pendingReplacementStatus.prereqs}
                          unmetPrereqs={pendingReplacementStatus.unmet}
                          prereqsSatisfied={pendingReplacementStatus.satisfied}
                          resolvePrereqName={(code) => resolveCourseName(code)}
                          onConfirm={confirmReplacement}
                          onCancel={() => setPendingReplacement(null)}
                        />
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'electives' && (
              <div className="h-full p-6 overflow-y-auto">
                {loading && !plan && (
                  <div className="h-full flex items-center justify-center">
                    <div className="spinner" />
                  </div>
                )}
                {!plan && !loading && (
                  <p style={{ color: 'var(--neutral-dark)' }}>No plan yet.</p>
                )}
                {plan && (
                  <>
                    {electiveSuggestions.length === 0 && (
                      <p style={{ color: 'var(--neutral-dark)' }}>
                        No elective recommendations yet. As you get close to a minor, suggestions will appear here.
                      </p>
                    )}
                    {electiveSuggestions.length > 0 && (
                      <ElectiveRecommendationPanel
                        electives={electiveSuggestions}
                        onAdd={handleAddCourse}
                        existingCodes={existingCourseCodes}
                      />
                    )}
                  </>
                )}
              </div>
            )}

            {activeTab === 'chat' && (
              <ChatInterface
                messages={messages}
                onSendMessage={(msg) => {
                  // For now, chat is explanatory; we append the question and a deterministic reply.
                  setMessages(prev => [
                    ...prev,
                    { role: 'user', content: msg, timestamp: new Date() },
                    {
                      role: 'assistant',
                      content:
                        'Right now, the advisor chat is connected to the real plan engine but does not change your plan. ' +
                        'In the next iteration we can add actions like “add minor”, “recompute”, and “why this course?”.',
                      timestamp: new Date()
                    }
                  ]);
                }}
              />
            )}
          </div>
        </div>

        {/* Right: Progress + Alerts */}
        <div className="rounded-2xl border overflow-hidden" style={{ background: 'var(--white)', borderColor: 'var(--neutral-border)' }}>
          <div className="p-4 border-b" style={{ borderColor: 'var(--neutral-border)' }}>
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: 'var(--academic-gold)' }}
              >
                <Sparkles className="w-4 h-4" style={{ color: 'var(--white)' }} />
              </div>
              <div>
                <h4 style={{ color: 'var(--navy-dark)', marginBottom: '2px' }}>Smart Minor Suggestions</h4>
                <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                  Complete minors efficiently
                </p>
              </div>
            </div>
            {smartMinorSuggestions.length === 0 && (
              <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                No minor suggestions available.
              </p>
            )}
            {smartMinorSuggestions.length > 0 && (
              <div className="space-y-2">
                {smartMinorSuggestions.map((suggestion) => (
                  (() => {
                    const needCount = Math.max(0, Number(suggestion.remaining_count ?? suggestion.remaining_courses.length ?? 0));
                    const estimatedTotal = Math.max(3, needCount + 1);
                    const doneCount = Math.max(0, estimatedTotal - needCount);
                    const isOpen = expandedSmartMinor === suggestion.minor;
                    const remainingItems = (suggestion.remaining_courses ?? []).slice(0, 4);
                    const creditImpact = needCount * 3;

                    return (
                      <div
                        key={suggestion.minor}
                        className="rounded-xl border"
                        style={{
                          borderColor: isOpen ? 'var(--academic-gold)' : 'var(--neutral-border)',
                          background: 'var(--white)'
                        }}
                      >
                        <button
                          type="button"
                          className="w-full p-3 text-left"
                          onClick={() => setExpandedSmartMinor(prev => (prev === suggestion.minor ? null : suggestion.minor))}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold" style={{ color: 'var(--navy-dark)' }}>
                                {suggestion.minor}
                              </span>
                              <span
                                className="px-1.5 py-0.5 rounded text-xs font-semibold"
                                style={{ color: 'var(--black)' }}
                              >
                                {needCount}
                              </span>
                            </div>
                            {isOpen ? (
                              <ChevronUp className="w-4 h-4" style={{ color: 'var(--neutral-dark)' }} />
                            ) : (
                              <ChevronDown className="w-4 h-4" style={{ color: 'var(--neutral-dark)' }} />
                            )}
                          </div>
                          <div className="text-sm mt-1" style={{ color: 'var(--neutral-dark)' }}>
                            +{creditImpact} credits
                          </div>
                          <div className="mt-2 flex items-center justify-end">
                            <span className="text-xs font-medium" style={{ color: 'var(--navy-dark)' }}>
                              {doneCount}/{estimatedTotal}
                            </span>
                          </div>
                        </button>

                        {isOpen && (
                          <div className="px-3 pb-3 pt-0 border-t" style={{ borderColor: 'var(--neutral-border)' }}>
                            <div
                              className="mt-2 p-2 rounded text-sm"
                              style={{ background: 'var(--neutral-cream)', color: 'var(--navy-dark)' }}
                            >
                              {suggestion.why}
                            </div>
                            <div className="grid grid-cols-2 gap-2 mt-2">
                              <div>
                                <div className="text-sm font-semibold flex items-center gap-1" style={{ color: '#10B981' }}>
                                  <Check className="w-4 h-4" />
                                  Done ({doneCount})
                                </div>
                                <div
                                  className="mt-1 p-2 rounded text-xs"
                                  style={{ background: 'var(--neutral-gray)', color: 'var(--neutral-dark)' }}
                                >
                                  Completed items are tracked automatically from your plan and transcript.
                                </div>
                              </div>
                              <div>
                                <div className="text-sm font-semibold" style={{ color: 'var(--academic-gold)' }}>
                                  Need ({needCount})
                                </div>
                                <div className="mt-1 space-y-1">
                                  {remainingItems.map((courseCode, index) => (
                                    <div
                                      key={`${suggestion.minor}:${courseCode}:${index}`}
                                      className="px-2 py-1 rounded text-xs border"
                                      style={{ borderColor: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
                                    >
                                      {courseCode}
                                    </div>
                                  ))}
                                  {remainingItems.length === 0 && (
                                    <div className="text-xs" style={{ color: 'var(--neutral-dark)' }}>
                                      No missing courses listed.
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()
                ))}
              </div>
            )}

            {(genEdCategoryNeeds.length > 0 || !!plan) && (
              <div
                className="p-3 rounded-lg border mt-4"
                style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-cream)' }}
              >
                <div className="font-semibold" style={{ color: 'var(--navy-dark)' }}>
                  GenEd Categories
                </div>
                <div className="mt-2 space-y-2">
                  {genEdCategoryNeeds.map((entry) => (
                    <div key={entry.label} className="flex items-center justify-between gap-3">
                      <span className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                        {entry.label}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={
                          entry.need === 0
                            ? { background: '#D7F4E6', color: '#0B6E4F' }
                            : { background: '#FCE8B2', color: '#6A4B00' }
                        }
                      >
                        {entry.need === 0 ? 'Satisfied' : `Need ${entry.need}`}
                      </span>
                    </div>
                  ))}
                  <div key="wic-requirement" className="flex items-center justify-between gap-3">
                    <span className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                      Writing Intensive Courses (WICs) ({wicRequirementStatus.completed}/{wicRequirementStatus.required})
                    </span>
                    <span
                      className="px-2 py-0.5 rounded text-xs font-medium"
                      style={
                        wicRequirementStatus.need === 0
                          ? { background: '#D7F4E6', color: '#0B6E4F' }
                          : { background: '#FCE8B2', color: '#6A4B00' }
                      }
                    >
                      {wicRequirementStatus.need === 0 ? 'Satisfied' : `Need ${wicRequirementStatus.need}`}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <ProgressDashboard
            progress={progress}
            totalCredits={totalCredits}
            catalogYear={catalog.catalog_year ?? '2025-26'}
          />
        </div>
      </div>
      {loading && plan && (
        <div
          className="plan-update-overlay"
          role="status"
          aria-live="polite"
          aria-label="Updating your plan"
        >
          <div className="plan-update-card">
            <div className="plan-update-loader" aria-hidden="true">
              <span className="plan-update-dot" />
              <span className="plan-update-dot" />
              <span className="plan-update-dot" />
            </div>
            <h4 className="plan-update-title">Updating your plan</h4>
            <p className="plan-update-text">Applying changes and revalidating requirements...</p>
          </div>
        </div>
      )}
      {pendingSwapSourceCourse && (
        <div
          style={{
            position: "fixed",
            right: "16px",
            bottom: "16px",
            zIndex: 1050,
            width: "min(460px, calc(100vw - 32px))",
            background: "var(--neutral-cream)",
            border: "1px solid var(--neutral-border)",
            borderRadius: "10px",
            padding: "10px 12px",
            boxShadow: "0 10px 24px rgba(0,0,0,0.18)",
            color: "var(--navy-dark)",
          }}
        >
          <div className="text-sm">
            Move course mode: selected <b>{pendingSwapSourceCourse.code}</b> in{" "}
            <b>{pendingSwapSourceCourse.semester}</b>. Click <b>Move course</b> on another planned course to swap.
          </div>
          <div className="mt-2">
            <button
              type="button"
              className="text-xs px-2 py-1 rounded border"
              style={{ borderColor: "var(--neutral-border)", color: "var(--navy-dark)", background: "var(--white)" }}
              onClick={() => {
                setPendingSwapSourceInstanceId(null);
                setMoveCourseWarning(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}











import { useState } from 'react';
import { Briefcase, CheckCircle2, ChevronDown, Lightbulb, PenLine, Shapes } from 'lucide-react';
import type { GeneratePlanResponse, MinorSuggestion } from '../../api';
import type { Progress } from '../../types';
import type { ElectiveRequirementSummary } from '../../utils/electiveProgress';
import { ElectiveProgressCards } from './ElectiveProgressCards';
import { ProgressDashboard } from '../ProgressDashboard';

type ConcentrationAudit = NonNullable<GeneratePlanResponse['business_concentration_audit']>;

interface RequirementsTabProps {
  electiveRequirements: ElectiveRequirementSummary[];
  progress: Progress[];
  totalCredits: { completed: number; total: number };
  catalogYear: string;
  genEdNeeds: { label: string; need: number }[];
  wic: { required: number; completed: number; need: number };
  concentrationAudit: GeneratePlanResponse['business_concentration_audit'];
  minorSuggestions: MinorSuggestion[];
}

const STATUS_BADGE: Record<string, string> = {
  completed: 'badge-success',
  planned: 'badge-info',
  missing: 'badge-warning',
};

function NeedBadge({ need }: { need: number }) {
  return need === 0 ? (
    <span className="badge badge-success">
      <CheckCircle2 aria-hidden="true" />
      Covered
    </span>
  ) : (
    <span className="badge badge-warning num">Need {need}</span>
  );
}

function GenEdCard({ genEdNeeds, wic }: Pick<RequirementsTabProps, 'genEdNeeds' | 'wic'>) {
  return (
    <section className="card card-pad stack-4" aria-labelledby="gened-title">
      <header className="flex items-center gap-3">
        <span className="icon-tile" aria-hidden="true"><Shapes /></span>
        <div>
          <h2 id="gened-title" className="section-title">General education</h2>
          <p className="section-subtitle">Categories covered by completed and planned courses.</p>
        </div>
      </header>
      <ul className="requirement-list">
        {genEdNeeds.map((entry) => (
          <li key={entry.label}>
            <span>{entry.label}</span>
            <NeedBadge need={entry.need} />
          </li>
        ))}
        <li>
          <span className="flex items-center gap-2">
            <PenLine aria-hidden="true" className="requirement-icon" />
            Writing intensive courses <span className="muted num">({wic.completed}/{wic.required})</span>
          </span>
          <NeedBadge need={wic.need} />
        </li>
      </ul>
    </section>
  );
}

function ConcentrationCard({ audit }: { audit: ConcentrationAudit }) {
  const summary = audit.summary ?? {};
  const satisfied =
    Number(summary.missing_required_courses ?? 0) === 0
    && Number(summary.remaining_pool_credits ?? 0) === 0
    && Number(summary.remaining_pool_courses ?? 0) === 0;
  return (
    <section className="card card-pad stack-4" aria-labelledby="concentration-title">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="icon-tile" aria-hidden="true"><Briefcase /></span>
          <div>
            <h2 id="concentration-title" className="section-title">Business concentration</h2>
            <p className="section-subtitle">{audit.selected}</p>
          </div>
        </div>
        <span className={`badge ${satisfied ? 'badge-success' : 'badge-warning'}`}>
          {satisfied ? 'Satisfied' : 'In progress'}
        </span>
      </header>

      {(audit.messages ?? []).map((message, index) => (
        <div key={`${message.kind}:${index}`} className={`alert ${message.kind === 'conflict' ? 'alert-warning' : 'alert-info'}`}>
          <p>{message.message}</p>
        </div>
      ))}

      {(audit.required_courses ?? []).length > 0 && (
        <div className="stack-2">
          <span className="text-xs font-semibold muted">Required courses</span>
          <ul className="requirement-list">
            {(audit.required_courses ?? []).map((course) => (
              <li key={course.code}>
                <span><span className="font-semibold">{course.code}</span> <span className="muted">{course.title}</span></span>
                <span className={`badge ${STATUS_BADGE[course.status] ?? 'badge-neutral'}`}>{course.status}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(audit.elective_pools ?? []).map((pool) => (
        <div key={pool.id} className="pool stack-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-sm">{pool.label}</span>
            <span className="text-xs muted num">
              {(pool.required_credits ?? 0) > 0
                ? `${pool.counted_credits ?? 0}/${pool.required_credits ?? 0} credits`
                : `${pool.counted_courses ?? 0}/${pool.courses_required ?? 0} courses`}
            </span>
          </div>
          {(pool.matched_courses ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {(pool.matched_courses ?? []).map((course) => (
                <span key={course.code} className={`chip ${course.status === 'completed' ? 'chip-success' : ''}`}>{course.code}</span>
              ))}
            </div>
          )}
          {(pool.notes ?? []).map((note) => (
            <p key={note} className="text-xs muted">{note}</p>
          ))}
        </div>
      ))}
    </section>
  );
}

function MinorSuggestionsCard({ suggestions }: { suggestions: MinorSuggestion[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <section className="card card-pad stack-4" aria-labelledby="minor-suggestions-title">
      <header className="flex items-center gap-3">
        <span className="icon-tile" aria-hidden="true"><Lightbulb /></span>
        <div>
          <h2 id="minor-suggestions-title" className="section-title">Minors within reach</h2>
          <p className="section-subtitle">Minors your courses already count toward.</p>
        </div>
      </header>
      {suggestions.length === 0 ? (
        <p className="text-sm muted">No minor is close enough to suggest yet.</p>
      ) : (
        <div className="stack-2">
          {suggestions.map((suggestion) => {
            const needCount = Math.max(0, Number(suggestion.remaining_count ?? suggestion.remaining_courses.length ?? 0));
            const isOpen = expanded === suggestion.minor;
            return (
              <div key={suggestion.minor} className="elective-card">
                <button
                  type="button"
                  className="elective-card-toggle"
                  aria-expanded={isOpen}
                  onClick={() => setExpanded(isOpen ? null : suggestion.minor)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="elective-card-title">{suggestion.minor}</span>
                    <span className="flex items-center gap-2">
                      <span className="badge badge-gold num">
                        {needCount} course{needCount === 1 ? '' : 's'} to go
                      </span>
                      <ChevronDown className="elective-card-chevron" aria-hidden="true" />
                    </span>
                  </div>
                </button>
                {isOpen && (
                  <div className="elective-card-details stack-3">
                    <p className="text-sm">{suggestion.why}</p>
                    {suggestion.remaining_courses.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {suggestion.remaining_courses.slice(0, 6).map((course, index) => (
                          <span key={`${course}:${index}`} className="chip">{course}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

/** Everything the degree audit tracks, grouped by requirement type. */
export function RequirementsTab({
  electiveRequirements,
  progress,
  totalCredits,
  catalogYear,
  genEdNeeds,
  wic,
  concentrationAudit,
  minorSuggestions,
}: RequirementsTabProps) {
  const showConcentration = !!concentrationAudit?.selected && concentrationAudit.selected !== 'General';
  return (
    <div className="requirements-grid">
      <div className="stack-4">
        <ProgressDashboard progress={progress} totalCredits={totalCredits} catalogYear={catalogYear} />
        <ElectiveProgressCards requirements={electiveRequirements} />
        {showConcentration && concentrationAudit && <ConcentrationCard audit={concentrationAudit} />}
      </div>
      <div className="stack-4">
        <GenEdCard genEdNeeds={genEdNeeds} wic={wic} />
        <MinorSuggestionsCard suggestions={minorSuggestions} />
      </div>
    </div>
  );
}

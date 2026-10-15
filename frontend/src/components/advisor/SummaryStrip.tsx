import { CalendarRange, CheckCircle2, ListChecks, ListTodo, TriangleAlert } from 'lucide-react';

interface SummaryStripProps {
  completedCredits: number;
  /** This semester's courses, not earned yet. */
  inProgressCredits?: number;
  /** Completed plus planned credits; what the plan reaches at graduation. */
  projectedCredits: number;
  degreeCredits: number;
  remainingTerms: number;
  issueCount: number;
  onShowIssues: () => void;
  /** Programs whose electives the plan does not cover yet (the student picks them). */
  electivesToChoose: number;
  onShowElectives: () => void;
}

/** Four numbers a student checks first: progress, plan total, time left, problems. */
export function SummaryStrip({
  completedCredits,
  inProgressCredits = 0,
  projectedCredits,
  degreeCredits,
  remainingTerms,
  issueCount,
  onShowIssues,
  electivesToChoose,
  onShowElectives,
}: SummaryStripProps) {
  const percent = degreeCredits > 0 ? Math.min(100, Math.round((completedCredits / degreeCredits) * 100)) : 0;
  const planCovers = projectedCredits >= degreeCredits;

  return (
    <section className="summary-strip" aria-label="Plan summary">
      <div className="card stat">
        <span className="stat-label">Degree progress</span>
        <span className="stat-value num">{percent}%</span>
        <div className="progress" aria-hidden="true">
          <div className="progress-fill" style={{ width: `${percent}%` }} />
        </div>
        <span className="stat-hint num">
          {completedCredits} of {degreeCredits} credits earned{inProgressCredits ? `, ${inProgressCredits} in progress` : ''}
        </span>
      </div>

      <div className="card stat">
        <span className="stat-label">
          <ListChecks aria-hidden="true" />
          Credits in plan
        </span>
        <span className="stat-value num">{projectedCredits}</span>
        <span className={`stat-hint ${planCovers ? 'is-good' : ''}`}>
          {planCovers ? 'Reaches the degree total' : `${degreeCredits - projectedCredits} short of ${degreeCredits}`}
        </span>
      </div>

      <div className="card stat">
        <span className="stat-label">
          <CalendarRange aria-hidden="true" />
          Semesters left
        </span>
        <span className="stat-value num">{remainingTerms}</span>
        <span className="stat-hint">Including the current one</span>
      </div>

      {issueCount > 0 ? (
        <button type="button" className="card stat stat-button is-warning" onClick={onShowIssues}>
          <span className="stat-label">
            <TriangleAlert aria-hidden="true" />
            Needs attention
          </span>
          <span className="stat-value num">{issueCount}</span>
          <span className="stat-hint">Review in the plan</span>
        </button>
      ) : electivesToChoose > 0 ? (
        <button type="button" className="card stat stat-button" onClick={onShowElectives}>
          <span className="stat-label">
            <ListTodo aria-hidden="true" />
            Plan check
          </span>
          <span className="stat-value">Electives to choose</span>
          <span className="stat-hint">
            {electivesToChoose === 1 ? 'One program needs' : `${electivesToChoose} programs need`} more electives
          </span>
        </button>
      ) : (
        <div className="card stat is-good">
          <span className="stat-label">
            <CheckCircle2 aria-hidden="true" />
            Plan check
          </span>
          <span className="stat-value">All clear</span>
          <span className="stat-hint">Every requirement is covered</span>
        </div>
      )}
    </section>
  );
}

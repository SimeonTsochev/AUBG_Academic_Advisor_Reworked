import { Progress } from '../types';
import { BadgeCheck, TrendingUp } from 'lucide-react';

interface ProgressDashboardProps {
  progress: Progress[];
  totalCredits: { completed: number; total: number };
  catalogYear?: string | null;
}

const fillClass = (category: string) => {
  if (category.includes('Major')) return 'is-gold';
  return '';
};

const percentOf = (completed: number, total: number) =>
  total > 0 ? Math.min(100, Math.max(0, Math.round((completed / total) * 100))) : 0;

export function ProgressDashboard({ progress, totalCredits, catalogYear }: ProgressDashboardProps) {
  const overall = percentOf(totalCredits.completed, totalCredits.total);

  return (
    <section className="card card-pad stack-4" aria-labelledby="degree-progress-title">
      <header className="flex items-center gap-3">
        <span className="icon-tile" aria-hidden="true"><TrendingUp /></span>
        <div>
          <h2 id="degree-progress-title" className="section-title">Degree progress</h2>
          <p className="section-subtitle">Credits earned from completed courses and transfer credit.</p>
        </div>
      </header>

      <div className="progress-overall stack-2">
        <div className="flex items-center justify-between gap-3">
          <span className="font-semibold">Overall</span>
          <span className="num progress-overall-value">
            {totalCredits.completed}<span className="muted">/{totalCredits.total}</span>
          </span>
        </div>
        <div className="progress" aria-hidden="true">
          <div className="progress-fill" style={{ width: `${overall}%` }} />
        </div>
        <span className="text-sm muted num">{Math.max(0, totalCredits.total - totalCredits.completed)} credits remaining</span>
      </div>

      <ul className="progress-list">
        {progress.map((item) => (
          <li key={item.category} className="stack-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">{item.category}</span>
              <span className="muted num">{item.completed}/{item.total}</span>
            </div>
            <div
              className="progress"
              role="progressbar"
              aria-label={item.category}
              aria-valuemin={0}
              aria-valuemax={item.total}
              aria-valuenow={item.completed}
            >
              <div className={`progress-fill ${fillClass(item.category)}`} style={{ width: `${percentOf(item.completed, item.total)}%` }} />
            </div>
          </li>
        ))}
      </ul>

      <p className="flex items-center gap-2 text-xs muted">
        <BadgeCheck aria-hidden="true" className="requirement-icon" />
        Checked against the {catalogYear ? `AY ${catalogYear}` : 'AY 2025-26'} AUBG academic catalog.
      </p>
    </section>
  );
}

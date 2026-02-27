import { Progress } from '../types';
import { CheckCircle2, Circle, Clock } from 'lucide-react';

interface ProgressDashboardProps {
  progress: Progress[];
  totalCredits: { completed: number; total: number };
  catalogYear?: string | null;
}

export function ProgressDashboard({ progress, totalCredits, catalogYear }: ProgressDashboardProps) {
  const overallProgress = (totalCredits.completed / totalCredits.total) * 100;

  const getProgressColor = (category: string) => {
    if (category === 'Overall') return 'var(--navy-blue)';
    if (category.includes('Major')) return 'var(--academic-gold)';
    if (category.includes('Minor')) return 'var(--in-progress)';
    return 'var(--neutral-dark)';
  };

  return (
    <div className="h-full overflow-y-auto p-6" style={{ backgroundColor: 'var(--white)' }}>
      <div className="mb-8">
        <h3 className="mb-6">Degree Progress</h3>

        {/* Overall Progress */}
        <div className="mb-8 p-5 rounded-xl" style={{ backgroundColor: 'var(--neutral-gray)' }}>
          <div className="flex justify-between items-baseline mb-3">
            <h4>Overall Progress</h4>
            <span style={{ fontSize: '1.5rem', color: 'var(--navy-blue)' }}>
              {totalCredits.completed}/{totalCredits.total}
            </span>
          </div>
          <div className="mb-2 h-3 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--remaining)' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${overallProgress}%`,
                backgroundColor: 'var(--navy-blue)'
              }}
            />
          </div>
          <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
            {totalCredits.total - totalCredits.completed} credits remaining
          </p>
        </div>

        {/* Individual Progress Sections */}
        <div className="space-y-6">
          {progress.map((item, index) => {
            const pct = Math.min(100, Math.max(0, (item.completed / item.total) * 100));
            const color = getProgressColor(item.category);
            return (
              <div key={index}>
                <div className="flex justify-between items-baseline mb-2">
                  <h4 className="text-sm">{item.category}</h4>
                  <span className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                    {item.completed}/{item.total}
                  </span>
                </div>
                <div className="mb-1 h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--remaining)' }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: color
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="pt-6 border-t" style={{ borderColor: 'var(--neutral-border)' }}>
        <p className="text-sm mb-3" style={{ fontWeight: 600 }}>Status Legend</p>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--completed)' }} />
            <span>Completed</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Clock className="w-4 h-4" style={{ color: 'var(--in-progress)' }} />
            <span>In Progress</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Circle className="w-4 h-4" style={{ color: 'var(--neutral-dark)' }} />
            <span>Remaining</span>
          </div>
        </div>
      </div>

      {/* Trust Badge */}
      <div className="mt-8 p-4 rounded-lg border" style={{ borderColor: 'var(--neutral-border)', backgroundColor: 'var(--neutral-gray)' }}>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--academic-gold)' }}>
            <CheckCircle2 className="w-5 h-5" style={{ color: 'var(--white)' }} />
          </div>
          <div>
            <p style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.25rem' }}>
              Catalog-Verified Degree Plan
            </p>
            <p style={{ fontSize: '0.75rem', color: 'var(--neutral-dark)' }}>
              Based on {catalogYear ? `AY ${catalogYear}` : 'AY 2025-26'} Academic Catalog
            </p>
            <p style={{ fontSize: '0.75rem', color: 'var(--neutral-dark)', marginTop: '0.5rem' }}>
              This plan follows official AUBG academic rules.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

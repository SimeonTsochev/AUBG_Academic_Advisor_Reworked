import { forwardRef, useState } from 'react';
import { TriangleAlert } from 'lucide-react';

const COLLAPSED_COUNT = 3;

interface PlanAlertsProps {
  errors: string[];
}

/** "Plan needs attention": every validation error as its own line, long lists collapsed. */
export const PlanAlerts = forwardRef<HTMLDivElement, PlanAlertsProps>(function PlanAlerts({ errors }, ref) {
  const [showAll, setShowAll] = useState(false);
  if (errors.length === 0) return null;
  const visible = showAll ? errors : errors.slice(0, COLLAPSED_COUNT);

  return (
    <div ref={ref} className="alert alert-warning" role="status" tabIndex={-1}>
      <TriangleAlert aria-hidden="true" />
      <div className="min-w-0">
        <p className="alert-title">Plan needs attention</p>
        <ul>
          {visible.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
        {errors.length > COLLAPSED_COUNT && (
          <button type="button" className="btn btn-ghost btn-sm alert-more" onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show fewer' : `Show ${errors.length - COLLAPSED_COUNT} more`}
          </button>
        )}
        <p className="alert-note">You can keep editing; the plan just may not meet every graduation rule yet.</p>
      </div>
    </div>
  );
});

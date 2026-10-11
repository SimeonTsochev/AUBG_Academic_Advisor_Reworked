import type { PlacementWaiver } from '../../api';

interface PlacementTestsCardProps {
  /** Placement tests the selected programs offer (C++ COS 1020, C# INF 1030, the MLC languages). */
  tests: PlacementWaiver[];
  /** Courses the student says a placement test waived. */
  waived: string[];
  onToggle: (course: string) => void;
}

export function PlacementTestsCard({ tests, waived, onToggle }: PlacementTestsCardProps) {
  if (tests.length === 0) return null;
  return (
    <div className="card card-pad setup-card">
      <h2 className="section-title">Placement tests</h2>
      <p className="section-subtitle setup-card-intro">
        Passing a placement test waives the course; you take another elective instead.
      </p>
      <div className="grid-auto">
        {tests.map((test) => (
          <label key={test.course} className="select-tile">
            <input
              type="checkbox"
              checked={waived.includes(test.course)}
              onChange={() => onToggle(test.course)}
            />
            <span>{test.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

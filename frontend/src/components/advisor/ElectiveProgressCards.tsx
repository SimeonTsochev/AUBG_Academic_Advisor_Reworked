import { useState } from 'react';
import { BookOpen, CheckCircle2, ChevronDown } from 'lucide-react';
import { describeElectiveRemaining, type ElectiveRequirementSummary } from '../../utils/electiveProgress';

const LISTED_COURSES_SHOWN = 18;

interface ElectiveProgressCardsProps {
  requirements: ElectiveRequirementSummary[];
}

/** Elective credits per program, counted by the backend from completed and planned courses. */
export function ElectiveProgressCards({ requirements }: ElectiveProgressCardsProps) {
  const [expanded, setExpanded] = useState<string | null>(null);
  if (requirements.length === 0) return null;

  return (
    <section className="card card-pad stack-4" aria-labelledby="elective-requirements-title">
      <header className="flex items-center gap-3">
        <span className="icon-tile" aria-hidden="true">
          <BookOpen />
        </span>
        <div>
          <h2 id="elective-requirements-title" className="section-title">Elective requirements</h2>
          <p className="section-subtitle">Courses in your plan count automatically as you add them.</p>
        </div>
      </header>

      <div className="stack-3">
        {requirements.map((requirement) => {
          const isOpen = expanded === requirement.key;
          const percent = requirement.required > 0
            ? Math.min(100, Math.round((requirement.counted / requirement.required) * 100))
            : 0;
          const panelId = `elective-${requirement.key.replace(/[^a-z0-9]+/gi, '-')}`;
          return (
            <div key={requirement.key} className="elective-card">
              <button
                type="button"
                className="elective-card-toggle"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => setExpanded(isOpen ? null : requirement.key)}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="elective-card-title">{requirement.label}</span>
                  <span className="flex items-center gap-2">
                    {requirement.isComplete ? (
                      <span className="badge badge-success">
                        <CheckCircle2 aria-hidden="true" />
                        Completed
                      </span>
                    ) : (
                      <span className="badge badge-warning num">{describeElectiveRemaining(requirement)}</span>
                    )}
                    <ChevronDown className="elective-card-chevron" aria-hidden="true" />
                  </span>
                </div>
                <div className="progress" aria-hidden="true">
                  <div
                    className={`progress-fill ${requirement.isComplete ? 'is-success' : 'is-gold'}`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
                <span className="text-sm muted num">
                  {requirement.counted} of {requirement.required} {requirement.unit}
                </span>
              </button>

              {requirement.courses.length > 0 && (
                <div className="flex flex-wrap gap-2 elective-card-courses">
                  {requirement.courses.map((course) => (
                    <span
                      key={course.code}
                      className={`chip ${course.completed ? 'chip-success' : ''}`}
                      title={course.completed ? 'Completed' : 'Planned'}
                    >
                      {course.code}
                      <span className="num muted">{course.credits} cr</span>
                    </span>
                  ))}
                </div>
              )}

              {isOpen && (
                <div id={panelId} className="elective-card-details stack-3">
                  {requirement.allowedCourses.length > 0 && (
                    <div className="stack-2">
                      <span className="text-xs font-semibold muted">Listed courses</span>
                      <div className="flex flex-wrap gap-1">
                        {requirement.allowedCourses.slice(0, LISTED_COURSES_SHOWN).map((code) => (
                          <span key={code} className="badge badge-gold">{code}</span>
                        ))}
                        {requirement.allowedCourses.length > LISTED_COURSES_SHOWN && (
                          <span className="text-xs muted">
                            +{requirement.allowedCourses.length - LISTED_COURSES_SHOWN} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  {requirement.ruleText && <p className="text-sm muted">{requirement.ruleText}</p>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

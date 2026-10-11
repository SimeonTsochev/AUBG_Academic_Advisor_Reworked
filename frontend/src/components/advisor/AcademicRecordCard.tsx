import { useState } from 'react';
import { Award, CircleAlert } from 'lucide-react';
import type { AcademicRecord } from '../../api';
import { formatGpa, GRADE_CHOICES, type GradeMap } from '../../utils/grades';

function GradeSelect({ code, value, onChange }: { code: string; value: string; onChange: (grade: string | null) => void }) {
  return (
    <select
      className="input setup-number"
      aria-label={`Grade for ${code}`}
      value={value}
      onChange={(event) => onChange(event.target.value || null)}
    >
      <option value="">No grade</option>
      {GRADE_CHOICES.map((grade) => <option key={grade} value={grade}>{grade}</option>)}
    </select>
  );
}

const MAJOR_GPA_MINIMUM = 2.5;

interface AcademicRecordCardProps {
  record: AcademicRecord | null;
  grades: GradeMap;
  onSetGrade: (code: string, grade: string | null) => void;
}

/** GPA, GPA in each major, Latin honors outlook and Dean's List terms (catalog pp.59-60). */
export function AcademicRecordCard({ record, grades, onSetGrade }: AcademicRecordCardProps) {
  const [editing, setEditing] = useState(false);
  const ungraded = record?.ungraded_courses ?? [];
  return (
    <section className="card card-pad stack-4" aria-labelledby="academic-record-title">
      <header className="flex items-center gap-3">
        <span className="icon-tile" aria-hidden="true"><Award /></span>
        <div>
          <h2 id="academic-record-title" className="section-title">GPA and honors</h2>
          <p className="section-subtitle">From your transcript grades; retakes replace the earlier grade.</p>
        </div>
      </header>

      {!record?.has_grades ? (
        <p className="text-sm muted">Import your transcript in setup to see your GPA and honors outlook.</p>
      ) : (
        <>
          <ul className="requirement-list">
            <li>
              <span>Cumulative GPA <span className="muted num">({record.attempted_credits} graded credits)</span></span>
              <span className={`badge num ${record.gpa !== null && record.gpa < 2 ? 'badge-warning' : 'badge-info'}`}>
                {formatGpa(record.gpa)}
              </span>
            </li>
            {record.majors.map((major) => (
              <li key={major.major}>
                <span>GPA in {major.major} <span className="muted num">({major.credits} credits)</span></span>
                <span
                  className={`badge num ${major.gpa !== null && major.gpa < MAJOR_GPA_MINIMUM ? 'badge-warning' : 'badge-info'}`}
                  title={`Graduation needs ${MAJOR_GPA_MINIMUM.toFixed(3)} in the major`}
                >
                  {formatGpa(major.gpa)}
                </span>
              </li>
            ))}
            <li>
              <span>Course load</span>
              <span className="text-sm muted">
                {record.max_load > 17 ? `Up to ${record.max_load} credits (GPA 3.300+)` : 'Up to 17 credits'}
              </span>
            </li>
          </ul>

          <div className="stack-2">
            <span className="text-xs font-semibold muted">Latin honors</span>
            <p className="text-sm">
              {record.honors.current ? <>On track for <b>{record.honors.current}</b>. </> : null}
              {record.honors.next && (
                record.honors.next.reachable && record.honors.next.needed_average !== null
                  ? <>
                      {record.honors.next.name} ({record.honors.next.min_gpa.toFixed(3)}) needs an average of{' '}
                      <b className="num">{record.honors.next.needed_average.toFixed(2)}</b> over your remaining{' '}
                      <span className="num">{record.remaining_credits}</span> credits.
                    </>
                  : <>{record.honors.next.name} ({record.honors.next.min_gpa.toFixed(3)}) is out of reach with the credits left.</>
              )}
            </p>
          </div>

          {(record.presidents_list || record.terms.some((term) => term.deans_list)) && (
            <div className="flex flex-wrap gap-1">
              {record.presidents_list && <span className="badge badge-gold">President's List</span>}
              {record.terms.filter((term) => term.deans_list).map((term) => (
                <span key={term.term} className="badge badge-success">Dean's List · {term.term}</span>
              ))}
            </div>
          )}

          {ungraded.length > 0 && (
            <div className="alert alert-warning stack-2" role="status">
              <CircleAlert aria-hidden="true" />
              <div className="min-w-0 stack-2">
                <p className="alert-title">Completed without a grade</p>
                <p className="text-sm">The transcript import found no grade for these, so the GPA leaves them out. Add them:</p>
                <ul className="requirement-list">
                  {ungraded.map((code) => (
                    <li key={code}>
                      <span className="font-semibold">{code}</span>
                      <GradeSelect code={code} value="" onChange={(grade) => onSetGrade(code, grade)} />
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {Object.keys(grades).length > 0 && (
            <div className="stack-2">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing((v) => !v)} aria-expanded={editing}>
                {editing ? 'Done editing grades' : 'Edit grades'}
              </button>
              {editing && (
                <ul className="requirement-list">
                  {Object.entries(grades).sort(([a], [b]) => a.localeCompare(b)).map(([code, entry]) => (
                    <li key={code}>
                      <span><span className="font-semibold">{code}</span>{entry.term ? <span className="muted"> · {entry.term}</span> : null}</span>
                      <GradeSelect code={code} value={entry.grade} onChange={(grade) => onSetGrade(code, grade)} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <p className="text-xs muted">Your grades stay on this device: they are not saved in your share link.</p>
        </>
      )}
    </section>
  );
}

import { Award } from 'lucide-react';
import type { AcademicRecord } from '../../api';
import { formatGpa } from '../../utils/grades';

const MAJOR_GPA_MINIMUM = 2.5;

/** GPA, GPA in each major, Latin honors outlook and Dean's List terms (catalog pp.59-60). */
export function AcademicRecordCard({ record }: { record: AcademicRecord | null }) {
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

          <p className="text-xs muted">Your grades stay on this device: they are not saved in your share link.</p>
        </>
      )}
    </section>
  );
}

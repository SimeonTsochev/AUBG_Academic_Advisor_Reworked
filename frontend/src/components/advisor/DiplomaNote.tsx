import { Info } from 'lucide-react';

interface DiplomaNoteProps {
  majors: string[];
  /** Majors that lead to a US and a Bulgarian diploma. */
  dualDiplomaMajors: string[];
}

/**
 * Every student needs at least one dual-diploma major to graduate (catalog p.72). A note rather than a
 * plan error: a student planning a single-diploma major often has not added the second major yet.
 */
export function DiplomaNote({ majors, dualDiplomaMajors }: DiplomaNoteProps) {
  const subject = majors.length === 1 ? `${majors[0]} gives` : 'Your majors give';
  const options = dualDiplomaMajors.length > 1
    ? `${dualDiplomaMajors.slice(0, -1).join(', ')} or ${dualDiplomaMajors[dualDiplomaMajors.length - 1]}`
    : dualDiplomaMajors.join('');
  return (
    <div className="alert alert-info" role="status">
      <Info aria-hidden="true" />
      <p>
        {subject} a US diploma only. To graduate you also need a dual-diploma major (US and Bulgarian
        diploma){options ? `: ${options}` : ''} (catalog p.72).
      </p>
    </div>
  );
}

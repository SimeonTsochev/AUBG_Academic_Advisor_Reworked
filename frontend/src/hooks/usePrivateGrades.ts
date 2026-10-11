import { useEffect, useRef, useState } from 'react';
import { loadGrades, saveGrades, type GradeMap } from '../utils/grades';

/**
 * Transcript grades for GPA. Private: stored in this browser under the plan's share token and sent
 * with plan requests, but never part of the snapshot payload, so a shared link does not reveal them.
 * Setup's grades win; a restored plan reads the grades this browser stored under its token. Every
 * saved edit gets a new token, so the grades move to the newest one.
 */
export function usePrivateGrades(
  initialGrades: GradeMap | undefined,
  initialToken: string | null,
  currentToken: string | null,
) {
  const [grades, setGrades] = useState<GradeMap>(() =>
    initialGrades && Object.keys(initialGrades).length > 0 ? initialGrades : loadGrades(initialToken),
  );
  const storedTokenRef = useRef<string | null>(initialToken);

  useEffect(() => {
    if (!currentToken) return;
    saveGrades(currentToken, grades, storedTokenRef.current);
    storedTokenRef.current = currentToken;
  }, [currentToken, grades]);

  return [grades, setGrades] as const;
}

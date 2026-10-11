import { Languages } from 'lucide-react';
import type { ProgramInfo } from '../../api';

interface ProgramOptionPromptProps {
  /** Majors whose required option has no choice yet, e.g. a European Studies plan saved without a language. */
  majors: string[];
  programInfo: Record<string, ProgramInfo>;
  onChoose: (major: string, choice: string) => void;
}

/** Lets a saved plan pick a required major option in place, without redoing setup. */
export function ProgramOptionPrompt({ majors, programInfo, onChoose }: ProgramOptionPromptProps) {
  if (majors.length === 0) return null;
  return (
    <>
      {majors.map((major) => {
        const options = programInfo[major]?.options;
        if (!options) return null;
        const id = `program-option-${major.replace(/\W+/g, '-').toLowerCase()}`;
        return (
          <div key={major} className="alert alert-info" role="status">
            <Languages aria-hidden="true" />
            <div className="min-w-0 stack-2">
              <label className="alert-title" htmlFor={id}>{major}: choose your {options.label.toLowerCase()}</label>
              {options.description && <p>{options.description}</p>}
              <select
                id={id}
                className="input"
                defaultValue=""
                onChange={(event) => event.target.value && onChoose(major, event.target.value)}
              >
                <option value="" disabled>Choose…</option>
                {options.choices.map((choice) => (
                  <option key={choice} value={choice}>{choice}</option>
                ))}
              </select>
            </div>
          </div>
        );
      })}
    </>
  );
}

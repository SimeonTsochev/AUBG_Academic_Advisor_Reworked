import type { ProgramOptions } from '../../api';

interface ProgramOptionCardProps {
  program: string;
  kind: 'major' | 'minor';
  /** The program's options; no card when it offers none. */
  options: ProgramOptions | null | undefined;
  chosen: string[];
  onToggle: (choice: string, multiple: boolean) => void;
}

/** A program's options on the setup screen: CS/IS concentrations, a European Studies or MLC language. */
export function ProgramOptionCard({ program, kind, options, chosen, onToggle }: ProgramOptionCardProps) {
  if (!options) return null;
  return (
    <div className="card card-pad setup-card">
      <h2 className="section-title">{program} {kind}: {options.label}</h2>
      <p className="section-subtitle setup-card-intro">
        {options.required
          ? 'Required: choose one.'
          : options.multiple ? 'Optional: choose any you want to declare.' : 'Optional.'}
      </p>
      <div className="grid-auto">
        {options.choices.map((choice) => (
          <label key={choice} className="select-tile">
            <input
              type={options.multiple ? 'checkbox' : 'radio'}
              name={`program-option-${kind}-${program}`}
              checked={chosen.includes(choice)}
              onChange={() => onToggle(choice, options.multiple)}
            />
            <span>{choice}</span>
          </label>
        ))}
      </div>
      {options.description && <div className="text-xs mt-3 muted">{options.description}</div>}
    </div>
  );
}

import { ElectiveSuggestion } from '../types';
import { Award, Info } from 'lucide-react';
import { useState } from 'react';

interface ElectiveRecommendationPanelProps {
  electives: ElectiveSuggestion[];
  onAdd?: (code: string) => void;
  existingCodes?: Set<string>;
}

export function ElectiveRecommendationPanel({ electives, onAdd, existingCodes }: ElectiveRecommendationPanelProps) {
  const [showTooltip, setShowTooltip] = useState<string | null>(null);

  return (
    <div className="rounded-xl p-6 shadow-sm" style={{ backgroundcolor: '#EAF4FF' }}>
      <div className="flex items-center gap-3 mb-5">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: 'var(--academic-gold)' }}
        >
          <Award className="w-5 h-5" style={{ color: 'var(--white)' }} />
        </div>
        <div>
          <h4>Recommended Electives</h4>
          <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
            Optimized for your degree requirements
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {electives.map((elective, index) => (
          <div
            key={elective.code}
            className="p-4 rounded-lg border-2 transition-all hover:shadow-md cursor-pointer relative"
            style={{
              borderColor: 'var(--neutral-border)',
              backgroundColor: 'var(--neutral-gray)'
            }}
            onMouseEnter={() => setShowTooltip(elective.code)}
            onMouseLeave={() => setShowTooltip(null)}
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex-1">
                <div className="flex items-baseline gap-2 mb-1">
                  <span style={{ fontWeight: 600, color: 'var(--navy-dark)' }}>
                    {elective.code}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--academic-gold)', color: 'var(--white)' }}>
                    Rank #{index + 1}
                  </span>
                </div>
                <p className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
                  {elective.name}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
                  {elective.credits} cr
                </span>
                {onAdd && (
                  <button
                    type="button"
                    onClick={() => onAdd(elective.code)}
                    disabled={existingCodes?.has(elective.code)}
                    className="text-xs px-2 py-1 rounded border"
                    style={{
                      borderColor: 'var(--neutral-border)',
                      color: 'var(--navy-dark)',
                      background: existingCodes?.has(elective.code) ? 'var(--neutral-gray)' : 'var(--white)',
                      cursor: existingCodes?.has(elective.code) ? 'not-allowed' : 'pointer',
                      opacity: existingCodes?.has(elective.code) ? 0.6 : 1
                    }}
                    title={existingCodes?.has(elective.code) ? 'Already in plan' : 'Add to plan'}
                  >
                    {existingCodes?.has(elective.code) ? 'In plan' : 'Add'}
                  </button>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <span
                className="text-sm px-2 py-1 rounded"
                style={{
                  backgroundColor: 'var(--navy-blue)',
                  color: 'var(--white)',
                  fontWeight: 500
                }}
              >
                Requirements satisfied: {elective.requirementsSatisfied}
              </span>
            </div>

            <div className="flex flex-wrap gap-2">
              {elective.tags.map((tag, i) => {
                const normalized = tag.toLowerCase();
                const isWic = normalized.includes('writing intensive');
                const isGenEd = normalized.includes('gen ed');
                const background = isWic
                  ? 'var(--navy-blue)'
                  : isGenEd
                    ? 'var(--academic-gold)'
                    : 'var(--white)';
                const color = isWic ? 'var(--white)' : 'var(--neutral-dark)';
                return (
                  <span
                    key={i}
                    className="px-2 py-1 rounded text-xs"
                    style={{
                      backgroundColor: background,
                      color,
                      border: background === 'var(--white)' ? '1px solid var(--neutral-border)' : 'none'
                    }}
                  >
                    {tag}
                  </span>
                );
              })}
            </div>

            {/* Explanation Tooltip */}
            {showTooltip === elective.code && (
              <div
                className="absolute left-0 top-full mt-2 p-3 rounded-lg shadow-lg z-20"
                style={{
                  backgroundColor: 'var(--navy-dark)',
                  color: 'var(--white)',
                  width: '100%',
                  maxWidth: '320px'
                }}
              >
                <div className="flex items-start gap-2">
                  <Info className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#EAF4FF' }} />
                  <p style={{ fontSize: '0.875rem', color: '#EAF4FF' }}>{elective.explanation}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

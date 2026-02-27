import { MinorSuggestion } from '../types';
import { AlertCircle, Plus, X } from 'lucide-react';

interface MinorDetectionAlertProps {
  suggestion: MinorSuggestion;
  onAddMinor: () => void;
  onIgnore: () => void;
}

export function MinorDetectionAlert({ suggestion, onAddMinor, onIgnore }: MinorDetectionAlertProps) {
  return (
    <div
      className="rounded-xl p-6 shadow-lg border-2"
      style={{
        backgroundColor: 'var(--white)',
        borderColor: 'var(--academic-gold)'
      }}
    >
      <div className="flex items-start gap-4">
        <div
          className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
          style={{ backgroundColor: 'var(--academic-gold)' }}
        >
          <AlertCircle className="w-6 h-6" style={{ color: 'var(--white)' }} />
        </div>

        <div className="flex-1">
          <h4 className="mb-2">
            You are {suggestion.coursesNeeded} course{suggestion.coursesNeeded !== 1 ? 's' : ''} away from completing a Minor in {suggestion.minorName}
          </h4>
          
          <div className="mb-4">
            <p className="text-sm mb-2" style={{ fontWeight: 600, color: 'var(--neutral-dark)' }}>
              Remaining Required Courses:
            </p>
            <ul className="space-y-1">
              {suggestion.remainingCourses.map((course, index) => (
                <li
                  key={index}
                  className="text-sm pl-4"
                  style={{
                    color: 'var(--neutral-dark)',
                    position: 'relative'
                  }}
                >
                  <span
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '0.5em',
                      width: '4px',
                      height: '4px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--academic-gold)'
                    }}
                  />
                  {course}
                </li>
              ))}
            </ul>
          </div>

          <div className="mb-4 p-3 rounded-lg" style={{ backgroundColor: 'var(--neutral-gray)' }}>
            <p className="text-sm" style={{ color: 'var(--neutral-dark)' }}>
              <span style={{ fontWeight: 600 }}>Credit Impact:</span> +{suggestion.creditImpact} additional credits
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={onAddMinor}
              className="px-5 py-2.5 rounded-lg flex items-center gap-2 transition-all hover:shadow-md"
              style={{
                backgroundColor: 'var(--navy-blue)',
                color: 'var(--white)'
              }}
            >
              <Plus className="w-4 h-4" />
              Add Minor to My Plan
            </button>
            <button
              onClick={onIgnore}
              className="px-5 py-2.5 rounded-lg flex items-center gap-2 transition-all border-2"
              style={{
                backgroundColor: 'var(--white)',
                color: 'var(--neutral-dark)',
                borderColor: 'var(--neutral-border)'
              }}
            >
              <X className="w-4 h-4" />
              Ignore for Now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

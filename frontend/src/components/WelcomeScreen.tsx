import { GraduationCap, ArrowRight, BookOpen, CheckCircle2, TriangleAlert } from 'lucide-react';

interface WelcomeScreenProps {
  onStart: () => void;
  onHowItWorks: () => void;
  isLoading?: boolean;
  errorMsg?: string;
}

const FEATURES = [
  'Checked against the AUBG academic catalog',
  'Double majors, minors and concentrations',
  'Transcript import with automatic retakes',
];

export function WelcomeScreen({ onStart, onHowItWorks, isLoading, errorMsg }: WelcomeScreenProps) {
  return (
    <div className="welcome-screen">
      <main className="welcome-hero">
        <span className="welcome-mark" aria-hidden="true">
          <GraduationCap />
        </span>

        <h1 className="welcome-title">AUBG Academic Co-Advisor</h1>
        <p className="welcome-tagline">
          Build a semester-by-semester degree plan, see what is left for every major and minor, and graduate on time.
        </p>

        <div className="welcome-actions">
          <button type="button" onClick={onStart} disabled={isLoading} className="btn btn-primary btn-lg btn-forward">
            {isLoading ? (
              <>
                <span className="btn-spinner" aria-hidden="true" />
                <span>Loading catalog…</span>
              </>
            ) : (
              <>
                <span>Start degree plan</span>
                <ArrowRight aria-hidden="true" />
              </>
            )}
          </button>
          <button type="button" onClick={onHowItWorks} className="btn btn-outline btn-lg">
            <BookOpen aria-hidden="true" />
            <span>How it works</span>
          </button>
        </div>

        {errorMsg && (
          <div className="alert alert-danger welcome-error" role="alert">
            <TriangleAlert aria-hidden="true" />
            <p>{errorMsg}</p>
          </div>
        )}

        <ul className="welcome-features">
          {FEATURES.map((feature) => (
            <li key={feature}>
              <CheckCircle2 aria-hidden="true" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

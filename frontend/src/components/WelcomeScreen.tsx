import { GraduationCap, ArrowRight, BookOpen } from 'lucide-react';

interface WelcomeScreenProps {
  onStart: () => void;
  onHowItWorks: () => void;
  isLoading?: boolean;
  errorMsg?: string;
}

export function WelcomeScreen({ onStart, onHowItWorks, isLoading, errorMsg }: WelcomeScreenProps) {
  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="max-w-2xl w-full text-center">
        <div className="flex justify-center mb-8">
          <div className="w-20 h-20 rounded-full flex items-center justify-center" style={{ backgroundColor: 'var(--navy-blue)' }}>
            <GraduationCap className="w-12 h-12" style={{ color: 'var(--academic-gold)' }} />
          </div>
        </div>

        <h1 className="mb-4">AUBG Academic Co-Advisor</h1>

        <p className="mb-12 max-w-lg mx-auto" style={{ fontSize: '1.125rem' }}>
          Plan your degree. Optimize your majors. Graduate on time.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <button
            onClick={onStart}
            disabled={isLoading}
            className="px-8 py-4 rounded-lg flex items-center justify-center gap-2 transition-all hover:shadow-lg cursor-pointer disabled:cursor-not-allowed disabled:opacity-90"
            style={{
              backgroundColor: 'var(--navy-blue)',
              color: 'var(--white)'
            }}
          >
            {isLoading ? (
              <>
                <span
                  className="inline-block w-4 h-4 rounded-full border-2 border-white/40 border-t-white animate-spin"
                  aria-hidden="true"
                />
                <span>Loading catalog...</span>
                <span className="w-5 h-5" aria-hidden="true" />
              </>
            ) : (
              <>
                <span>Start Degree Plan</span>
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </button>

          <button
            onClick={onHowItWorks}
            className="px-8 py-4 rounded-lg flex items-center justify-center gap-2 transition-all border-2 cursor-pointer"
            style={{
              backgroundColor: 'var(--white)',
              color: 'var(--navy-blue)',
              borderColor: 'var(--neutral-border)'
            }}
          >
            <BookOpen className="w-5 h-5" />
            How It Works
          </button>
        </div>

        {errorMsg && (
          <p className="mt-4 text-sm" style={{ color: '#ef4444' }}>
            {errorMsg}
          </p>
        )}

        <div className="mt-16 pt-8 border-t" style={{ borderColor: 'var(--neutral-border)' }}>
          <div className="flex flex-wrap justify-center gap-8 text-center">
            <div>
              <div className="mb-2" style={{ fontSize: '2rem', color: 'var(--academic-gold)' }}>&#10003;</div>
              <p className="text-sm">Catalog-Verified Plans</p>
            </div>
            <div>
              <div className="mb-2" style={{ fontSize: '2rem', color: 'var(--academic-gold)' }}>&#10003;</div>
              <p className="text-sm">Multiple Majors Support</p>
            </div>
            <div>
              <div className="mb-2" style={{ fontSize: '2rem', color: 'var(--academic-gold)' }}>&#10003;</div>
              <p className="text-sm">Smart Minor Detection</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

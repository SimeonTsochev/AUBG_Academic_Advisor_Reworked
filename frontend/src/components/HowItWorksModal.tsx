import { useEffect } from 'react';
import { X, CheckCircle2, Calendar, Award } from 'lucide-react';

interface HowItWorksModalProps {
  onClose: () => void;
  /** "Get Started": close and open the setup screen. */
  onGetStarted: () => void;
}

export function HowItWorksModal({ onClose, onGetStarted }: HowItWorksModalProps) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-6 z-50"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
      onClick={onClose}
    >
      <div
        className="max-w-3xl w-full rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto"
        style={{ backgroundColor: 'var(--white)' }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="how-it-works-title"
      >
        <div className="p-8">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <h2 id="how-it-works-title">How It Works</h2>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-ghost btn-icon"
              aria-label="Close"
              autoFocus
            >
              <X className="w-6 h-6" aria-hidden="true" />
            </button>
          </div>

          {/* Steps */}
          <div className="space-y-8">
            <div className="flex gap-4">
              <div
                className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
                style={{ backgroundColor: 'var(--navy-blue)' }}
              >
                <span style={{ color: 'var(--white)' }}>1</span>
              </div>
              <div>
                <h3 className="mb-2">Tell Us Your Goals</h3>
                <p style={{ color: 'var(--neutral-dark)' }}>
                  Select your major(s), minor(s), and catalog year. Our system supports multiple majors and will optimize your course schedule accordingly.
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div
                className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
                style={{ backgroundColor: 'var(--navy-blue)' }}
              >
                <Calendar className="w-6 h-6" style={{ color: 'var(--white)' }} />
              </div>
              <div>
                <h3 className="mb-2">Get Your Personalized Plan</h3>
                <p style={{ color: 'var(--neutral-dark)' }}>
                  We generate a complete semester-by-semester plan that accounts for prerequisites, course availability, and optimal credit distribution. Every plan is verified against the official AUBG academic catalog.
                </p>
              </div>
            </div>

            <div className="flex gap-4">
              <div
                className="flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center"
                style={{ backgroundColor: 'var(--navy-blue)' }}
              >
                <Award className="w-6 h-6" style={{ color: 'var(--white)' }} />
              </div>
              <div>
                <h3 className="mb-2">Discover Opportunities</h3>
                <p style={{ color: 'var(--neutral-dark)' }}>
                  We'll alert you to smart opportunities like completing additional minors with minimal extra credits, and recommend electives that satisfy multiple requirements.
                </p>
              </div>
            </div>
          </div>

          {/* Features */}
          <div className="mt-8 p-6 rounded-lg" style={{ backgroundColor: 'var(--neutral-gray)' }}>
            <h4 className="mb-4">Key Features</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--completed)' }} />
                <span className="text-sm">Catalog-verified degree plans</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--completed)' }} />
                <span className="text-sm">Multiple major support</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--completed)' }} />
                <span className="text-sm">Smart minor detection</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--completed)' }} />
                <span className="text-sm">Prerequisite tracking</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--completed)' }} />
                <span className="text-sm">Elective recommendations</span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" style={{ color: 'var(--completed)' }} />
                <span className="text-sm">Transcript import</span>
              </div>
            </div>
          </div>

          {/* CTA */}
          <button
            type="button"
            onClick={onGetStarted}
            className="btn btn-primary btn-lg btn-block mt-6"
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
}

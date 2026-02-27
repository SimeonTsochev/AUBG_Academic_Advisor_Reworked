import { X, CheckCircle2, MessageSquare, Calendar, Award } from 'lucide-react';

interface HowItWorksModalProps {
  onClose: () => void;
}

export function HowItWorksModal({ onClose }: HowItWorksModalProps) {
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
      >
        <div className="p-8">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <h2>How It Works</h2>
            <button
              onClick={onClose}
              className="p-2 rounded-lg transition-all hover:bg-gray-100"
              style={{ color: 'var(--neutral-dark)' }}
            >
              <X className="w-6 h-6" />
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
                <MessageSquare className="w-6 h-6" style={{ color: 'var(--white)' }} />
              </div>
              <div>
                <h3 className="mb-2">Chat with Your Advisor</h3>
                <p style={{ color: 'var(--neutral-dark)' }}>
                  Ask questions about your plan, explore "what-if" scenarios, and get instant explanations for course recommendations. Our AI advisor understands AUBG's academic rules and can help you make informed decisions.
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
                <span className="text-sm">Real-time chat support</span>
              </div>
            </div>
          </div>

          {/* CTA */}
          <button
            onClick={onClose}
            className="w-full mt-6 px-6 py-4 rounded-lg transition-all hover:shadow-lg"
            style={{
              backgroundColor: 'var(--navy-blue)',
              color: 'var(--white)'
            }}
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
}

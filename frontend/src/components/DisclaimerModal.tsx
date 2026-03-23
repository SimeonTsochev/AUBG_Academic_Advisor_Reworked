import { useEffect, useState } from 'react';

interface DisclaimerModalProps {
  onClose: () => void;
  onConfirm: () => void;
}

export function DisclaimerModal({ onClose, onConfirm }: DisclaimerModalProps) {
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[1200] flex items-center justify-center p-6"
      style={{ backgroundColor: 'rgba(15, 30, 58, 0.42)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl border shadow-2xl"
        style={{
          backgroundColor: 'var(--white)',
          borderColor: 'var(--neutral-border)',
          boxShadow: '0 24px 48px rgba(15, 30, 58, 0.24)',
        }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="disclaimer-title"
        aria-describedby="disclaimer-description"
      >
        <div className="p-8 md:p-10">
          <h2 id="disclaimer-title" className="mb-5">
            Disclaimer
          </h2>

          <div
            id="disclaimer-description"
            className="grid gap-4 text-base"
            style={{ color: 'var(--neutral-dark)' }}
          >
            <p>
              This app is a planning tool only. The recommendations are based on available
              catalog data and may not reflect all individual circumstances or policy updates.
            </p>
            <p>
              Always verify your course choices with your official academic advisor before
              registering.
            </p>
            <p>
              This application does not enroll you in courses or modify your academic record.
              All registrations must be completed through the official AUBG registration system.
            </p>
            <p>
              By continuing, you acknowledge that you use the recommendations at your own risk.
            </p>
          </div>

          <label
            className="mt-7 flex items-start gap-3 rounded-xl border px-4 py-4 cursor-pointer"
            style={{
              borderColor: accepted ? 'var(--academic-gold)' : 'var(--neutral-border)',
              backgroundColor: 'var(--neutral-gray)',
            }}
          >
            <input
              type="checkbox"
              checked={accepted}
              onChange={(event) => setAccepted(event.target.checked)}
              autoFocus
              className="mt-1"
            />
            <span style={{ color: 'var(--navy-dark)', fontWeight: 500 }}>
              I understand and wish to continue.
            </span>
          </label>

          <div className="mt-7 flex justify-end">
            <button
              type="button"
              onClick={onConfirm}
              disabled={!accepted}
              className="px-6 py-3 rounded-xl font-semibold transition-all"
              style={{
                backgroundColor: accepted ? 'var(--academic-gold)' : 'var(--neutral-border)',
                color: accepted ? 'var(--navy-dark)' : 'var(--neutral-dark)',
                cursor: accepted ? 'pointer' : 'not-allowed',
              }}
            >
              Continue to Plan
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

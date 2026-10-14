import { useEffect } from 'react';

interface StudentProjectNoticeProps {
  onAcknowledge: () => void;
}

// Shown before anything else on every route, so a visitor knows up front who made the tool.
export function StudentProjectNotice({ onAcknowledge }: StudentProjectNoticeProps) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onAcknowledge();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onAcknowledge]);

  return (
    <div className="modal-overlay">
      <div
        className="modal"
        style={{ width: 'min(100%, 38rem)' }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="student-notice-title"
        aria-describedby="student-notice-description"
      >
        <div className="p-8 md:p-10">
          <h2 id="student-notice-title" className="mb-5">
            Before you start
          </h2>

          <div
            id="student-notice-description"
            className="grid gap-4 text-base"
            style={{ color: 'var(--neutral-dark)' }}
          >
            <p>
              This planner was built by an AUBG student as an independent project. I am just a
              student and I am not employed by the American University in Bulgaria.
            </p>
            <p>
              This is not an official AUBG service, and it is not endorsed by the university or its
              academic advising staff.
            </p>
          </div>

          <div className="mt-7 flex justify-end">
            <button
              type="button"
              onClick={onAcknowledge}
              autoFocus
              className="btn btn-primary btn-lg"
            >
              I understand
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

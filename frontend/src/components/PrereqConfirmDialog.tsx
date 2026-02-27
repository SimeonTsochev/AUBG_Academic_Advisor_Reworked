interface PrereqConfirmDialogProps {
  courseToAdd: {
    code: string;
    name?: string;
    term?: string;
  };
  prereqs: string[];
  prereqsSatisfied: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
  unmetPrereqs?: string[];
  resolvePrereqName?: (code: string) => string | undefined;
}

export function PrereqConfirmDialog({
  courseToAdd,
  prereqs,
  prereqsSatisfied,
  onConfirm,
  onCancel,
  title,
  unmetPrereqs,
  resolvePrereqName
}: PrereqConfirmDialogProps) {
  const heading =
    title ??
    (courseToAdd.term
      ? `Add ${courseToAdd.code} to ${courseToAdd.term}?`
      : `Add ${courseToAdd.code}?`);

  const formatLabel = (code: string) => {
    const name = resolvePrereqName?.(code);
    return name && name !== code ? `${code} - ${name}` : code;
  };

  const prereqLabels = prereqs.map(formatLabel);
  const unmetLabels = (unmetPrereqs ?? prereqs).map(formatLabel);

  return (
    <div
      className="p-3 rounded-lg border"
      style={{ borderColor: 'var(--neutral-border)', background: 'var(--neutral-cream)' }}
    >
      <div className="font-medium mb-2">{heading}</div>
      {courseToAdd.name && courseToAdd.name !== courseToAdd.code && (
        <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
          {courseToAdd.name}
        </div>
      )}
      {prereqs.length > 0 && (
        <>
          <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
            This course has prerequisites:
          </div>
          <div className="flex flex-wrap gap-2 mb-3">
            {prereqLabels.map((label) => (
              <span
                key={label}
                className="px-2 py-1 rounded text-xs"
                style={{ backgroundColor: 'var(--neutral-gray)', color: 'var(--neutral-dark)' }}
              >
                {label}
              </span>
            ))}
          </div>
        </>
      )}
      {!prereqsSatisfied && (
        <>
          <div className="text-sm mb-2" style={{ color: 'var(--neutral-dark)' }}>
            Prereqs not yet satisfied in your plan. We can still add it, but your schedule may be invalid unless you add
            prereqs earlier.
          </div>
          {unmetLabels.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {unmetLabels.map((label) => (
                <span
                  key={label}
                  className="px-2 py-1 rounded text-xs"
                  style={{ backgroundColor: 'var(--neutral-border)', color: 'var(--navy-dark)' }}
                >
                  {label}
                </span>
              ))}
            </div>
          )}
        </>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="px-3 py-2 rounded-lg text-sm font-medium"
          style={{ background: 'var(--academic-gold)', color: 'var(--navy-dark)' }}
          onClick={onConfirm}
        >
          Confirm
        </button>
        <button
          type="button"
          className="px-3 py-2 rounded-lg text-sm font-medium border"
          style={{ borderColor: 'var(--neutral-border)', background: 'var(--white)' }}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

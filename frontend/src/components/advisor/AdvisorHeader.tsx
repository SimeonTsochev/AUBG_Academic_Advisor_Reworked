import { ArrowLeft, Check, Copy, FileDown, FileJson, GraduationCap } from 'lucide-react';

interface ShareToken {
  token: string | null;
  isLoading: boolean;
  error: string | null;
  copyStatus: 'idle' | 'copied' | 'error';
  onCopy: () => void;
}

interface AdvisorHeaderProps {
  majors: string[];
  minors: string[];
  businessConcentration: string | null;
  canDownload: boolean;
  share: ShareToken;
  onBack: () => void;
  onDownloadJson: () => void;
  onDownloadPdf: () => void;
}

function ShareTokenButton({ token, isLoading, error, copyStatus, onCopy }: ShareToken) {
  if (!token) {
    return (
      <span className="badge badge-neutral" title={error ?? undefined}>
        {isLoading ? 'Saving share link…' : 'Share link unavailable'}
      </span>
    );
  }
  return (
    <button type="button" className="btn btn-ghost btn-sm" onClick={onCopy} title="Copy the code that reopens this plan">
      {copyStatus === 'copied' ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      <span className="num" style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>{token}</span>
      <span>{copyStatus === 'copied' ? 'Copied' : copyStatus === 'error' ? 'Retry' : 'Copy'}</span>
    </button>
  );
}

/** Sticky top bar: where you are, which programs the plan covers, and the export actions. */
export function AdvisorHeader({
  majors,
  minors,
  businessConcentration,
  canDownload,
  share,
  onBack,
  onDownloadJson,
  onDownloadPdf,
}: AdvisorHeaderProps) {
  return (
    <header className="advisor-header">
      <div className="page advisor-header-inner">
        <button type="button" className="btn btn-outline btn-back btn-sm" onClick={onBack}>
          <ArrowLeft aria-hidden="true" />
          <span>Setup</span>
        </button>

        <div className="advisor-header-title">
          <span className="icon-tile" aria-hidden="true">
            <GraduationCap />
          </span>
          <div className="min-w-0">
            <h1 className="advisor-title">Your degree plan</h1>
            <div className="flex flex-wrap gap-1 advisor-programs">
              {majors.map((major) => (
                <span key={`major:${major}`} className="badge badge-navy">{major}</span>
              ))}
              {businessConcentration && businessConcentration !== 'General' && (
                <span className="badge badge-gold">{businessConcentration} concentration</span>
              )}
              {minors.map((minor) => (
                <span key={`minor:${minor}`} className="badge badge-neutral">Minor: {minor}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="advisor-header-actions">
          <ShareTokenButton {...share} />
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={onDownloadJson}
            disabled={!canDownload}
            title="Download the plan as JSON"
          >
            <FileJson aria-hidden="true" />
            <span>JSON</span>
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={onDownloadPdf} disabled={!canDownload}>
            <FileDown aria-hidden="true" />
            <span>Download PDF</span>
          </button>
        </div>
      </div>
    </header>
  );
}

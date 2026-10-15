import { Info } from 'lucide-react';

interface SkippedEditsProps {
  messages: string[];
}

/** The student's changes the planner skipped, or made room for by moving its own courses (utils/planWarnings.ts). */
export function SkippedEdits({ messages }: SkippedEditsProps) {
  if (messages.length === 0) return null;
  return (
    <div className="alert alert-info" role="status">
      <Info aria-hidden="true" />
      <div className="min-w-0">
        <p className="alert-title">About your recent changes</p>
        <ul>
          {messages.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

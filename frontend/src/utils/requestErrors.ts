// fetch() rejects with these when the server cannot be reached (Chrome/Edge, Firefox, Safari).
const NETWORK_FAILURE = /failed to fetch|networkerror|load failed|network request failed/i;

/**
 * A sentence a student can act on for a failed request: an unreachable server reads as such, and
 * any other failure keeps the server's own reason without the "POST /plan/generate failed (...)" prefix.
 */
export function describeRequestError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  if (!message.trim()) return fallback;
  if (NETWORK_FAILURE.test(message)) {
    return "The planning service could not be reached. Check your connection and try again.";
  }
  const reason = message.replace(/^(GET|POST|PUT|DELETE)\s+\S+\s+failed(\s*\([^)]*\))?:?\s*/i, "").trim();
  return reason || fallback;
}

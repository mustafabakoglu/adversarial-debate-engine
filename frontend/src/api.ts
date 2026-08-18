import type { DebateEvent } from "./types";

export interface DebateStreamHandlers {
  onEvent: (event: DebateEvent) => void;
  /** Called once when the stream ends, whether cleanly or with a transport error. */
  onClose: (transportError: boolean) => void;
}

/**
 * Open a debate stream. Returns a function that aborts it.
 *
 * EventSource is used rather than fetch+ReadableStream because the endpoint is a
 * plain GET and EventSource handles frame parsing for us. Its automatic
 * reconnect is unwanted here — a debate is not resumable — so we close it
 * ourselves as soon as the server signals completion or failure.
 */
export function streamDebate(claim: string, handlers: DebateStreamHandlers): () => void {
  const url = `/api/debate/stream?claim=${encodeURIComponent(claim)}`;
  const source = new EventSource(url);
  let finished = false;

  const shutdown = (transportError: boolean) => {
    if (finished) return;
    finished = true;
    source.close();
    handlers.onClose(transportError);
  };

  source.onmessage = (message: MessageEvent<string>) => {
    let event: DebateEvent;
    try {
      event = JSON.parse(message.data) as DebateEvent;
    } catch {
      return;
    }
    handlers.onEvent(event);
    if (event.type === "done" || event.type === "error") {
      shutdown(false);
    }
  };

  source.onerror = () => {
    // EventSource reports both "server closed the connection" and real network
    // failures here; only the latter matters, and only before we are finished.
    shutdown(true);
  };

  return () => shutdown(false);
}

import type { DebateEvent } from "./types";

export interface StreamHandlers {
  onEvent: (event: DebateEvent) => void;
  /** Called once when the stream ends; `transportError` means it dropped. */
  onClose: (transportError: boolean) => void;
}

/**
 * Subscribe to a server-sent event stream of debate events.
 *
 * EventSource parses the frames for us, but its automatic reconnect is wrong
 * here — a debate cannot be resumed halfway — so the connection is closed as
 * soon as the server signals completion or failure.
 */
function subscribe(url: string, handlers: StreamHandlers): () => void {
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
    if (event.type === "done" || event.type === "error") shutdown(false);
  };

  source.onerror = () => shutdown(true);

  return () => shutdown(false);
}

export function startDebate(claim: string, handlers: StreamHandlers): () => void {
  return subscribe(`/api/debate/stream?claim=${encodeURIComponent(claim)}`, handlers);
}

export function challengeVerdict(
  sessionId: string,
  argument: string,
  handlers: StreamHandlers,
): () => void {
  const query = `session=${encodeURIComponent(sessionId)}&argument=${encodeURIComponent(argument)}`;
  return subscribe(`/api/debate/challenge?${query}`, handlers);
}

export interface DemoSummary {
  name: string;
  claim: string;
  rounds: number;
  recorded_at: string;
}

/** Recorded debates the server can replay. Absent or unreachable means none. */
export async function fetchDemos(): Promise<DemoSummary[]> {
  try {
    const response = await fetch("/api/demos");
    if (!response.ok) return [];
    const body = (await response.json()) as { demos?: DemoSummary[] };
    return body.demos ?? [];
  } catch {
    return [];
  }
}

export function replayDebate(name: string, handlers: StreamHandlers): () => void {
  return subscribe(`/api/debate/replay?name=${encodeURIComponent(name)}`, handlers);
}

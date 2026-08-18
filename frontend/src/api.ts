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

/**
 * Whether a debate engine is reachable at all.
 *
 * This page is deployable as static files, because the recorded debates need no server.
 * So it has to work out which of the two it is: a full deployment where a claim can be
 * argued live, or a static host where only the recordings exist.
 */
export async function fetchEngineStatus(): Promise<{ live: boolean; model: string | null }> {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) return { live: false, model: null };
    const body = (await response.json()) as { configured?: boolean; model?: string | null };
    return { live: Boolean(body.configured), model: body.model ?? null };
  } catch {
    return { live: false, model: null };
  }
}

/** Recorded debates: from the API if there is one, otherwise from static files. */
export async function fetchDemos(): Promise<DemoSummary[]> {
  for (const url of ["/api/demos", "demos/index.json"]) {
    try {
      const response = await fetch(url);
      if (!response.ok) continue;
      const body = (await response.json()) as { demos?: DemoSummary[] };
      if (body.demos?.length) return body.demos;
    } catch {
      // Try the next source; a missing one is not an error worth showing.
    }
  }
  return [];
}

export function replayDebate(name: string, handlers: StreamHandlers): () => void {
  return subscribe(`/api/debate/replay?name=${encodeURIComponent(name)}`, handlers);
}

/**
 * Replay a recording client-side, for a static deployment.
 *
 * Deliberately the same shape as the server's replay - the same events, the same pauses
 * where a live run waited on the model - so nothing downstream can tell which one it is
 * watching and the UI needs no static-only branch.
 */
export function replayLocally(name: string, handlers: StreamHandlers, gapMs = 700): () => void {
  let stopped = false;
  const timers: number[] = [];
  const slow = new Set(["turn_start", "status", "referee", "verdict"]);

  void (async () => {
    let recording: { claim?: string; recorded_at?: string; events?: DebateEvent[] };
    try {
      const response = await fetch(`demos/${encodeURIComponent(name)}.json`);
      if (!response.ok) throw new Error(String(response.status));
      recording = await response.json();
    } catch {
      handlers.onEvent({
        type: "error",
        message: "That recorded debate could not be loaded.",
        recoverable: false,
      });
      handlers.onClose(false);
      return;
    }

    handlers.onEvent({
      type: "session",
      session_id: "",
      claim: recording.claim ?? "",
      recorded: true,
      recorded_at: recording.recorded_at ?? "",
    });

    for (const event of recording.events ?? []) {
      if (stopped) return;
      if (event.type === "turn_delta" || event.type === "session") continue;

      if (slow.has(event.type) && gapMs) {
        await new Promise<void>((resolve) => {
          timers.push(window.setTimeout(resolve, gapMs));
        });
        if (stopped) return;
      }

      // Hand the whole turn over as one fragment; the client types it out.
      if (event.type === "turn_end" && event.text) {
        handlers.onEvent({ type: "turn_delta", text: event.text });
      }
      handlers.onEvent(event);
    }

    handlers.onClose(false);
  })();

  return () => {
    stopped = true;
    for (const timer of timers) window.clearTimeout(timer);
  };
}

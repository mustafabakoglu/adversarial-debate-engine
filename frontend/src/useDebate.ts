import { useCallback, useEffect, useRef, useState } from "react";

import { challengeVerdict, replayDebate, startDebate, type StreamHandlers } from "./api";
import { keyboard } from "./sound";
import type { DebateEvent, Entry, Message } from "./types";

interface DebateState {
  claim: string | null;
  entries: Entry[];
  status: string | null;
  error: string | null;
  running: boolean;
  /** True once a verdict has arrived and the user may argue back. */
  canChallenge: boolean;
  /** True when what is on screen is a replay of a recorded debate. */
  recorded: boolean;
}

const INITIAL: DebateState = {
  claim: null,
  entries: [],
  status: null,
  error: null,
  running: false,
  canChallenge: false,
  recorded: false,
};

/**
 * Everything the network hands us goes into one queue, and a clock drains it.
 *
 * The model produces a turn far faster than anyone reads it, so the raw stream
 * arrives in bursts that dump a paragraph on screen at once — which reads like a
 * machine pasting text, not like someone arguing. So fragments are held and
 * released a few characters at a time, and the next event is only processed once
 * the current turn has finished being typed. Ordering therefore survives: a
 * verdict cannot appear while the last word is still being written.
 *
 * The rate is not constant. It rises with the backlog, so if the server gets far
 * ahead the typing speeds up rather than falling minutes behind, and it pauses
 * briefly at sentence ends, which is most of what makes it feel like a person.
 */
const TICK_MS = 30;
const BASE_CHARS_PER_SECOND = 24;
const SENTENCE_PAUSE_MS = 190;
const CLAUSE_PAUSE_MS = 70;
const PARAGRAPH_PAUSE_MS = 260;

/** A stream close is queued like an event so it lands after the typing finishes. */
type QueueItem = DebateEvent | { type: "__close"; transportError: boolean };

function pauseAfter(char: string): number {
  if (char === "\n") return PARAGRAPH_PAUSE_MS;
  if (char === "." || char === "!" || char === "?" || char === "…") return SENTENCE_PAUSE_MS;
  if (char === "," || char === ";" || char === ":" || char === "—") return CLAUSE_PAUSE_MS;
  return 0;
}

function charsPerTick(backlog: number): number {
  // Catch-up curve. The thresholds are deliberately high — a single turn is around
  // 900 characters, so a backlog under that is just the model being ahead of the
  // reader, which is the normal state and should not speed anything up. Only a
  // backlog of several turns means the display is genuinely falling behind.
  const multiplier = backlog > 2400 ? 3.2 : backlog > 1500 ? 2.1 : backlog > 800 ? 1.4 : 1;
  return Math.max(1, Math.round((BASE_CHARS_PER_SECOND * multiplier * TICK_MS) / 1000));
}

export function useDebate() {
  const [state, setState] = useState<DebateState>(INITIAL);
  const sessionRef = useRef<string | null>(null);
  const abortRef = useRef<(() => void) | null>(null);
  const counterRef = useRef(0);

  const queueRef = useRef<QueueItem[]>([]);
  const bufferRef = useRef("");
  const pauseUntilRef = useRef(0);
  const timerRef = useRef<number | null>(null);

  const nextId = () => `e${counterRef.current++}`;

  /** Apply one event to the visible state. Deltas never reach this. */
  const apply = useCallback((item: QueueItem) => {
    setState((current) => {
      switch (item.type) {
        case "session":
          sessionRef.current = item.session_id;
          return { ...current, claim: item.claim, recorded: Boolean(item.recorded) };

        case "round_start":
          return {
            ...current,
            status: item.name,
            entries: [
              ...current.entries,
              { kind: "round", id: nextId(), number: item.number, name: item.name },
            ],
          };

        case "status":
          return { ...current, status: item.message };

        case "turn_start": {
          const message: Message = { ...item, text: "", streaming: true };
          return {
            ...current,
            entries: [...current.entries, { kind: "message", id: nextId(), message }],
          };
        }

        case "turn_end": {
          const { type: _type, ...turn } = item;
          const entries = [...current.entries];
          for (let i = entries.length - 1; i >= 0; i -= 1) {
            const entry = entries[i];
            if (entry.kind === "message" && entry.message.streaming) {
              entries[i] = { ...entry, message: { ...turn, streaming: false } };
              return { ...current, entries };
            }
          }
          // The user's own challenge arrives as a turn_end with no turn_start,
          // because nothing was streamed for it.
          return {
            ...current,
            entries: [
              ...entries,
              { kind: "message", id: nextId(), message: { ...turn, streaming: false } },
            ],
          };
        }

        case "referee": {
          const { type: _type, ...referee } = item;
          return {
            ...current,
            status: null,
            entries: [...current.entries, { kind: "referee", id: nextId(), referee }],
          };
        }

        case "verdict": {
          const { type: _type, ...verdict } = item;
          return {
            ...current,
            status: null,
            canChallenge: true,
            entries: [...current.entries, { kind: "verdict", id: nextId(), verdict }],
          };
        }

        case "error":
          return { ...current, status: null, error: item.message };

        case "done":
          return { ...current, status: null };

        case "turn_delta":
          // Handled by the typing clock, never applied directly.
          return current;

        case "__close":
          return {
            ...current,
            running: false,
            status: null,
            error:
              current.error ??
              (item.transportError
                ? "Lost the connection to the debate server. Make sure the backend is running on port 8123."
                : null),
          };
      }
    });
  }, []);

  /** Move `count` characters from the buffer into the open message. */
  const type = useCallback((count: number) => {
    const chunk = bufferRef.current.slice(0, count);
    bufferRef.current = bufferRef.current.slice(chunk.length);
    if (!chunk) return;

    for (const char of chunk) keyboard.press(char);
    pauseUntilRef.current = performance.now() + pauseAfter(chunk[chunk.length - 1]);

    setState((current) => {
      const entries = [...current.entries];
      for (let i = entries.length - 1; i >= 0; i -= 1) {
        const entry = entries[i];
        if (entry.kind === "message" && entry.message.streaming) {
          entries[i] = { ...entry, message: { ...entry.message, text: entry.message.text + chunk } };
          return { ...current, entries };
        }
      }
      return current;
    });
  }, []);

  const stopClock = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startClock = useCallback(() => {
    if (timerRef.current !== null) return;

    timerRef.current = window.setInterval(() => {
      if (performance.now() < pauseUntilRef.current) return;

      if (bufferRef.current.length) {
        const queued = queueRef.current.reduce(
          (total, item) => (item.type === "turn_delta" ? total + item.text.length : total),
          0,
        );
        type(charsPerTick(bufferRef.current.length + queued));
        return;
      }

      // Nothing left to type: take events until one needs typing.
      while (queueRef.current.length) {
        const item = queueRef.current.shift() as QueueItem;
        if (item.type === "turn_delta") {
          bufferRef.current += item.text;
          break;
        }
        apply(item);
        // Let each committed turn render before the next speaker starts.
        if (item.type === "turn_end") break;
      }

      if (!queueRef.current.length && !bufferRef.current.length) stopClock();
    }, TICK_MS);
  }, [apply, stopClock, type]);

  const handlers = useCallback(
    (): StreamHandlers => ({
      onEvent: (event) => {
        queueRef.current.push(event);
        startClock();
      },
      onClose: (transportError) => {
        queueRef.current.push({ type: "__close", transportError });
        startClock();
      },
    }),
    [startClock],
  );

  const start = useCallback(
    (claim: string) => {
      abortRef.current?.();
      stopClock();
      queueRef.current = [];
      bufferRef.current = "";
      pauseUntilRef.current = 0;
      counterRef.current = 0;
      sessionRef.current = null;
      setState({ ...INITIAL, claim, running: true, status: "Opening the debate" });
      abortRef.current = startDebate(claim, handlers());
    },
    [handlers, stopClock],
  );

  const replay = useCallback(
    (name: string, claim: string) => {
      abortRef.current?.();
      stopClock();
      queueRef.current = [];
      bufferRef.current = "";
      pauseUntilRef.current = 0;
      counterRef.current = 0;
      sessionRef.current = null;
      setState({ ...INITIAL, claim, running: true, recorded: true, status: "Replaying" });
      abortRef.current = replayDebate(name, handlers());
    },
    [handlers, stopClock],
  );

  const challenge = useCallback(
    (argument: string) => {
      const sessionId = sessionRef.current;
      if (!sessionId) return;
      queueRef.current = [];
      bufferRef.current = "";
      pauseUntilRef.current = 0;
      setState((current) => ({
        ...current,
        running: true,
        canChallenge: false,
        error: null,
        status: "Putting your argument to both sides",
      }));
      abortRef.current = challengeVerdict(sessionId, argument, handlers());
    },
    [handlers],
  );

  const reset = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    stopClock();
    queueRef.current = [];
    bufferRef.current = "";
    sessionRef.current = null;
    counterRef.current = 0;
    setState(INITIAL);
  }, [stopClock]);

  useEffect(
    () => () => {
      abortRef.current?.();
      stopClock();
    },
    [stopClock],
  );

  return { ...state, start, replay, challenge, reset };
}

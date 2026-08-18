import { useCallback, useEffect, useRef, useState } from "react";

import { streamDebate } from "./api";
import { ClaimInput } from "./components/ClaimInput";
import { DebateView } from "./components/DebateView";
import type { DebateEvent, Turn, Verdict } from "./types";

export default function App() {
  const [claim, setClaim] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const abortRef = useRef<(() => void) | null>(null);

  // Abort an in-flight debate if the component goes away.
  useEffect(() => () => abortRef.current?.(), []);

  const handleEvent = useCallback((event: DebateEvent) => {
    switch (event.type) {
      case "status":
        setStatus(event.message);
        break;
      case "round_start":
        setStatus(`Round ${event.number} — ${event.name}`);
        break;
      case "turn": {
        const { type: _type, ...turn } = event;
        setTurns((current) => [...current, turn]);
        break;
      }
      case "verdict": {
        const { type: _type, ...result } = event;
        setVerdict(result);
        setStatus(null);
        break;
      }
      case "error":
        setError(event.message);
        setStatus(null);
        break;
      case "claim":
      case "done":
        break;
    }
  }, []);

  const start = useCallback(
    (nextClaim: string) => {
      abortRef.current?.();
      setClaim(nextClaim);
      setTurns([]);
      setVerdict(null);
      setError(null);
      setStatus("Opening the debate...");
      setRunning(true);

      abortRef.current = streamDebate(nextClaim, {
        onEvent: handleEvent,
        onClose: (transportError) => {
          setRunning(false);
          setStatus(null);
          if (transportError) {
            setError((current) =>
              current ??
              "Lost the connection to the debate server. Make sure the backend is running, then try again.",
            );
          }
        },
      });
    },
    [handleEvent],
  );

  const reset = useCallback(() => {
    abortRef.current?.();
    abortRef.current = null;
    setClaim(null);
    setTurns([]);
    setStatus(null);
    setVerdict(null);
    setError(null);
    setRunning(false);
  }, []);

  return (
    <main className="min-h-screen">
      {claim === null ? (
        <ClaimInput onStart={start} />
      ) : (
        <DebateView
          claim={claim}
          turns={turns}
          status={status}
          verdict={verdict}
          error={error}
          running={running}
          onReset={reset}
        />
      )}
    </main>
  );
}

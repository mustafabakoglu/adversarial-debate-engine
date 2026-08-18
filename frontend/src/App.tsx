import { useCallback, useEffect, useRef } from "react";

import { ClaimInput } from "./components/ClaimInput";
import { DebateView } from "./components/DebateView";
import { SettingsBar } from "./components/SettingsBar";
import { useDebate } from "./useDebate";
import { useTheme, useTypingSound } from "./useSettings";

export default function App() {
  const {
    claim,
    entries,
    status,
    error,
    running,
    recorded,
    canChallenge,
    start,
    replay,
    challenge,
    reset,
  } = useDebate();
  const theme = useTheme();
  const sound = useTypingSound();

  // Starting a debate is a click, which is the browser's price for playing audio.
  const startDebate = useCallback(
    (nextClaim: string) => {
      sound.armFromGesture();
      start(nextClaim);
    },
    [sound, start],
  );

  // Deep links: ?claim=... starts a live debate, ?replay=name plays a recording.
  // Written for demo recordings, where a page that argues the moment it loads beats
  // one that needs a click, and useful on its own for sharing a claim.
  const launched = useRef(false);
  useEffect(() => {
    if (launched.current) return;
    launched.current = true;

    const params = new URLSearchParams(window.location.search);
    const recording = params.get("replay");
    const linkedClaim = params.get("claim");
    if (recording) replay(recording, linkedClaim ?? "");
    else if (linkedClaim && linkedClaim.trim().length >= 8) start(linkedClaim.trim());
  }, [replay, start]);

  const startReplay = useCallback(
    (name: string, nextClaim: string) => {
      sound.armFromGesture();
      replay(name, nextClaim);
    },
    [replay, sound],
  );

  return (
    <main className="min-h-screen bg-canvas text-ink">
      <SettingsBar sound={sound} theme={theme} />
      {claim === null ? (
        <ClaimInput onStart={startDebate} onReplay={startReplay} />
      ) : (
        <DebateView
          claim={claim}
          entries={entries}
          status={status}
          error={error}
          running={running}
          recorded={recorded}
          canChallenge={canChallenge}
          onChallenge={challenge}
          onReset={reset}
        />
      )}
    </main>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchEngineStatus } from "./api";
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

  // A static deployment has the recordings but no engine. Ask once, then say so
  // plainly rather than letting someone submit a claim into nothing.
  const [live, setLive] = useState<boolean | null>(null);
  useEffect(() => {
    let mounted = true;
    void fetchEngineStatus().then(({ live: reachable }) => {
      if (mounted) setLive(reachable);
    });
    return () => {
      mounted = false;
    };
  }, []);

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
    if (launched.current || live === null) return;
    launched.current = true;

    const params = new URLSearchParams(window.location.search);
    const recording = params.get("replay");
    const linkedClaim = params.get("claim");
    if (recording) replay(recording, linkedClaim ?? "", live === false);
    else if (linkedClaim && linkedClaim.trim().length >= 8) start(linkedClaim.trim());
  }, [live, replay, start]);

  const startReplay = useCallback(
    (name: string, nextClaim: string) => {
      sound.armFromGesture();
      replay(name, nextClaim, live === false);
    },
    [live, replay, sound],
  );

  return (
    <main className="min-h-screen bg-canvas text-ink">
      <SettingsBar sound={sound} theme={theme} />
      {claim === null ? (
        <ClaimInput onStart={startDebate} onReplay={startReplay} live={live} />
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

import { useEffect, useState } from "react";

import { fetchDemos, type DemoSummary, type EngineStatus } from "../api";

const EXAMPLES = [
  "AI will replace software developers.",
  "A university degree is no longer necessary.",
  "Remote work is more productive than working from an office.",
  "Attendance requirements at universities should be abolished.",
];

interface Props {
  onStart: (claim: string) => void;
  onReplay: (name: string, claim: string) => void;
  /** null while unknown. Drives what the claim box is allowed to promise. */
  engine: EngineStatus | null;
  disabled?: boolean;
}

export function ClaimInput({ onStart, onReplay, engine, disabled = false }: Props) {
  const live = engine === null ? null : engine.live;
  const [claim, setClaim] = useState("");
  const [demos, setDemos] = useState<DemoSummary[]>([]);

  // Recorded debates are optional: none on disk means this section simply is not
  // there, and the server being unreachable is not worth an error here.
  useEffect(() => {
    let live = true;
    void fetchDemos().then((found) => {
      if (live) setDemos(found);
    });
    return () => {
      live = false;
    };
  }, []);
  const trimmed = claim.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < 8;
  const canStart = trimmed.length >= 8 && !disabled && live !== false;

  const submit = () => {
    if (canStart) onStart(trimmed);
  };

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-6 py-20">
      <p className="mb-3 text-xs font-medium tracking-[0.2em] text-ink-faint uppercase">
        Adversarial AI Debate Engine
      </p>
      <h1 className="mb-4 text-center text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
        This AI does not agree with you.
      </h1>
      <p className="mb-12 max-w-xl text-center text-base leading-relaxed text-ink-soft">
        Submit a claim. One agent attacks it, one defends it, and they keep going until a
        referee rules the disagreement is actually finished. A third agent then scores how
        well they argued &mdash; not whether you were right.
      </p>

      <div className="w-full">
        <label htmlFor="claim" className="sr-only">
          Enter a claim
        </label>
        <textarea
          id="claim"
          value={claim}
          onChange={(event) => setClaim(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              event.preventDefault();
              submit();
            }
          }}
          rows={3}
          maxLength={400}
          placeholder={
            live === false ? "Read-only demo — watch a recorded debate below" : "Enter a claim..."
          }
          disabled={disabled || live === false}
          className="w-full resize-none rounded-2xl border border-line bg-surface px-6 py-5 text-lg leading-relaxed text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none disabled:opacity-50"
        />

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <span className="text-xs text-ink-faint">
            {live === false
              ? engine?.reachable
                ? "This deployment has no model key, so live debates are off. The recorded debates below are real ones."
                : "No engine behind this page — run it locally, or deploy the container, to argue your own claim."
              : tooShort
                ? "A claim needs at least 8 characters."
                : "⌘ / Ctrl + Enter to start"}
          </span>
          <button
            type="button"
            onClick={submit}
            disabled={!canStart}
            className="rounded-full bg-ink px-7 py-3 text-sm font-semibold tracking-wide text-canvas uppercase transition hover:opacity-90 disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-faint disabled:opacity-100"
          >
            Start Debate
          </button>
        </div>
      </div>

      {demos.length ? (
        <div className="mt-14 w-full">
          <p className="mb-2 text-xs tracking-[0.16em] text-ink-faint uppercase">
            Or watch one that already happened
          </p>
          <p className="mb-4 text-xs leading-relaxed text-ink-faint">
            A real debate, recorded and replayed at the same pace. No model calls, so it works
            with no key and no network.
          </p>
          <div className="flex flex-col gap-2">
            {demos.map((demo) => (
              <button
                key={demo.name}
                type="button"
                onClick={() => onReplay(demo.name, demo.claim)}
                disabled={disabled}
                className="flex flex-col gap-1 rounded-xl border border-line-soft bg-raised px-5 py-3 text-left transition hover:border-ink-faint disabled:opacity-40"
              >
                <span className="text-sm text-ink">{demo.claim}</span>
                <span className="text-xs text-ink-faint">
                  recorded · {demo.rounds} rounds
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-14 w-full">
        <p className="mb-4 text-xs tracking-[0.16em] text-ink-faint uppercase">Try one</p>
        <div className="flex flex-col gap-2">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setClaim(example)}
              disabled={disabled}
              className="rounded-xl border border-line-soft bg-raised px-5 py-3 text-left text-sm text-ink-soft transition hover:border-ink-faint hover:text-ink disabled:opacity-40"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

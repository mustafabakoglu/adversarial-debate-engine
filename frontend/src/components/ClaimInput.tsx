import { useState } from "react";

const EXAMPLES = [
  "AI will replace software developers.",
  "A university degree is no longer necessary.",
  "Remote work is more productive than working from an office.",
  "Attendance requirements at universities should be abolished.",
];

interface Props {
  onStart: (claim: string) => void;
  disabled?: boolean;
}

export function ClaimInput({ onStart, disabled = false }: Props) {
  const [claim, setClaim] = useState("");
  const trimmed = claim.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < 8;
  const canStart = trimmed.length >= 8 && !disabled;

  const submit = () => {
    if (canStart) onStart(trimmed);
  };

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center px-6 py-20">
      <p className="mb-3 text-xs font-medium tracking-[0.2em] text-white/40 uppercase">
        Adversarial AI Debate Engine
      </p>
      <h1 className="mb-4 text-center text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
        This AI does not agree with you.
      </h1>
      <p className="mb-12 max-w-xl text-center text-base leading-relaxed text-white/50">
        Submit a claim. One agent attacks it, one defends it, and each must answer the
        other. A third agent scores how well they argued &mdash; not whether you were right.
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
          placeholder="Enter a claim..."
          disabled={disabled}
          className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-5 text-lg leading-relaxed text-white placeholder:text-white/25 focus:border-white/25 focus:outline-none disabled:opacity-50"
        />

        <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <span className="text-xs text-white/30">
            {tooShort ? "A claim needs at least 8 characters." : "⌘ / Ctrl + Enter to start"}
          </span>
          <button
            type="button"
            onClick={submit}
            disabled={!canStart}
            className="rounded-full bg-white px-7 py-3 text-sm font-semibold tracking-wide text-neutral-950 uppercase transition hover:bg-white/90 disabled:cursor-not-allowed disabled:bg-white/20 disabled:text-white/40"
          >
            Start Debate
          </button>
        </div>
      </div>

      <div className="mt-14 w-full">
        <p className="mb-4 text-xs tracking-[0.16em] text-white/30 uppercase">Try one</p>
        <div className="flex flex-col gap-2">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setClaim(example)}
              disabled={disabled}
              className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-5 py-3 text-left text-sm text-white/60 transition hover:border-white/20 hover:text-white/90 disabled:opacity-40"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

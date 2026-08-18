import { useState } from "react";

const MIN_LENGTH = 8;
const MAX_LENGTH = 2000;

interface Props {
  onSubmit: (argument: string) => void;
  disabled?: boolean;
}

/**
 * The challenge round: the person who submitted the claim argues back, and both
 * sides have to answer them before the debate is judged again.
 */
export function ChallengeInput({ onSubmit, disabled = false }: Props) {
  const [argument, setArgument] = useState("");
  const trimmed = argument.trim();
  const canSend = trimmed.length >= MIN_LENGTH && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSubmit(trimmed);
    setArgument("");
  };

  return (
    <section className="enter rounded-2xl border border-line bg-raised p-6">
      <h3 className="mb-2 text-xs font-semibold tracking-[0.18em] text-ink-soft uppercase">
        Not convinced?
      </h3>
      <p className="mb-4 text-sm leading-relaxed text-ink-soft">
        Argue back. Both sides have to answer you specifically, and the judge scores the
        debate again with your argument in the transcript &mdash; it will not agree with you
        just because you asked.
      </p>

      <label htmlFor="challenge" className="sr-only">
        Your counter-argument
      </label>
      <textarea
        id="challenge"
        value={argument}
        onChange={(event) => setArgument(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            submit();
          }
        }}
        rows={4}
        maxLength={MAX_LENGTH}
        placeholder="The verdict missed that..."
        disabled={disabled}
        className="w-full resize-none rounded-xl border border-line bg-surface px-5 py-4 text-[0.9375rem] leading-relaxed text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none disabled:opacity-50"
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-ink-faint">
          {trimmed.length > 0 && trimmed.length < MIN_LENGTH
            ? `At least ${MIN_LENGTH} characters.`
            : "⌘ / Ctrl + Enter to send"}
        </span>
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          className="rounded-full bg-ink px-6 py-2.5 text-sm font-semibold tracking-wide text-canvas uppercase transition hover:opacity-90 disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-faint disabled:opacity-100"
        >
          Challenge the verdict
        </button>
      </div>
    </section>
  );
}

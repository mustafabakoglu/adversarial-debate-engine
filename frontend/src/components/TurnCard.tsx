import { KIND_LABEL, SPEAKER_LABEL, type Message } from "../types";

const SIDE_STYLES: Record<Message["speaker"], { border: string; dot: string; label: string }> = {
  prosecutor: {
    border: "border-l-prosecutor",
    dot: "bg-prosecutor",
    label: "text-prosecutor",
  },
  defender: {
    border: "border-l-defender",
    dot: "bg-defender",
    label: "text-defender",
  },
  // Neither the user nor the judge is a side in the debate, so they get no side
  // colour. The judge gets the solid one, because the bench is not a participant.
  user: {
    border: "border-l-ink-faint",
    dot: "bg-ink-faint",
    label: "text-ink",
  },
  judge: {
    border: "border-l-ink",
    dot: "bg-ink",
    label: "text-ink",
  },
};

export function TurnCard({ message }: { message: Message }) {
  const style = SIDE_STYLES[message.speaker];
  const isQuestion = message.kind === "cross_question" || message.kind === "judge_question";

  return (
    <article className={`enter rounded-r-xl border-l-2 bg-surface px-5 py-4 ${style.border}`}>
      <header className="mb-3 flex items-center gap-2">
        <span className={`size-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
        <span className={`text-xs font-semibold tracking-[0.14em] uppercase ${style.label}`}>
          {SPEAKER_LABEL[message.speaker]}
        </span>
        <span className="text-xs tracking-[0.14em] text-ink-faint uppercase">
          {KIND_LABEL[message.kind]}
        </span>
      </header>
      <p
        className={`text-[0.9375rem] leading-relaxed whitespace-pre-wrap ${
          isQuestion ? "text-ink italic" : "text-ink-soft"
        }`}
      >
        {message.text}
        {message.streaming ? <span className="caret" aria-hidden="true" /> : null}
      </p>
    </article>
  );
}

import { KIND_LABEL, SPEAKER_LABEL, type Turn } from "../types";

const SIDE_STYLES: Record<Turn["speaker"], { border: string; dot: string; label: string }> = {
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
};

export function TurnCard({ turn }: { turn: Turn }) {
  const style = SIDE_STYLES[turn.speaker];
  const isQuestion = turn.kind === "cross_question";

  return (
    <article
      className={`animate-rise rounded-r-xl border-l-2 bg-white/[0.025] px-5 py-4 ${style.border}`}
    >
      <header className="mb-3 flex items-center gap-2">
        <span className={`size-1.5 rounded-full ${style.dot}`} aria-hidden="true" />
        <span className={`text-xs font-semibold tracking-[0.14em] uppercase ${style.label}`}>
          {SPEAKER_LABEL[turn.speaker]}
        </span>
        <span className="text-xs tracking-[0.14em] text-white/25 uppercase">
          {KIND_LABEL[turn.kind]}
        </span>
      </header>
      <p
        className={`text-[0.9375rem] leading-relaxed whitespace-pre-wrap ${
          isQuestion ? "text-white/90 italic" : "text-white/75"
        }`}
      >
        {turn.text}
      </p>
    </article>
  );
}

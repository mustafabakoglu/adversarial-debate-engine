import { SPEAKER_LABEL, type Verdict } from "../types";

function ScoreRow({
  label,
  score,
  isWinner,
  tone,
}: {
  label: string;
  score: number;
  isWinner: boolean;
  tone: "prosecutor" | "defender";
}) {
  const bar = tone === "prosecutor" ? "bg-prosecutor" : "bg-defender";
  const text = tone === "prosecutor" ? "text-prosecutor" : "text-defender";
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className={`text-xs font-semibold tracking-[0.14em] uppercase ${text}`}>{label}</span>
        <span
          className={`font-mono text-2xl tabular-nums ${isWinner ? "text-ink" : "text-ink-faint"}`}
        >
          {score}
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-line">
        <div
          className={`h-full rounded-full transition-[width] duration-700 ease-out ${bar}`}
          style={{ width: `${Math.max(2, score)}%` }}
        />
      </div>
    </div>
  );
}

function Finding({ title, body }: { title: string; body: string }) {
  if (!body) return null;
  return (
    <div>
      <h4 className="mb-1.5 text-xs tracking-[0.14em] text-ink-faint uppercase">{title}</h4>
      <p className="text-sm leading-relaxed text-ink-soft">{body}</p>
    </div>
  );
}

export function VerdictCard({ verdict }: { verdict: Verdict }) {
  const winnerLabel =
    verdict.winner === "draw" ? "Draw" : SPEAKER_LABEL[verdict.winner].toUpperCase();

  return (
    <section className="enter rounded-2xl border border-line bg-surface p-7">
      <header className="mb-7 flex items-center gap-2">
        <span className="text-xs font-semibold tracking-[0.2em] text-ink-soft uppercase">
          ⚖ Judge &mdash; Debate Result
        </span>
      </header>

      <div className="mb-8 grid gap-6 sm:grid-cols-2">
        <ScoreRow
          label="Prosecutor"
          score={verdict.prosecutor_score}
          isWinner={verdict.winner === "prosecutor"}
          tone="prosecutor"
        />
        <ScoreRow
          label="Defender"
          score={verdict.defender_score}
          isWinner={verdict.winner === "defender"}
          tone="defender"
        />
      </div>

      <div className="mb-7 flex flex-wrap items-end gap-x-10 gap-y-4 border-y border-line py-5">
        <div>
          <p className="mb-1 text-xs tracking-[0.14em] text-ink-faint uppercase">Winner</p>
          <p className="text-xl font-semibold tracking-tight">{winnerLabel}</p>
        </div>
        <div>
          <p className="mb-1 text-xs tracking-[0.14em] text-ink-faint uppercase">Confidence</p>
          <p className="font-mono text-xl tabular-nums">{verdict.confidence}%</p>
        </div>
      </div>

      {verdict.reasoning ? (
        <p className="mb-7 text-[0.9375rem] leading-relaxed text-ink">{verdict.reasoning}</p>
      ) : null}

      <div className="grid gap-6">
        <Finding title="Strongest argument" body={verdict.strongest_argument} />
        <Finding title="Weakest argument" body={verdict.weakest_argument} />
        <Finding title="Key unresolved question" body={verdict.unresolved_question} />
      </div>
    </section>
  );
}

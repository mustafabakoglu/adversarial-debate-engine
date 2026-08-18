import { useEffect, useRef } from "react";

import type { Turn, Verdict } from "../types";
import { TurnCard } from "./TurnCard";
import { VerdictCard } from "./VerdictCard";

interface Props {
  claim: string;
  turns: Turn[];
  status: string | null;
  verdict: Verdict | null;
  error: string | null;
  running: boolean;
  onReset: () => void;
}

interface RoundGroup {
  number: number;
  name: string;
  turns: Turn[];
}

function groupRounds(turns: Turn[]): RoundGroup[] {
  const groups: RoundGroup[] = [];
  for (const turn of turns) {
    const last = groups[groups.length - 1];
    if (!last || last.number !== turn.round) {
      groups.push({ number: turn.round, name: turn.round_name, turns: [turn] });
    } else {
      last.turns.push(turn);
    }
  }
  return groups;
}

function RoundHeader({ group }: { group: RoundGroup }) {
  return (
    <div className="mb-5 flex items-center gap-4">
      <span className="font-mono text-xs text-white/30">
        {String(group.number).padStart(2, "0")}
      </span>
      <h3 className="text-xs font-semibold tracking-[0.18em] text-white/55 uppercase">
        {group.name}
      </h3>
      <span className="h-px flex-1 bg-white/[0.07]" />
    </div>
  );
}

export function DebateView({
  claim,
  turns,
  status,
  verdict,
  error,
  running,
  onReset,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const groups = groupRounds(turns);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, verdict, status]);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-12">
      <header className="mb-12 border-b border-white/[0.07] pb-8">
        <p className="mb-3 text-xs tracking-[0.18em] text-white/35 uppercase">Claim under debate</p>
        <h2 className="text-2xl leading-snug font-semibold tracking-tight text-balance sm:text-3xl">
          {claim}
        </h2>
      </header>

      <div className="flex flex-col gap-12">
        {groups.map((group) => (
          <section key={group.number}>
            <RoundHeader group={group} />
            {/* Cross examination is a sequential question/answer thread, so it
                stays in a single column; the other rounds are simultaneous. */}
            <div
              className={
                group.number === 3
                  ? "flex flex-col gap-4"
                  : "grid gap-4 md:grid-cols-2 md:items-start"
              }
            >
              {group.turns.map((turn, index) => (
                <TurnCard key={`${turn.round}-${turn.kind}-${turn.speaker}-${index}`} turn={turn} />
              ))}
            </div>
          </section>
        ))}

        {running && status ? (
          <div className="flex items-center gap-3 text-sm text-white/40">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-white/50" />
              <span className="relative inline-flex size-2 rounded-full bg-white/70" />
            </span>
            {status}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-xl border border-defender/40 bg-defender/[0.07] px-5 py-4 text-sm text-white/80">
            {error}
          </div>
        ) : null}

        {verdict ? <VerdictCard verdict={verdict} /> : null}

        {!running ? (
          <div>
            <button
              type="button"
              onClick={onReset}
              className="rounded-full border border-white/15 px-6 py-2.5 text-sm font-medium text-white/70 transition hover:border-white/35 hover:text-white"
            >
              New debate
            </button>
          </div>
        ) : null}
      </div>

      <div ref={endRef} />
    </div>
  );
}

import { useEffect, useRef } from "react";

import { isSequentialRound, type Entry, type Message, type Referee, type Verdict } from "../types";
import { ChallengeInput } from "./ChallengeInput";
import { RefereeNote } from "./RefereeNote";
import { TurnCard } from "./TurnCard";
import { VerdictCard } from "./VerdictCard";

interface Props {
  claim: string;
  entries: Entry[];
  status: string | null;
  error: string | null;
  running: boolean;
  recorded: boolean;
  canChallenge: boolean;
  onChallenge: (argument: string) => void;
  onReset: () => void;
}

interface RoundBlock {
  kind: "round";
  id: string;
  number: number;
  name: string;
  messages: { id: string; message: Message }[];
}

type Block =
  | RoundBlock
  | { kind: "verdict"; id: string; verdict: Verdict }
  | { kind: "referee"; id: string; referee: Referee };

/**
 * The stream arrives as a flat list of entries. Rounds, referee calls and verdicts
 * alternate — a long or challenged debate has several of each — so messages are
 * folded back into the round that was open when they arrived, and everything else
 * stays where it landed.
 */
function toBlocks(entries: Entry[]): Block[] {
  const blocks: Block[] = [];
  let open: RoundBlock | null = null;

  for (const entry of entries) {
    if (entry.kind === "round") {
      open = { kind: "round", id: entry.id, number: entry.number, name: entry.name, messages: [] };
      blocks.push(open);
    } else if (entry.kind === "verdict") {
      open = null;
      blocks.push({ kind: "verdict", id: entry.id, verdict: entry.verdict });
    } else if (entry.kind === "referee") {
      open = null;
      blocks.push({ kind: "referee", id: entry.id, referee: entry.referee });
    } else if (open && open.number === entry.message.round) {
      open.messages.push({ id: entry.id, message: entry.message });
    } else {
      // No round header for this turn (or the round changed under us): start one
      // from the turn itself rather than dropping it.
      open = {
        kind: "round",
        id: `r${entry.id}`,
        number: entry.message.round,
        name: entry.message.round_name,
        messages: [{ id: entry.id, message: entry.message }],
      };
      blocks.push(open);
    }
  }

  return blocks;
}

function RoundHeader({ number, name }: { number: number; name: string }) {
  return (
    <div className="mb-5 flex items-center gap-4">
      <span className="font-mono text-xs text-ink-faint">{String(number).padStart(2, "0")}</span>
      <h3 className="text-xs font-semibold tracking-[0.18em] text-ink-soft uppercase">{name}</h3>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}

export function DebateView({
  claim,
  entries,
  status,
  error,
  running,
  recorded,
  canChallenge,
  onChallenge,
  onReset,
}: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const blocks = toBlocks(entries);

  // Follow the stream, but only on structural changes — scrolling on every
  // character would fight the reader.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries.length, status]);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-12">
      <header className="mb-12 border-b border-line pb-8">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <p className="text-xs tracking-[0.18em] text-ink-faint uppercase">Claim under debate</p>
          {recorded ? (
            <span className="rounded-full border border-line px-2.5 py-0.5 text-xs tracking-[0.14em] text-ink-faint uppercase">
              recorded replay
            </span>
          ) : null}
        </div>
        <h2 className="text-2xl leading-snug font-semibold tracking-tight text-balance sm:text-3xl">
          {claim}
        </h2>
      </header>

      <div className="flex flex-col gap-10">
        {blocks.map((block) => {
          if (block.kind === "verdict") return <VerdictCard key={block.id} verdict={block.verdict} />;
          if (block.kind === "referee") return <RefereeNote key={block.id} referee={block.referee} />;

          const sequential = isSequentialRound(block.messages.map(({ message }) => message.kind));
          return (
            <section key={block.id}>
              <RoundHeader number={block.number} name={block.name} />
              <div
                className={
                  sequential ? "flex flex-col gap-4" : "grid gap-4 md:grid-cols-2 md:items-start"
                }
              >
                {block.messages.map(({ id, message }) => (
                  <TurnCard key={id} message={message} />
                ))}
              </div>
            </section>
          );
        })}

        {running && status ? (
          <div className="flex items-center gap-3 text-sm text-ink-faint">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-ink-faint" />
              <span className="relative inline-flex size-2 rounded-full bg-ink-soft" />
            </span>
            {status}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-xl border border-defender bg-surface px-5 py-4 text-sm text-ink">
            {error}
          </div>
        ) : null}

        {canChallenge && !running ? (
          <ChallengeInput onSubmit={onChallenge} disabled={running} />
        ) : null}

        {!running ? (
          <div>
            <button
              type="button"
              onClick={onReset}
              className="rounded-full border border-line px-6 py-2.5 text-sm font-medium text-ink-soft transition hover:border-ink-faint hover:text-ink"
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

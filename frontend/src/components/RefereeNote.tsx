import type { Referee } from "../types";

/**
 * The referee's call between rounds. Worth showing rather than hiding: it is the
 * only place the reader learns *why* the debate is still going, and it makes the
 * variable length legible instead of arbitrary.
 */
export function RefereeNote({ referee }: { referee: Referee }) {
  const { resolved, tension, note, rounds_left: roundsLeft } = referee;

  return (
    <div className="enter flex flex-col gap-1.5 rounded-xl border border-dashed border-line bg-raised px-5 py-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold tracking-[0.16em] text-ink-faint uppercase">
          Referee
        </span>
        <span className="text-xs tracking-[0.14em] text-ink-faint uppercase">
          {resolved ? "closing it" : `another round · ${roundsLeft} left`}
        </span>
      </div>
      {note ? <p className="text-sm leading-relaxed text-ink-soft">{note}</p> : null}
      {!resolved && tension ? (
        <p className="text-sm leading-relaxed text-ink">
          <span className="text-ink-faint">Still open: </span>
          {tension}
        </p>
      ) : null}
    </div>
  );
}

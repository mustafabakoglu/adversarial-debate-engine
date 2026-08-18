export type Speaker = "prosecutor" | "defender" | "user" | "judge";

export type TurnKind =
  | "opening"
  | "rebuttal"
  | "cross_question"
  | "cross_answer"
  | "clash"
  | "judge_question"
  | "bench_answer"
  | "closing"
  | "user_argument"
  | "challenge_response";

export type Winner = "prosecutor" | "defender" | "draw";

export interface Turn {
  round: number;
  round_name: string;
  speaker: Speaker;
  kind: TurnKind;
  text: string;
}

export interface Verdict {
  prosecutor_score: number;
  defender_score: number;
  winner: Winner;
  confidence: number;
  reasoning: string;
  strongest_argument: string;
  weakest_argument: string;
  unresolved_question: string;
}

/** The referee's call on whether the debate still has anything left in it. */
export interface Referee {
  resolved: boolean;
  tension: string;
  note: string;
  rounds_left: number;
}

/** Events emitted by the debate and challenge streams. */
export type DebateEvent =
  | {
      type: "session";
      session_id: string;
      claim: string;
      /** Set when the stream is a replay of a recorded debate rather than a live run. */
      recorded?: boolean;
      recorded_at?: string;
    }
  | { type: "round_start"; number: number; name: string }
  | { type: "status"; message: string }
  | { type: "turn_start"; round: number; round_name: string; speaker: Speaker; kind: TurnKind }
  | { type: "turn_delta"; text: string }
  | ({ type: "turn_end" } & Turn)
  | ({ type: "referee" } & Referee)
  | ({ type: "verdict" } & Verdict)
  | { type: "error"; message: string; recoverable: boolean }
  | { type: "done" };

/** A message in the transcript. `streaming` marks the one still being written. */
export interface Message extends Turn {
  streaming: boolean;
}

/** Verdicts and referee calls interleave with messages so a long debate reads in order. */
export type Entry =
  | { kind: "round"; id: string; number: number; name: string }
  | { kind: "message"; id: string; message: Message }
  | { kind: "referee"; id: string; referee: Referee }
  | { kind: "verdict"; id: string; verdict: Verdict };

export const KIND_LABEL: Record<TurnKind, string> = {
  opening: "opening",
  rebuttal: "rebuttal",
  cross_question: "question",
  cross_answer: "answer",
  clash: "going at it",
  judge_question: "question from the bench",
  bench_answer: "answering the judge",
  closing: "last word",
  user_argument: "your challenge",
  challenge_response: "answering you",
};

export const SPEAKER_LABEL: Record<Speaker, string> = {
  prosecutor: "Prosecutor",
  defender: "Defender",
  user: "You",
  judge: "Judge",
};

const SEQUENTIAL_KINDS: TurnKind[] = [
  "cross_question",
  "cross_answer",
  "clash",
  "user_argument",
  "judge_question",
];

/**
 * Rounds whose turns answer each other in sequence read as one column; the
 * simultaneous rounds sit side by side. Decided by what is in the round rather
 * than by its number, because the number of clash rounds is not fixed.
 */
export function isSequentialRound(kinds: TurnKind[]): boolean {
  return kinds.some((kind) => SEQUENTIAL_KINDS.includes(kind));
}

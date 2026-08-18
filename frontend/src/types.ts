export type Speaker = "prosecutor" | "defender";

export type TurnKind =
  | "opening"
  | "rebuttal"
  | "cross_question"
  | "cross_answer"
  | "closing";

export type Winner = Speaker | "draw";

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

/** Events emitted by GET /api/debate/stream. */
export type DebateEvent =
  | { type: "claim"; claim: string }
  | { type: "round_start"; number: number; name: string }
  | { type: "status"; message: string }
  | ({ type: "turn" } & Turn)
  | ({ type: "verdict" } & Verdict)
  | { type: "error"; message: string; recoverable: boolean }
  | { type: "done" };

export const KIND_LABEL: Record<TurnKind, string> = {
  opening: "Opening",
  rebuttal: "Rebuttal",
  cross_question: "Question",
  cross_answer: "Answer",
  closing: "Closing",
};

export const SPEAKER_LABEL: Record<Speaker, string> = {
  prosecutor: "Prosecutor",
  defender: "Defender",
};

"""Request and response models for the debate API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .config import MAX_ARGUMENT_LENGTH, MAX_CLAIM_LENGTH, MIN_CLAIM_LENGTH

# "user" appears only in challenge rounds, where the person who submitted the
# claim argues back. They are never scored — see the judge prompt.
Speaker = Literal["prosecutor", "defender", "user", "judge"]
TurnKind = Literal[
    "opening",
    "rebuttal",
    "cross_question",
    "cross_answer",
    "clash",
    "judge_question",
    "bench_answer",
    "closing",
    "user_argument",
    "challenge_response",
]
Winner = Literal["prosecutor", "defender", "draw"]


class DebateRequest(BaseModel):
    claim: str = Field(..., description="The claim to be debated.")

    @field_validator("claim")
    @classmethod
    def _validate_claim(cls, value: str) -> str:
        claim = " ".join(value.split())
        if len(claim) < MIN_CLAIM_LENGTH:
            raise ValueError(f"claim must be at least {MIN_CLAIM_LENGTH} characters")
        if len(claim) > MAX_CLAIM_LENGTH:
            raise ValueError(f"claim must be at most {MAX_CLAIM_LENGTH} characters")
        return claim


class ChallengeRequest(BaseModel):
    """A counter-argument from the person who submitted the claim."""

    argument: str = Field(..., description="The user's own argument against the verdict.")

    @field_validator("argument")
    @classmethod
    def _validate_argument(cls, value: str) -> str:
        argument = " ".join(value.split())
        if len(argument) < MIN_CLAIM_LENGTH:
            raise ValueError(f"argument must be at least {MIN_CLAIM_LENGTH} characters")
        if len(argument) > MAX_ARGUMENT_LENGTH:
            raise ValueError(f"argument must be at most {MAX_ARGUMENT_LENGTH} characters")
        return argument


class Turn(BaseModel):
    round: int
    round_name: str
    speaker: Speaker
    kind: TurnKind
    text: str


class Round(BaseModel):
    number: int
    name: str
    turns: list[Turn]


class Verdict(BaseModel):
    prosecutor_score: int
    defender_score: int
    winner: Winner
    confidence: int
    reasoning: str
    strongest_argument: str
    weakest_argument: str
    unresolved_question: str


class DebateResponse(BaseModel):
    claim: str
    rounds: list[Round]
    prosecutor_score: int
    defender_score: int
    winner: Winner
    confidence: int
    reasoning: str
    strongest_argument: str
    weakest_argument: str
    unresolved_question: str


# JSON Schema handed to the model for the verdict. Structured outputs require
# every object to declare additionalProperties: false, and do not support
# numeric range constraints, so scores are clamped in Python instead.
VERDICT_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "prosecutor_score": {
            "type": "integer",
            "description": "Quality of PROSECUTOR's argumentation, 0-100.",
        },
        "defender_score": {
            "type": "integer",
            "description": "Quality of DEFENDER's argumentation, 0-100.",
        },
        "winner": {
            "type": "string",
            "enum": ["prosecutor", "defender", "draw"],
            "description": "Who argued better. Not who is factually right.",
        },
        "confidence": {
            "type": "integer",
            "description": "How certain the verdict is, 0-100. Level debates score low.",
        },
        "reasoning": {
            "type": "string",
            "description": "Two or three sentences justifying the verdict.",
        },
        "strongest_argument": {
            "type": "string",
            "description": "The strongest argument in the debate, quoted, with the side attributed.",
        },
        "weakest_argument": {
            "type": "string",
            "description": "The weakest argument in the debate, quoted, with the side attributed.",
        },
        "unresolved_question": {
            "type": "string",
            "description": "The question neither side settled that would most change the outcome.",
        },
    },
    "required": [
        "prosecutor_score",
        "defender_score",
        "winner",
        "confidence",
        "reasoning",
        "strongest_argument",
        "weakest_argument",
        "unresolved_question",
    ],
    "additionalProperties": False,
}


# The referee's decision after each open-clash round. Same structured-output
# constraints as the verdict: no numeric ranges, additionalProperties false.
REFEREE_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "resolved": {
            "type": "boolean",
            "description": "True if the disagreement is exhausted and the debate should be closed.",
        },
        "tension": {
            "type": "string",
            "description": (
                "If not resolved, the one specific thing they are disagreeing about right now, "
                "as a single sentence in the language of the debate. Empty if resolved."
            ),
        },
        "note": {
            "type": "string",
            "description": (
                "One short sentence for the audience explaining why the debate continues or "
                "stops, in the language of the debate."
            ),
        },
    },
    "required": ["resolved", "tension", "note"],
    "additionalProperties": False,
}


class RefereeDecision(BaseModel):
    resolved: bool
    tension: str
    note: str


# The judge's optional question before the closing statements.
BENCH_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "ask": {
            "type": "boolean",
            "description": "True only if the answer would actually change how you score this.",
        },
        "target": {
            "type": "string",
            "enum": ["prosecutor", "defender", "both"],
            "description": "Who has to answer. Empty of meaning when ask is false.",
        },
        "question": {
            "type": "string",
            "description": (
                "The question, in the language of the debate, with at most two sentences of "
                "framing. Empty if ask is false."
            ),
        },
    },
    "required": ["ask", "target", "question"],
    "additionalProperties": False,
}


class BenchQuestion(BaseModel):
    ask: bool
    target: Literal["prosecutor", "defender", "both"]
    question: str

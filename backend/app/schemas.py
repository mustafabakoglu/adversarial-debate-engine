"""Request and response models for the debate API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .config import MAX_CLAIM_LENGTH, MIN_CLAIM_LENGTH

Speaker = Literal["prosecutor", "defender"]
TurnKind = Literal["opening", "rebuttal", "cross_question", "cross_answer", "closing"]
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

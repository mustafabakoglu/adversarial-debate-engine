"""Debate orchestration.

The engine runs a fixed four-round protocol and then a verdict:

    Round 1  Opening arguments      both sides, in parallel, neither sees the other
    Round 2  Rebuttal               both sides, in parallel, each answers the opening
    Round 3  Cross examination      sequential: P asks -> D answers -> D asks -> P answers
    Round 4  Closing arguments      both sides, in parallel, full transcript visible
    Verdict  Judge                  structured output

`run` is an async generator of events so the same code path serves both the
streaming endpoint and the plain POST endpoint.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from anthropic import AsyncAnthropic

from . import config
from .prompts import (
    CLOSING_INSTRUCTION,
    CROSS_ANSWER_INSTRUCTION,
    CROSS_QUESTION_INSTRUCTION,
    DEFENDER_SYSTEM,
    JUDGE_SYSTEM,
    OPENING_INSTRUCTION,
    PROSECUTOR_SYSTEM,
    REBUTTAL_INSTRUCTION,
)
from .schemas import VERDICT_JSON_SCHEMA, Round, Turn, Verdict

logger = logging.getLogger(__name__)

ROUND_NAMES = {
    1: "Opening Arguments",
    2: "Rebuttal",
    3: "Cross Examination",
    4: "Final Arguments",
}

SPEAKER_LABEL = {"prosecutor": "PROSECUTOR", "defender": "DEFENDER"}

SYSTEM_FOR = {"prosecutor": PROSECUTOR_SYSTEM, "defender": DEFENDER_SYSTEM}


class DebateError(RuntimeError):
    """Raised when the debate cannot be completed."""


class ModelRefusal(DebateError):
    """The model declined to produce a turn."""


def _extract_text(message: Any) -> str:
    """Collect the text blocks of a response, ignoring thinking blocks."""
    parts = [block.text for block in message.content if getattr(block, "type", None) == "text"]
    return "".join(parts).strip()


def _loads_lenient(raw: str) -> dict:
    """Parse JSON that may be wrapped in prose or a fenced code block."""
    text = raw.strip()
    fence = "```"
    if text.startswith(fence):
        segments = text.split(fence)
        if len(segments) >= 2:
            text = segments[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise DebateError("the judge did not return parseable JSON")
        return json.loads(text[start : end + 1])


def _clamp(value: Any, low: int = 0, high: int = 100, default: int = 50) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


class DebateEngine:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        # Older SDK releases do not accept output_config; detected on first use.
        self._supports_output_config = True

    async def close(self) -> None:
        await self._client.close()

    # -- model plumbing ----------------------------------------------------

    async def _create(self, **params: Any) -> Any:
        """Call the Messages API, degrading gracefully on an older SDK."""
        if not self._supports_output_config:
            params.pop("output_config", None)
        try:
            return await self._client.messages.create(**params)
        except TypeError as exc:
            if "output_config" not in params or "output_config" not in str(exc):
                raise
            logger.warning("installed anthropic SDK rejects output_config; continuing without it")
            self._supports_output_config = False
            params.pop("output_config", None)
            return await self._client.messages.create(**params)

    async def _speak(self, speaker: str, context: str) -> str:
        message = await self._create(
            model=self._model,
            max_tokens=config.DEBATER_MAX_TOKENS,
            system=SYSTEM_FOR[speaker],
            output_config={"effort": config.DEBATER_EFFORT},
            messages=[{"role": "user", "content": context}],
        )
        if message.stop_reason == "refusal":
            raise ModelRefusal(
                "The model declined to argue this claim. Try phrasing it as a debatable "
                "proposition rather than a request about a restricted topic."
            )
        text = _extract_text(message)
        if not text:
            raise DebateError(SPEAKER_LABEL[speaker] + " returned an empty turn")
        return text

    # -- context building --------------------------------------------------

    @staticmethod
    def _render_transcript(turns: list[Turn]) -> str:
        if not turns:
            return "(no turns yet)"
        lines: list[str] = []
        for turn in turns:
            lines.append(
                "[Round {n} - {name}] {who}:".format(
                    n=turn.round, name=turn.round_name, who=SPEAKER_LABEL[turn.speaker]
                )
            )
            lines.append(turn.text)
            lines.append("")
        return "\n".join(lines).strip()

    def _context(self, claim: str, turns: list[Turn], instruction: str) -> str:
        return (
            "CLAIM UNDER DEBATE:\n"
            + claim
            + "\n\nTRANSCRIPT SO FAR:\n"
            + self._render_transcript(turns)
            + "\n\nYOUR TASK:\n"
            + instruction
        )

    # -- rounds ------------------------------------------------------------

    async def _parallel_round(
        self,
        claim: str,
        number: int,
        instruction: str,
        kind: str,
        visible: list[Turn],
    ) -> list[Turn]:
        """Both sides speak from the same visible transcript, concurrently."""
        context = self._context(claim, visible, instruction)
        prosecutor_text, defender_text = await asyncio.gather(
            self._speak("prosecutor", context),
            self._speak("defender", context),
        )
        return [
            Turn(
                round=number,
                round_name=ROUND_NAMES[number],
                speaker="prosecutor",
                kind=kind,  # type: ignore[arg-type]
                text=prosecutor_text,
            ),
            Turn(
                round=number,
                round_name=ROUND_NAMES[number],
                speaker="defender",
                kind=kind,  # type: ignore[arg-type]
                text=defender_text,
            ),
        ]

    async def _judge(self, claim: str, turns: list[Turn]) -> Verdict:
        context = (
            "CLAIM THAT WAS DEBATED:\n"
            + claim
            + "\n\nFULL TRANSCRIPT:\n"
            + self._render_transcript(turns)
            + "\n\nYOUR TASK:\nScore both sides and return the verdict."
        )
        message = await self._create(
            model=self._model,
            max_tokens=config.JUDGE_MAX_TOKENS,
            system=JUDGE_SYSTEM,
            output_config={
                "effort": config.JUDGE_EFFORT,
                "format": {"type": "json_schema", "schema": VERDICT_JSON_SCHEMA},
            },
            messages=[{"role": "user", "content": context}],
        )
        if message.stop_reason == "refusal":
            raise ModelRefusal("The model declined to judge this debate.")

        data = _loads_lenient(_extract_text(message))

        prosecutor_score = _clamp(data.get("prosecutor_score"))
        defender_score = _clamp(data.get("defender_score"))
        winner = data.get("winner")
        if winner not in ("prosecutor", "defender", "draw"):
            winner = "draw"

        # Guard against a verdict that contradicts its own scores, which would
        # read as a bug on screen.
        if winner == "prosecutor" and defender_score > prosecutor_score:
            winner = "defender"
        elif winner == "defender" and prosecutor_score > defender_score:
            winner = "prosecutor"
        elif winner != "draw" and prosecutor_score == defender_score:
            winner = "draw"

        return Verdict(
            prosecutor_score=prosecutor_score,
            defender_score=defender_score,
            winner=winner,  # type: ignore[arg-type]
            confidence=_clamp(data.get("confidence")),
            reasoning=str(data.get("reasoning") or "").strip(),
            strongest_argument=str(data.get("strongest_argument") or "").strip(),
            weakest_argument=str(data.get("weakest_argument") or "").strip(),
            unresolved_question=str(data.get("unresolved_question") or "").strip(),
        )

    # -- public API --------------------------------------------------------

    async def run(self, claim: str) -> AsyncIterator[dict]:
        """Yield debate events in order, finishing with the verdict."""
        turns: list[Turn] = []

        def emit_round(number: int) -> dict:
            return {"type": "round_start", "number": number, "name": ROUND_NAMES[number]}

        def emit_turn(turn: Turn) -> dict:
            return {"type": "turn", **turn.model_dump()}

        # Round 1 - openings, neither side sees the other.
        yield emit_round(1)
        yield {"type": "status", "message": "Both sides preparing opening arguments..."}
        opening = await self._parallel_round(claim, 1, OPENING_INSTRUCTION, "opening", [])
        turns.extend(opening)
        for turn in opening:
            yield emit_turn(turn)

        # Round 2 - rebuttals, both answering the openings.
        yield emit_round(2)
        yield {"type": "status", "message": "Analyzing opponent's argument..."}
        rebuttal = await self._parallel_round(
            claim, 2, REBUTTAL_INSTRUCTION, "rebuttal", list(turns)
        )
        turns.extend(rebuttal)
        for turn in rebuttal:
            yield emit_turn(turn)

        # Round 3 - cross examination, strictly sequential.
        yield emit_round(3)
        for asker, answerer in (("prosecutor", "defender"), ("defender", "prosecutor")):
            yield {
                "type": "status",
                "message": SPEAKER_LABEL[asker] + " preparing a question...",
            }
            question_text = await self._speak(
                asker, self._context(claim, turns, CROSS_QUESTION_INSTRUCTION)
            )
            question = Turn(
                round=3,
                round_name=ROUND_NAMES[3],
                speaker=asker,  # type: ignore[arg-type]
                kind="cross_question",
                text=question_text,
            )
            turns.append(question)
            yield emit_turn(question)

            yield {
                "type": "status",
                "message": SPEAKER_LABEL[answerer] + " must answer directly...",
            }
            answer_text = await self._speak(
                answerer, self._context(claim, turns, CROSS_ANSWER_INSTRUCTION)
            )
            answer = Turn(
                round=3,
                round_name=ROUND_NAMES[3],
                speaker=answerer,  # type: ignore[arg-type]
                kind="cross_answer",
                text=answer_text,
            )
            turns.append(answer)
            yield emit_turn(answer)

        # Round 4 - closings.
        yield emit_round(4)
        yield {"type": "status", "message": "Both sides preparing final arguments..."}
        closing = await self._parallel_round(claim, 4, CLOSING_INSTRUCTION, "closing", list(turns))
        turns.extend(closing)
        for turn in closing:
            yield emit_turn(turn)

        # Verdict.
        yield {"type": "status", "message": "Judge reviewing the transcript..."}
        verdict = await self._judge(claim, turns)
        yield {"type": "verdict", **verdict.model_dump()}
        yield {"type": "done"}


def group_rounds(turns: list[Turn]) -> list[Round]:
    """Group a flat turn list into the rounds structure of the REST response."""
    rounds: list[Round] = []
    for turn in turns:
        if not rounds or rounds[-1].number != turn.round:
            rounds.append(Round(number=turn.round, name=turn.round_name, turns=[]))
        rounds[-1].turns.append(turn)
    return rounds

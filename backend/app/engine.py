"""Debate orchestration.

The engine runs a fixed opening, then as many rounds as the argument earns:

    Round 1   Opening arguments     each side writes without seeing the other
    Round 2   Rebuttal              each side must take the opening apart
    Round 3   Cross examination     P asks -> D answers -> D asks -> P answers
    Round 4+  Open clash            only while the referee says it is still live
    Bench     Judge's question      optional: the judge asks, they answer
    Last      Last word             closing statements, full transcript visible
    Verdict   Judge                 structured output
    Then      Challenge             the user argues back; both sides must answer
                                    them specifically, then a fresh verdict

The number of rounds is not fixed, and that is the point. After cross examination
a referee reads the transcript and decides whether the disagreement is exhausted
or has merely moved onto a sharper point; if it is still live, both sides get
another round aimed at that exact tension, and the referee looks again. A debate
that resolves quickly closes in four rounds; one where neither side will give way
runs to MAX_DEBATE_ROUNDS.

`run` and `challenge` are async generators of events, so the same code path serves
the streaming endpoint and the plain POST endpoint.

Rounds 1, 2 and the last word are logically simultaneous - neither side may react
to the other - and that is enforced by controlling *what transcript each side can
see*, not by issuing the calls concurrently. Clash rounds are the opposite: the
second speaker must see what was just said, because answering it is the whole
instruction. Turns are always produced one at a time, so the stream reads the way
an exchange reads.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Iterable

from . import config
from .errors import DebateError
from .prompts import (
    BENCH_ANSWER_INSTRUCTION,
    BENCH_INSTRUCTION,
    BENCH_SYSTEM,
    CLASH_INSTRUCTION,
    CLOSING_INSTRUCTION,
    CROSS_ANSWER_INSTRUCTION,
    CROSS_QUESTION_INSTRUCTION,
    DEFENDER_SYSTEM,
    JUDGE_SYSTEM,
    OPENING_INSTRUCTION,
    PROSECUTOR_SYSTEM,
    REBUTTAL_INSTRUCTION,
    REFEREE_INSTRUCTION,
    REFEREE_SYSTEM,
    USER_CHALLENGE_INSTRUCTION,
)
from .providers import Provider
from .schemas import (
    BENCH_JSON_SCHEMA,
    REFEREE_JSON_SCHEMA,
    VERDICT_JSON_SCHEMA,
    BenchQuestion,
    RefereeDecision,
    Round,
    Turn,
    Verdict,
)

logger = logging.getLogger(__name__)

OPENING_ROUND_NAME = "Opening Arguments"
REBUTTAL_ROUND_NAME = "Rebuttal"
CROSS_ROUND_NAME = "Cross Examination"
BENCH_ROUND_NAME = "From the Bench"
CLOSING_ROUND_NAME = "Last Word"

SPEAKER_LABEL = {
    "prosecutor": "PROSECUTOR",
    "defender": "DEFENDER",
    "user": "THE PERSON WHO MADE THE CLAIM",
    "judge": "THE JUDGE",
}

SYSTEM_FOR = {"prosecutor": PROSECUTOR_SYSTEM, "defender": DEFENDER_SYSTEM}


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
            raise DebateError("the model did not return parseable JSON")
        return json.loads(text[start : end + 1])


def _plain(text: str) -> str:
    """Strip the markdown emphasis the models are told not to use.

    A prompt rule gets obeyed most of the time, and "most of the time" is not good
    enough for something that shows up as literal asterisks in the middle of a
    sentence. Deleting the character costs nothing: the debaters are speaking, so
    an asterisk never carries meaning here.
    """
    return text.replace("*", "")


def _clamp(value: Any, low: int = 0, high: int = 100, default: int = 50) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


class DebateEngine:
    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._provider.model

    async def close(self) -> None:
        await self._provider.close()

    # -- context building --------------------------------------------------

    @staticmethod
    def _render_transcript(turns: Iterable[Turn]) -> str:
        lines: list[str] = []
        for turn in turns:
            lines.append(
                "[Round {n} - {name}] {who}:".format(
                    n=turn.round, name=turn.round_name, who=SPEAKER_LABEL[turn.speaker]
                )
            )
            lines.append(turn.text)
            lines.append("")
        return "\n".join(lines).strip() or "(no turns yet)"

    def _context(self, claim: str, turns: Iterable[Turn], instruction: str) -> str:
        return (
            "CLAIM UNDER DEBATE:\n"
            + claim
            + "\n\nTRANSCRIPT SO FAR:\n"
            + self._render_transcript(turns)
            + "\n\nYOUR TASK:\n"
            + instruction
        )

    # -- streaming a single turn -------------------------------------------

    async def _stream_turn(
        self,
        *,
        claim: str,
        visible: list[Turn],
        speaker: str,
        kind: str,
        number: int,
        name: str,
        instruction: str,
    ) -> AsyncIterator[dict]:
        """Emit turn_start, a run of turn_delta events, then turn_end."""
        yield {
            "type": "turn_start",
            "round": number,
            "round_name": name,
            "speaker": speaker,
            "kind": kind,
        }

        chunks: list[str] = []
        async for raw_fragment in self._provider.stream(
            system=SYSTEM_FOR[speaker],
            user=self._context(claim, visible, instruction),
            max_tokens=config.DEBATER_MAX_TOKENS,
            effort=config.DEBATER_EFFORT,
        ):
            fragment = _plain(raw_fragment)
            if not fragment:
                continue
            chunks.append(fragment)
            yield {"type": "turn_delta", "text": fragment}

        text = "".join(chunks).strip()
        if not text:
            raise DebateError(SPEAKER_LABEL[speaker] + " returned an empty turn")

        turn = Turn(
            round=number,
            round_name=name,
            speaker=speaker,  # type: ignore[arg-type]
            kind=kind,  # type: ignore[arg-type]
            text=text,
        )
        yield {"type": "turn_end", **turn.model_dump()}

    # -- referee -----------------------------------------------------------

    async def _referee(self, claim: str, turns: list[Turn], rounds_left: int) -> RefereeDecision:
        """Decide whether the debate still has somewhere to go."""
        context = (
            "CLAIM UNDER DEBATE:\n"
            + claim
            + "\n\nTRANSCRIPT SO FAR:\n"
            + self._render_transcript(turns)
            + f"\n\nRounds still available if you continue: {rounds_left}."
            + "\n\nYOUR TASK:\n"
            + REFEREE_INSTRUCTION
        )
        try:
            raw = await self._provider.complete(
                system=REFEREE_SYSTEM,
                user=context,
                max_tokens=config.REFEREE_MAX_TOKENS,
                effort=config.REFEREE_EFFORT,
                json_schema=REFEREE_JSON_SCHEMA,
            )
            data = _loads_lenient(raw)
        except DebateError:
            # The referee is a pacing decision, not the product. If it fails, close
            # the debate rather than losing a transcript the reader can already see.
            logger.warning("referee call failed; closing the debate", exc_info=True)
            return RefereeDecision(resolved=True, tension="", note="")

        tension = _plain(str(data.get("tension") or "")).strip()
        resolved = bool(data.get("resolved")) or not tension
        return RefereeDecision(
            resolved=resolved,
            tension=tension,
            note=_plain(str(data.get("note") or "")).strip(),
        )

    # -- the bench ---------------------------------------------------------

    async def _bench(self, claim: str, turns: list[Turn]) -> BenchQuestion:
        """Ask the judge whether it wants anything before the closing statements."""
        context = (
            "CLAIM UNDER DEBATE:\n"
            + claim
            + "\n\nTRANSCRIPT SO FAR:\n"
            + self._render_transcript(turns)
            + "\n\nYOUR TASK:\n"
            + BENCH_INSTRUCTION
        )
        try:
            raw = await self._provider.complete(
                system=BENCH_SYSTEM,
                user=context,
                max_tokens=config.REFEREE_MAX_TOKENS,
                effort=config.JUDGE_EFFORT,
                json_schema=BENCH_JSON_SCHEMA,
            )
            data = _loads_lenient(raw)
        except DebateError:
            # Optional by design, so a failure here costs the debate nothing.
            logger.warning("bench call failed; skipping the judge's question", exc_info=True)
            return BenchQuestion(ask=False, target="both", question="")

        question = _plain(str(data.get("question") or "")).strip()
        target = data.get("target")
        if target not in ("prosecutor", "defender", "both"):
            target = "both"
        return BenchQuestion(
            ask=bool(data.get("ask")) and bool(question),
            target=target,  # type: ignore[arg-type]
            question=question,
        )

    # -- verdict -----------------------------------------------------------

    async def _judge(self, claim: str, turns: list[Turn]) -> Verdict:
        context = (
            "CLAIM THAT WAS DEBATED:\n"
            + claim
            + "\n\nFULL TRANSCRIPT:\n"
            + self._render_transcript(turns)
            + "\n\nYOUR TASK:\nScore both sides and return the verdict."
        )
        raw = await self._provider.complete(
            system=JUDGE_SYSTEM,
            user=context,
            max_tokens=config.JUDGE_MAX_TOKENS,
            effort=config.JUDGE_EFFORT,
            json_schema=VERDICT_JSON_SCHEMA,
        )
        data = _loads_lenient(raw)

        prosecutor_score = _clamp(data.get("prosecutor_score"))
        defender_score = _clamp(data.get("defender_score"))
        winner = data.get("winner")
        if winner not in ("prosecutor", "defender", "draw"):
            winner = "draw"

        # Guard against a verdict that contradicts its own scores, which would read
        # as a bug on screen.
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
            reasoning=_plain(str(data.get("reasoning") or "")).strip(),
            strongest_argument=_plain(str(data.get("strongest_argument") or "")).strip(),
            weakest_argument=_plain(str(data.get("weakest_argument") or "")).strip(),
            unresolved_question=_plain(str(data.get("unresolved_question") or "")).strip(),
        )

    # -- public API --------------------------------------------------------

    async def run(self, claim: str) -> AsyncIterator[dict]:
        """Run the debate to whatever length it earns, then the first verdict."""
        turns: list[Turn] = []

        async def play(
            number: int,
            name: str,
            kind: str,
            instruction: str,
            speakers: tuple[str, ...],
            frozen: bool,
        ) -> AsyncIterator[dict]:
            # `frozen` means the sides argue simultaneously: every speaker in the
            # round sees the same snapshot, so nobody can react to a sibling turn
            # produced moments earlier. Otherwise each speaker sees live state.
            snapshot = list(turns) if frozen else None
            for speaker in speakers:
                async for event in self._stream_turn(
                    claim=claim,
                    visible=snapshot if snapshot is not None else list(turns),
                    speaker=speaker,
                    kind=kind,
                    number=number,
                    name=name,
                    instruction=instruction,
                ):
                    if event["type"] == "turn_end":
                        turns.append(Turn(**{k: v for k, v in event.items() if k != "type"}))
                    yield event

        both = ("prosecutor", "defender")

        yield {"type": "round_start", "number": 1, "name": OPENING_ROUND_NAME}
        async for event in play(1, OPENING_ROUND_NAME, "opening", OPENING_INSTRUCTION, both, True):
            yield event

        yield {"type": "round_start", "number": 2, "name": REBUTTAL_ROUND_NAME}
        async for event in play(
            2, REBUTTAL_ROUND_NAME, "rebuttal", REBUTTAL_INSTRUCTION, both, True
        ):
            yield event

        yield {"type": "round_start", "number": 3, "name": CROSS_ROUND_NAME}
        for asker, answerer in (("prosecutor", "defender"), ("defender", "prosecutor")):
            async for event in play(
                3, CROSS_ROUND_NAME, "cross_question", CROSS_QUESTION_INSTRUCTION, (asker,), False
            ):
                yield event
            async for event in play(
                3, CROSS_ROUND_NAME, "cross_answer", CROSS_ANSWER_INSTRUCTION, (answerer,), False
            ):
                yield event

        # Open clash rounds, for as long as the referee says the fight is real. One
        # round is always reserved for the closing statements.
        number = 3
        clash = 0
        while number + 2 < config.MAX_DEBATE_ROUNDS:
            yield {"type": "status", "message": "Referee checking whether this is settled"}
            rounds_left = config.MAX_DEBATE_ROUNDS - 1 - number
            decision = await self._referee(claim, turns, rounds_left)
            yield {
                "type": "referee",
                "resolved": decision.resolved,
                "tension": decision.tension,
                "note": decision.note,
                "rounds_left": rounds_left,
            }
            if decision.resolved:
                break

            clash += 1
            number += 1
            name = f"Open Clash {clash}"
            yield {"type": "round_start", "number": number, "name": name}
            # Whoever answered last in the previous round speaks first here, so the
            # same side does not always get the last word before the referee looks.
            order = both if clash % 2 else tuple(reversed(both))
            async for event in play(
                number,
                name,
                "clash",
                CLASH_INSTRUCTION.format(focus=decision.tension),
                order,
                False,
            ):
                yield event

        yield {"type": "status", "message": "The judge may have a question"}
        bench = await self._bench(claim, turns)
        if bench.ask:
            number += 1
            yield {"type": "round_start", "number": number, "name": BENCH_ROUND_NAME}
            question = Turn(
                round=number,
                round_name=BENCH_ROUND_NAME,
                speaker="judge",
                kind="judge_question",
                text=bench.question,
            )
            turns.append(question)
            yield {"type": "turn_end", **question.model_dump()}

            # Both answer the same question without seeing each other's answer, so
            # neither can shelter behind the other's concession.
            answerers = both if bench.target == "both" else (bench.target,)
            async for event in play(
                number, BENCH_ROUND_NAME, "bench_answer", BENCH_ANSWER_INSTRUCTION, answerers, True
            ):
                yield event

        number += 1
        yield {"type": "round_start", "number": number, "name": CLOSING_ROUND_NAME}
        async for event in play(
            number, CLOSING_ROUND_NAME, "closing", CLOSING_INSTRUCTION, both, True
        ):
            yield event

        yield {"type": "status", "message": "Judge reviewing the transcript"}
        verdict = await self._judge(claim, turns)
        yield {"type": "verdict", **verdict.model_dump()}
        yield {"type": "done"}

    async def challenge(self, claim: str, prior: list[Turn], argument: str) -> AsyncIterator[dict]:
        """Take the user's counter-argument, make both sides answer it, re-judge."""
        turns = list(prior)
        number = max((turn.round for turn in turns), default=0) + 1
        index = sum(1 for turn in turns if turn.kind == "user_argument") + 1
        name = f"Challenge {index}"

        yield {"type": "round_start", "number": number, "name": name}

        user_turn = Turn(
            round=number, round_name=name, speaker="user", kind="user_argument", text=argument
        )
        turns.append(user_turn)
        yield {"type": "turn_end", **user_turn.model_dump()}

        # Both sides answer the same challenge, neither seeing the other's answer.
        frozen = list(turns)
        for speaker in ("prosecutor", "defender"):
            async for event in self._stream_turn(
                claim=claim,
                visible=frozen,
                speaker=speaker,
                kind="challenge_response",
                number=number,
                name=name,
                instruction=USER_CHALLENGE_INSTRUCTION,
            ):
                if event["type"] == "turn_end":
                    turns.append(Turn(**{k: v for k, v in event.items() if k != "type"}))
                yield event

        yield {"type": "status", "message": "Judge re-reviewing with your argument included"}
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

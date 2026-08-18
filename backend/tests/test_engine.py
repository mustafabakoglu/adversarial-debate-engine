"""The debate protocol: how long a debate runs and what shape it has."""

from __future__ import annotations

import pytest

from app import config
from app.engine import DebateEngine, group_rounds
from app.schemas import Turn
from tests.conftest import StubProvider

CLAIM = "Universite diplomasi artik gereksiz."


async def collect(provider: StubProvider) -> dict:
    rounds: list[tuple[int, str]] = []
    turns: list[Turn] = []
    referees: list[dict] = []
    deltas: list[str] = []
    verdict: dict | None = None

    async for event in DebateEngine(provider).run(CLAIM):
        if event["type"] == "round_start":
            rounds.append((event["number"], event["name"]))
        elif event["type"] == "turn_delta":
            deltas.append(event["text"])
        elif event["type"] == "turn_end":
            turns.append(Turn(**{k: v for k, v in event.items() if k != "type"}))
        elif event["type"] == "referee":
            referees.append(event)
        elif event["type"] == "verdict":
            verdict = event

    return {
        "rounds": rounds,
        "turns": turns,
        "referees": referees,
        "deltas": deltas,
        "verdict": verdict,
    }


@pytest.mark.asyncio
async def test_shortest_debate_is_four_rounds():
    """A referee that says it is settled closes the debate immediately."""
    result = await collect(StubProvider(unresolved_rounds=0))

    assert [name for _, name in result["rounds"]] == [
        "Opening Arguments",
        "Rebuttal",
        "Cross Examination",
        "Last Word",
    ]
    assert result["verdict"] is not None
    # Opening 2, rebuttal 2, cross examination 4, last word 2.
    assert len(result["turns"]) == 10


@pytest.mark.asyncio
async def test_live_disagreement_earns_extra_rounds():
    result = await collect(StubProvider(unresolved_rounds=2))

    names = [name for _, name in result["rounds"]]
    assert names == [
        "Opening Arguments",
        "Rebuttal",
        "Cross Examination",
        "Open Clash 1",
        "Open Clash 2",
        "Last Word",
    ]
    # Every clash round is preceded by a referee call the reader can see, plus the
    # one that ended it.
    assert len(result["referees"]) == 3
    assert result["referees"][0]["resolved"] is False
    assert result["referees"][-1]["resolved"] is True


@pytest.mark.asyncio
async def test_clash_rounds_alternate_who_speaks_first():
    result = await collect(StubProvider(unresolved_rounds=2))
    clashes: dict[int, list[str]] = {}
    for turn in result["turns"]:
        if turn.kind == "clash":
            clashes.setdefault(turn.round, []).append(turn.speaker)

    first_speakers = [speakers[0] for _, speakers in sorted(clashes.items())]
    assert first_speakers == ["prosecutor", "defender"]


@pytest.mark.asyncio
async def test_round_cap_holds_when_nobody_gives_way():
    """The referee is not allowed to run the debate forever."""
    result = await collect(StubProvider(unresolved_rounds=99, bench_ask=True))

    numbers = [number for number, _ in result["rounds"]]
    assert max(numbers) == config.MAX_DEBATE_ROUNDS
    assert result["rounds"][-1][1] == "Last Word"
    assert result["rounds"][-2][1] == "From the Bench"


@pytest.mark.asyncio
async def test_bench_question_is_answered_by_both_sides():
    result = await collect(StubProvider(bench_ask=True))

    bench = [turn for turn in result["turns"] if turn.round_name == "From the Bench"]
    assert [(turn.speaker, turn.kind) for turn in bench] == [
        ("judge", "judge_question"),
        ("prosecutor", "bench_answer"),
        ("defender", "bench_answer"),
    ]
    # The bench round sits between the argument and the closing statements.
    assert [name for _, name in result["rounds"]][-2:] == ["From the Bench", "Last Word"]


@pytest.mark.asyncio
async def test_bench_question_can_target_one_side():
    result = await collect(StubProvider(bench_ask=True, bench_target="defender"))

    answers = [turn.speaker for turn in result["turns"] if turn.kind == "bench_answer"]
    assert answers == ["defender"]


@pytest.mark.asyncio
async def test_silent_bench_adds_no_round():
    result = await collect(StubProvider(bench_ask=False))

    assert "From the Bench" not in [name for _, name in result["rounds"]]
    assert not [turn for turn in result["turns"] if turn.kind == "judge_question"]


@pytest.mark.asyncio
async def test_asterisks_are_stripped_but_emoji_survive():
    result = await collect(StubProvider(bench_ask=True))

    assert not any("*" in turn.text for turn in result["turns"])
    assert not any("*" in delta for delta in result["deltas"])
    assert any("🙂" in turn.text for turn in result["turns"])

    verdict = result["verdict"]
    assert verdict is not None
    for field in ("reasoning", "strongest_argument", "weakest_argument", "unresolved_question"):
        assert "*" not in verdict[field]


@pytest.mark.asyncio
async def test_referee_failure_closes_the_debate_instead_of_breaking_it():
    class RefereeFails(StubProvider):
        async def complete(self, *, system, user, max_tokens, effort=None, json_schema=None):
            from app.errors import DebateError

            if "resolved" in set((json_schema or {}).get("properties", {})):
                raise DebateError("provider is having a day")
            return await super().complete(
                system=system,
                user=user,
                max_tokens=max_tokens,
                effort=effort,
                json_schema=json_schema,
            )

    result = await collect(RefereeFails())

    assert [name for _, name in result["rounds"]][-1] == "Last Word"
    assert result["verdict"] is not None


@pytest.mark.asyncio
async def test_verdict_winner_is_reconciled_with_its_own_scores():
    """A winner whose score is lower than the loser's would read as a bug."""
    contradictory = dict(
        prosecutor_score=40,
        defender_score=80,
        winner="prosecutor",
        confidence=90,
        reasoning="r",
        strongest_argument="s",
        weakest_argument="w",
        unresolved_question="u",
    )
    result = await collect(StubProvider(verdict=contradictory))
    assert result["verdict"]["winner"] == "defender"

    level = dict(contradictory, prosecutor_score=70, defender_score=70, winner="defender")
    result = await collect(StubProvider(verdict=level))
    assert result["verdict"]["winner"] == "draw"


@pytest.mark.asyncio
async def test_challenge_round_makes_both_sides_answer_the_user():
    provider = StubProvider()
    engine = DebateEngine(provider)
    prior = [
        Turn(round=1, round_name="Opening Arguments", speaker="prosecutor", kind="opening", text="a"),
        Turn(round=4, round_name="Last Word", speaker="defender", kind="closing", text="b"),
    ]

    turns: list[Turn] = []
    rounds: list[tuple[int, str]] = []
    async for event in engine.challenge(CLAIM, prior, "Ikiniz de olcumu tanimlamadiniz."):
        if event["type"] == "round_start":
            rounds.append((event["number"], event["name"]))
        elif event["type"] == "turn_end":
            turns.append(Turn(**{k: v for k, v in event.items() if k != "type"}))

    assert rounds == [(5, "Challenge 1")]
    assert [(turn.speaker, turn.kind) for turn in turns] == [
        ("user", "user_argument"),
        ("prosecutor", "challenge_response"),
        ("defender", "challenge_response"),
    ]


def test_group_rounds_keeps_turns_with_their_round():
    turns = [
        Turn(round=1, round_name="Opening Arguments", speaker="prosecutor", kind="opening", text="a"),
        Turn(round=1, round_name="Opening Arguments", speaker="defender", kind="opening", text="b"),
        Turn(round=2, round_name="Rebuttal", speaker="prosecutor", kind="rebuttal", text="c"),
    ]
    grouped = group_rounds(turns)

    assert [(round_.number, len(round_.turns)) for round_ in grouped] == [(1, 2), (2, 1)]

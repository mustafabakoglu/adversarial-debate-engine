"""Test fixtures.

Every test runs against a stub provider, so the suite makes no network calls, needs
no API key and finishes in under a second. The stub is configurable on the two
decisions that drive the protocol - whether the referee keeps the debate alive and
whether the judge asks a question from the bench - because those are what determine
the shape of a run.
"""

from __future__ import annotations

import json

import pytest

VERDICT = {
    "prosecutor_score": 70,
    "defender_score": 60,
    "winner": "prosecutor",
    "confidence": 55,
    "reasoning": "The prosecutor kept *answering* the actual point.",
    "strongest_argument": "PROSECUTOR: *this one*",
    "weakest_argument": "DEFENDER: *that one*",
    "unresolved_question": "Who pays for the *measurement*?",
}


class StubProvider:
    """Answers like a provider, without a network.

    `turn_text` deliberately contains asterisks and an emoji so the tests can check
    that one is stripped on the way out and the other is not.
    """

    name = "stub"
    model = "stub-1"

    turn_text = "Bak, *asil* mesele su 🙂"

    def __init__(
        self,
        *,
        unresolved_rounds: int = 0,
        bench_ask: bool = False,
        bench_target: str = "both",
        verdict: dict | None = None,
    ) -> None:
        self.unresolved_rounds = unresolved_rounds
        self.bench_ask = bench_ask
        self.bench_target = bench_target
        self.verdict = dict(verdict or VERDICT)
        self.referee_calls = 0
        self.bench_calls = 0
        self.judge_calls = 0
        self.stream_calls = 0
        self.closed = False

    async def complete(
        self, *, system, user, max_tokens, effort=None, json_schema=None
    ) -> str:  # noqa: ANN001
        keys = set((json_schema or {}).get("properties", {}))

        if "resolved" in keys:
            self.referee_calls += 1
            still_live = self.referee_calls <= self.unresolved_rounds
            return json.dumps(
                {
                    "resolved": not still_live,
                    "tension": "kim odeyecek" if still_live else "",
                    "note": "devam" if still_live else "bitti",
                }
            )

        if "ask" in keys:
            self.bench_calls += 1
            return json.dumps(
                {
                    "ask": self.bench_ask,
                    "target": self.bench_target,
                    "question": "Olcumu *kim* yapacak?" if self.bench_ask else "",
                }
            )

        self.judge_calls += 1
        return json.dumps(self.verdict)

    async def stream(self, *, system, user, max_tokens, effort=None):  # noqa: ANN001
        self.stream_calls += 1
        for fragment in ("Bak, ", "*asil* ", "mesele ", "su 🙂"):
            yield fragment

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def stub() -> StubProvider:
    return StubProvider()

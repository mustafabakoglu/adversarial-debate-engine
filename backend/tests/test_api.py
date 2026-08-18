"""The HTTP surface: validation, the SSE streams, sessions and replay."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.engine import DebateEngine
from tests.conftest import StubProvider

CLAIM = "Universite diplomasi artik gereksiz."


@pytest.fixture
def client(monkeypatch):
    """A client whose engine is the stub, so no test touches the network."""
    provider = StubProvider(unresolved_rounds=1, bench_ask=True)
    with TestClient(main.app) as test_client:
        test_client.app.state.engine = DebateEngine(provider)
        test_client.provider = provider  # type: ignore[attr-defined]
        yield test_client


def events(response) -> list[dict]:
    parsed = []
    for line in response.iter_lines():
        if line.startswith("data:"):
            parsed.append(json.loads(line[5:]))
    return parsed


def test_health_reports_the_live_provider(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "configured": True, "provider": "stub", "model": "stub-1"}


def test_health_without_a_key_says_so():
    with TestClient(main.app) as bare:
        bare.app.state.engine = None
        body = bare.get("/api/health").json()
        assert body["configured"] is False
        assert bare.post("/api/debate", json={"claim": CLAIM}).status_code == 503


def test_post_debate_returns_the_whole_debate(client):
    response = client.post("/api/debate", json={"claim": CLAIM})
    assert response.status_code == 200

    body = response.json()
    assert body["claim"] == CLAIM
    assert [round_["name"] for round_ in body["rounds"]][0] == "Opening Arguments"
    assert body["winner"] in ("prosecutor", "defender", "draw")
    assert "*" not in body["reasoning"]


@pytest.mark.parametrize("claim", ["no", "   ", "x" * 401])
def test_unusable_claims_are_rejected(client, claim):
    assert client.post("/api/debate", json={"claim": claim}).status_code == 422
    assert client.get("/api/debate/stream", params={"claim": claim}).status_code == 422


def test_stream_emits_the_debate_in_order(client):
    with client.stream("GET", "/api/debate/stream", params={"claim": CLAIM}) as response:
        assert response.status_code == 200
        received = events(response)

    kinds = [event["type"] for event in received]
    assert kinds[0] == "session"
    assert kinds[-1] == "done"
    assert "referee" in kinds
    # Deltas only ever arrive inside a turn.
    assert kinds.index("turn_start") < kinds.index("turn_delta") < kinds.index("turn_end")
    assert kinds.index("verdict") == len(kinds) - 2


def test_challenge_needs_a_live_session(client):
    response = client.get(
        "/api/debate/challenge", params={"session": "nope", "argument": "x" * 20}
    )
    assert response.status_code == 404


def test_challenge_continues_the_recorded_session(client):
    with client.stream("GET", "/api/debate/stream", params={"claim": CLAIM}) as response:
        session_id = next(
            event["session_id"] for event in events(response) if event["type"] == "session"
        )

    with client.stream(
        "GET",
        "/api/debate/challenge",
        params={"session": session_id, "argument": "Ikiniz de olcumu tanimlamadiniz."},
    ) as response:
        assert response.status_code == 200
        received = events(response)

    turns = [event for event in received if event["type"] == "turn_end"]
    assert [turn["speaker"] for turn in turns] == ["user", "prosecutor", "defender"]
    # The challenge round comes after every round of the debate it belongs to.
    assert turns[0]["round_name"] == "Challenge 1"
    assert received[-1]["type"] == "done"


def test_replay_needs_no_engine_and_no_key(tmp_path, monkeypatch):
    recording = {
        "claim": CLAIM,
        "rounds": 1,
        "recorded_at": "2026-01-01T00:00:00+00:00",
        "events": [
            {"type": "round_start", "number": 1, "name": "Opening Arguments"},
            {
                "type": "turn_start",
                "round": 1,
                "round_name": "Opening Arguments",
                "speaker": "prosecutor",
                "kind": "opening",
            },
            {
                "type": "turn_end",
                "round": 1,
                "round_name": "Opening Arguments",
                "speaker": "prosecutor",
                "kind": "opening",
                "text": "Diploma bir garanti degil.",
            },
            {"type": "done"},
        ],
    }
    (tmp_path / "saved.json").write_text(json.dumps(recording), encoding="utf-8")
    monkeypatch.setattr("app.config.DEMO_DIR", str(tmp_path))
    monkeypatch.setattr("app.config.REPLAY_GAP_SECONDS", 0.0)

    with TestClient(main.app) as bare:
        bare.app.state.engine = None  # no key, no provider, still a working demo

        listed = bare.get("/api/demos").json()["demos"]
        assert [demo["name"] for demo in listed] == ["saved"]
        assert listed[0]["claim"] == CLAIM

        with bare.stream("GET", "/api/debate/replay", params={"name": "saved"}) as response:
            assert response.status_code == 200
            received = events(response)

    assert received[0]["type"] == "session"
    assert received[0]["recorded"] is True
    kinds = [event["type"] for event in received]
    # The text is handed over as one fragment so the client types it out as before.
    assert kinds == ["session", "round_start", "turn_start", "turn_delta", "turn_end", "done"]


def test_replay_rejects_unknown_and_unsafe_names(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.DEMO_DIR", str(tmp_path))
    with TestClient(main.app) as bare:
        assert bare.get("/api/debate/replay", params={"name": "missing"}).status_code == 404
        assert bare.get("/api/debate/replay", params={"name": "../secrets"}).status_code == 404
        assert bare.get("/api/demos").json() == {"demos": []}

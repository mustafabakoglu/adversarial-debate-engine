"""Record a real debate to a JSON file, for the replay endpoint.

    python -m app.record demo-tr "Yapay zeka yazilimcilarin yerini alacak."
    python -m app.record --extend demo-tr "Ikiniz de olcumu tanimlamadiniz."

Runs the engine exactly as the live endpoint does and writes every event except the
token-by-token deltas, which the client reproduces on replay. Uses whatever is in
.env, so recording with MAX_DEBATE_ROUNDS=5 gives you a shorter demo.

`--extend` adds a challenge round to a recording that already exists, so a replay can
show the whole story - argument, verdict, someone arguing back, second verdict -
without paying for the debate twice.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from . import config, replay
from .engine import DebateEngine
from .errors import DebateError
from .providers import build_provider
from .schemas import Turn


async def record(name: str, claim: str) -> str:
    if not config.MODEL_API_KEY:
        raise DebateError("no MODEL_API_KEY configured; recording needs a live provider")

    engine = DebateEngine(
        build_provider(
            config.MODEL_PROVIDER,
            config.MODEL_API_KEYS,
            config.MODEL_NAME,
            config.REQUEST_MIN_INTERVAL,
        )
    )

    events: list[dict] = []
    rounds = 0
    try:
        async for event in engine.run(claim):
            if event["type"] == "turn_delta":
                continue
            if event["type"] == "round_start":
                rounds += 1
                print(f"  round {event['number']}: {event['name']}", flush=True)
            events.append(event)
    finally:
        await engine.close()

    payload = {
        "claim": claim,
        "provider": engine.provider_name,
        "model": engine.model,
        "rounds": rounds,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": events,
    }

    os.makedirs(config.DEMO_DIR, exist_ok=True)
    path = os.path.join(config.DEMO_DIR, name + ".json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    return path


async def extend(name: str, argument: str) -> str:
    """Append a challenge round, and the verdict it earns, to an existing recording."""
    if not config.MODEL_API_KEY:
        raise DebateError("no MODEL_API_KEY configured; recording needs a live provider")

    recording = replay.load(name)
    prior = [
        Turn(**{key: value for key, value in event.items() if key != "type"})
        for event in recording["events"]
        if event.get("type") == "turn_end"
    ]
    if not prior:
        raise DebateError("that recording has no turns to argue against")

    engine = DebateEngine(
        build_provider(
            config.MODEL_PROVIDER,
            config.MODEL_API_KEYS,
            config.MODEL_NAME,
            config.REQUEST_MIN_INTERVAL,
        )
    )
    added: list[dict] = []
    try:
        async for event in engine.challenge(recording["claim"], prior, argument):
            if event["type"] == "turn_delta":
                continue
            if event["type"] == "round_start":
                print(f"  round {event['number']}: {event['name']}", flush=True)
            added.append(event)
    finally:
        await engine.close()

    # The recording ended with `done`; the challenge continues from before it.
    events = [event for event in recording["events"] if event.get("type") != "done"]
    recording["events"] = events + added
    recording["rounds"] = int(recording.get("rounds") or 0) + 1

    path = os.path.join(config.DEMO_DIR, name + ".json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(recording, handle, ensure_ascii=False, indent=1)
    return path


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--extend":
        name, argument = sys.argv[2], sys.argv[3]
        print(f"extending {name!r} with a challenge round")
        try:
            print(f"wrote {asyncio.run(extend(name, argument))}")
        except DebateError as exc:
            print(f"failed: {exc}")
            return 1
        return 0

    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    name, claim = sys.argv[1], sys.argv[2]
    if not all(char.isalnum() or char in "-_" for char in name):
        print("name may only contain letters, digits, dashes and underscores")
        return 2

    print(f"recording {name!r} with provider={config.MODEL_PROVIDER} cap={config.MAX_DEBATE_ROUNDS}")
    try:
        path = asyncio.run(record(name, claim))
    except DebateError as exc:
        print(f"failed: {exc}")
        return 1
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

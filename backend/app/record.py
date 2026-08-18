"""Record a real debate to a JSON file, for the replay endpoint.

    python -m app.record demo-tr "Yapay zeka yazilimcilarin yerini alacak."

Runs the engine exactly as the live endpoint does and writes every event except
the token-by-token deltas, which the client reproduces on replay. Uses whatever is
in .env, so recording with MAX_DEBATE_ROUNDS=5 gives you a shorter demo.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

from . import config
from .engine import DebateEngine
from .errors import DebateError
from .providers import build_provider


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


def main() -> int:
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

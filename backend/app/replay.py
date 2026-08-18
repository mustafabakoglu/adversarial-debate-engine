"""Recorded debates, replayed down the same event stream as a live one.

This exists for one reason: a debate is twenty-odd model calls over several
minutes, and the two things most likely to be broken when you actually need to
show it to someone - a rate-limited free tier, a conference network - are exactly
the two things the live path depends on. A recording removes both from the
critical path without a second UI to maintain, because it replays the *same*
events the engine emits, so the client cannot tell the difference and nothing
special has to be built to display it.

It is deliberately not a fake: `recorded` is set on the session event, the UI
labels it, and a recording is only ever produced by an actual run of the engine
(see `record.py`). Nothing here can invent a debate that did not happen.

Recordings drop `turn_delta` events, because the client types out the text at its
own pace anyway - so one `turn_delta` carrying the whole turn reproduces exactly
what the reader saw the first time, at a fraction of the file size.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

from . import config
from .errors import DebateError

# Events that stand in for something the live run was waiting on, so they are the
# ones worth pausing before.
_SLOW_EVENTS = {"turn_start", "status", "referee", "verdict"}

_SKIPPED = {"turn_delta", "session"}


def available() -> list[dict]:
    """List the recordings on disk, newest first, without loading them fully."""
    if not os.path.isdir(config.DEMO_DIR):
        return []

    found: list[dict] = []
    for name in sorted(os.listdir(config.DEMO_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(config.DEMO_DIR, name)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        found.append(
            {
                "name": name[: -len(".json")],
                "claim": str(data.get("claim") or ""),
                "rounds": int(data.get("rounds") or 0),
                "recorded_at": str(data.get("recorded_at") or ""),
            }
        )
    return found


def load(name: str) -> dict:
    """Load one recording. `name` is a bare filename stem, never a path."""
    if not name or not all(char.isalnum() or char in "-_" for char in name):
        raise DebateError("no recorded debate by that name")

    path = os.path.join(config.DEMO_DIR, name + ".json")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise DebateError("no recorded debate by that name") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DebateError(f"that recording could not be read: {exc}") from exc

    if not isinstance(data.get("events"), list) or not data.get("claim"):
        raise DebateError("that recording is not a debate")
    return data


async def play(recording: dict, gap: float | None = None) -> AsyncIterator[dict]:
    """Re-emit a recording's events, pausing where the live run had to wait."""
    pause = config.REPLAY_GAP_SECONDS if gap is None else max(0.0, gap)

    for event in recording["events"]:
        if not isinstance(event, dict) or event.get("type") in _SKIPPED:
            continue

        if event["type"] in _SLOW_EVENTS and pause:
            await asyncio.sleep(pause)

        if event["type"] == "turn_end":
            # Hand the text over as one fragment; the client types it out.
            text = str(event.get("text") or "")
            if text:
                yield {"type": "turn_delta", "text": text}

        yield event

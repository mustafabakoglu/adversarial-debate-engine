"""Runtime configuration, read from the environment."""

import os

from dotenv import load_dotenv

load_dotenv()


def _clean(value: str | None) -> str:
    return (value or "").strip()


# Which adapter in providers.py to use: "mistral" or "anthropic".
MODEL_PROVIDER = _clean(os.getenv("MODEL_PROVIDER")) or "mistral"

# MODEL_API_KEY is the documented name. The provider-native variables are
# accepted as fallbacks so an existing environment keeps working.
#
# MODEL_API_KEYS takes a comma-separated list, because a free tier is a quota and a
# quota runs out: the provider rotates to the next key when one starts refusing, so a
# hosted demo does not die the moment several people try it at once.
def _key_ring() -> list[str]:
    keys: list[str] = []
    for candidate in (
        _clean(os.getenv("MODEL_API_KEY")),
        _clean(os.getenv("MISTRAL_API_KEY")),
        _clean(os.getenv("ANTHROPIC_API_KEY")),
        *(part.strip() for part in _clean(os.getenv("MODEL_API_KEYS")).split(",")),
    ):
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


MODEL_API_KEYS = _key_ring()

# The first key, kept as its own name because most of the app only needs to know
# whether a provider can be built at all.
MODEL_API_KEY = MODEL_API_KEYS[0] if MODEL_API_KEYS else ""

# Left empty so providers.py can pick its own default per provider.
MODEL_NAME = _clean(os.getenv("MODEL_NAME"))

# Reasoning effort. Honoured by the Anthropic adapter; ignored by Mistral, which
# has no equivalent control.
DEBATER_EFFORT = _clean(os.getenv("DEBATER_EFFORT")) or "medium"
JUDGE_EFFORT = _clean(os.getenv("JUDGE_EFFORT")) or "high"


def _int(name: str, default: int, low: int, high: int) -> int:
    raw = _clean(os.getenv(name))
    if not raw:
        return default
    try:
        return max(low, min(high, int(raw)))
    except ValueError:
        return default


def _optional_float(name: str) -> float | None:
    raw = _clean(os.getenv(name))
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


# Minimum seconds between provider requests. Leave unset to use the provider's
# own default (Mistral's free tier needs pacing; Anthropic does not). Raise it if
# you still see rate-limit errors.
REQUEST_MIN_INTERVAL = _optional_float("REQUEST_MIN_INTERVAL")

CORS_ORIGINS = [
    origin.strip()
    for origin in (
        _clean(os.getenv("CORS_ORIGINS")) or "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

# A debate turn is a short argument; the judge needs a little more room. The
# referee returns three short fields, so it needs almost nothing.
DEBATER_MAX_TOKENS = 2000
JUDGE_MAX_TOKENS = 3000
REFEREE_MAX_TOKENS = 600

# The debate runs until the referee says the disagreement is exhausted. The floor
# is structural - opening, rebuttal, cross examination and last word are always
# played, so four is the shortest possible debate. This is the ceiling, and it
# exists because a model will always find one more thing to say, and because every
# extra round costs two more calls. Configurable because the right value depends on
# what you are paying per call and how long you are willing to watch: 4 or 5 for a
# demo on a slow free tier, 10 when the argument matters more than the clock.
MAX_DEBATE_ROUNDS = _int("MAX_DEBATE_ROUNDS", 10, 4, 12)

# Injected into the debaters' voice rules. Shorter turns mean a faster debate, and
# it is the single biggest lever on how long a full run takes.
TURN_LENGTH_HINT = _clean(os.getenv("TURN_LENGTH_HINT")) or "70 to 150 words"

# Replay pacing: how long to hold between recorded events. The typing itself is
# paced by the client, so this only stands in for the gaps a live debate spends
# waiting on the model.
REPLAY_GAP_SECONDS = _optional_float("REPLAY_GAP_SECONDS")
if REPLAY_GAP_SECONDS is None:
    REPLAY_GAP_SECONDS = 0.7

# Where recorded debates live, for the replay endpoint.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(_BACKEND_DIR, "demos")

# The built frontend, served by this app when it is present, so a deployment is one
# service and one URL instead of two. Empty or missing means API-only, which is what
# `npm run dev` wants locally.
STATIC_DIR = _clean(os.getenv("STATIC_DIR")) or os.path.join(
    os.path.dirname(_BACKEND_DIR), "frontend", "dist"
)

# The referee is a cheap structural decision, not an argument, so it does not need
# the judge's depth.
REFEREE_EFFORT = "low"

# Guards against pathological input.
MAX_CLAIM_LENGTH = 400
MIN_CLAIM_LENGTH = 8

# A challenge argument is prose, so it gets more room than a claim.
MAX_ARGUMENT_LENGTH = 2000

# How many debates to keep in memory for challenge rounds (no database).
MAX_SESSIONS = 200

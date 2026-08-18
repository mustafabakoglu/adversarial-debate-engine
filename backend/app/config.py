"""Runtime configuration, read from the environment."""

import os

from dotenv import load_dotenv

load_dotenv()


def _clean(value: str | None) -> str:
    return (value or "").strip()


# MODEL_API_KEY is the documented name; ANTHROPIC_API_KEY is accepted so the
# stock SDK environment variable keeps working.
MODEL_API_KEY = _clean(os.getenv("MODEL_API_KEY")) or _clean(os.getenv("ANTHROPIC_API_KEY"))

MODEL_NAME = _clean(os.getenv("MODEL_NAME")) or "claude-opus-5"

DEBATER_EFFORT = _clean(os.getenv("DEBATER_EFFORT")) or "medium"
JUDGE_EFFORT = _clean(os.getenv("JUDGE_EFFORT")) or "high"

CORS_ORIGINS = [
    origin.strip()
    for origin in (_clean(os.getenv("CORS_ORIGINS")) or "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

# A debate turn is a short argument; the judge needs a little more room.
DEBATER_MAX_TOKENS = 2000
JUDGE_MAX_TOKENS = 3000

# Guards against pathological input.
MAX_CLAIM_LENGTH = 400
MIN_CLAIM_LENGTH = 8

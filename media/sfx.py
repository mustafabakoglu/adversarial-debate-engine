"""Two sound effects, synthesised: a transition and a reveal.

Downloading stock effects would mean a licence to track and a file to lose. These are
twenty lines of arithmetic each and they suit the app's restraint better anyway: a soft
noise sweep for a cut, a two-partial bell for the verdict. Standard library only.
"""

from __future__ import annotations

import math
import random
import struct
import sys
import wave

RATE = 44100


def save(path: str, samples: list[float]) -> None:
    peak = max(1e-6, max(abs(value) for value in samples))
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(
            b"".join(
                struct.pack("<h", int(max(-1.0, min(1.0, value / peak * 0.85)) * 32767))
                for value in samples
            )
        )
    print(f"wrote {path} ({len(samples) / RATE:.2f}s)")


def whoosh(seconds: float = 0.55) -> list[float]:
    """Noise through a bandpass that sweeps up and back down. Reads as movement."""
    length = int(RATE * seconds)
    out = [0.0] * length
    state1 = state2 = 0.0
    for i in range(length):
        t = i / length
        noise = random.uniform(-1.0, 1.0)
        # One-pole pair used as a crude resonant sweep: 400Hz -> 2.6kHz -> 500Hz.
        centre = 400 + 2200 * math.sin(math.pi * min(1.0, t * 1.15))
        alpha = min(0.95, centre / (RATE / 2))
        state1 += alpha * (noise - state1)
        state2 += alpha * (state1 - state2)
        envelope = math.sin(math.pi * t) ** 1.5
        out[i] = (state1 - state2) * envelope
    return out


def ding(seconds: float = 1.1) -> list[float]:
    """A quiet bell: fundamental plus a fifth above, both decaying fast."""
    length = int(RATE * seconds)
    out = [0.0] * length
    for i in range(length):
        t = i / RATE
        body = math.sin(2 * math.pi * 784 * t) * math.exp(-t / 0.22)
        upper = math.sin(2 * math.pi * 1176 * t) * math.exp(-t / 0.13) * 0.5
        air = math.sin(2 * math.pi * 2352 * t) * math.exp(-t / 0.06) * 0.18
        out[i] = (body + upper + air) * min(1.0, i / 120)
    return out


if __name__ == "__main__":
    random.seed(11)
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    save(f"{folder}/sfx_whoosh.wav", whoosh())
    save(f"{folder}/sfx_ding.wav", ding())

"""Generate the keyboard-sound bed for the demo video.

The app's typing sound is synthesised in WebAudio and there is no loopback device on
this machine, so the screen capture is silent. Rather than lose the feature in the
video, the same synthesis is reproduced offline: a bandpassed noise burst plus a low
thump per keystroke, jittered so a long stretch does not turn into a metronome.

    python keybed.py out.wav 120        # 120 seconds of typing

Standard library only.
"""

from __future__ import annotations

import math
import random
import struct
import sys
import wave

RATE = 44100
CLICKS_PER_SECOND = 11.0  # slower than the app's typing: one click per few characters


def biquad_bandpass(samples: list[float], freq: float, q: float) -> list[float]:
    """A single 2-pole bandpass, the same shape as the BiquadFilterNode in the app."""
    w0 = 2 * math.pi * freq / RATE
    alpha = math.sin(w0) / (2 * q)
    b0, b1, b2 = alpha, 0.0, -alpha
    a0, a1, a2 = 1 + alpha, -2 * math.cos(w0), 1 - alpha
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0

    out = [0.0] * len(samples)
    x1 = x2 = y1 = y2 = 0.0
    for i, x0 in enumerate(samples):
        y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y0
        x2, x1 = x1, x0
        y2, y1 = y1, y0
    return out


def keystroke(space: bool = False) -> list[float]:
    """One key: filtered noise for the click, a sine thump for the keycap."""
    decay = random.uniform(0.055, 0.075) if space else random.uniform(0.030, 0.048)
    length = int(RATE * (decay * 1.6))

    noise = [random.uniform(-1.0, 1.0) for _ in range(length)]
    freq = random.uniform(620, 820) if space else random.uniform(1250, 2450)
    click = biquad_bandpass(noise, freq, random.uniform(0.7, 1.2))

    level = 0.85 if space else random.uniform(0.5, 0.8)
    thump_freq = 96.0 if space else random.uniform(120, 170)

    out = [0.0] * length
    for i in range(length):
        t = i / RATE
        envelope = math.exp(-t / (decay / 3.0))
        thump = math.sin(2 * math.pi * thump_freq * t) * math.exp(-t / (decay / 2.2)) * 0.55
        out[i] = (click[i] * 1.6 + thump) * envelope * level
    return out


def build(seconds: float) -> list[float]:
    total = int(RATE * seconds)
    track = [0.0] * (total + RATE)
    position = 0.0

    while position < seconds:
        space = random.random() < 0.16
        sample = keystroke(space)
        start = int(position * RATE)
        for i, value in enumerate(sample):
            index = start + i
            if index < len(track):
                track[index] += value

        # Jittered spacing, with the occasional pause so it breathes like a sentence.
        gap = random.gauss(1.0 / CLICKS_PER_SECOND, 0.022)
        if random.random() < 0.035:
            gap += random.uniform(0.25, 0.7)
        position += max(0.035, gap)

    peak = max(1e-6, max(abs(value) for value in track))
    return [value / peak * 0.5 for value in track[:total]]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    path, seconds = sys.argv[1], float(sys.argv[2])
    random.seed(7)  # reproducible bed, so a re-render sounds identical
    track = build(seconds)

    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, value)) * 32767)) for value in track)
        )
    print(f"wrote {path} ({seconds:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

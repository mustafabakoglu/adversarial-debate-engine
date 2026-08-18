"""Narration for every part of the film, then made to sound like a person.

Raw text-to-speech reads thin and slightly synthetic on a laptop speaker. The fix is
not a different sentence, it is the signal chain every voice track gets before it goes
near a mix: cut the rumble, lift the chest around 140Hz, tame the sibilance, even the
level out with light compression, then normalise so every line sits at the same
loudness. Written down here rather than done by ear so the whole thing re-renders.

    python voice.py            # writes vo/<part>.wav
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess

import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "vo_raw")
OUT = os.path.join(HERE, "vo")

# Warm and low rather than bright and announcer-ish; "Multilingual" handles the odd
# Turkish word in the language section without switching accent mid-sentence.
VOICE = "en-US-AndrewMultilingualNeural"
RATE = "-3%"    # a touch under default: reads as considered rather than rushed
PITCH = "-2Hz"  # fuller, without dropping into parody

# The chain, in order: rumble out, chest in, presence in, sibilance down, level even,
# then a fixed loudness target so nothing has to be ridden in the mix.
CHAIN = (
    "highpass=f=75,"
    "equalizer=f=140:width_type=q:width=0.9:g=3.2,"
    "equalizer=f=320:width_type=q:width=1.1:g=-1.6,"
    "equalizer=f=2600:width_type=q:width=1.2:g=1.8,"
    "equalizer=f=7200:width_type=q:width=1.4:g=-2.4,"
    "acompressor=threshold=-19dB:ratio=3:attack=12:release=180:makeup=2,"
    "loudnorm=I=-16:TP=-1.5:LRA=9,"
    "aformat=sample_fmts=s16:sample_rates=44100:channel_layouts=stereo"
)

LINES: dict[str, str] = {
    "intro": (
        "Ask any AI assistant whether your plan is good, and it will find reasons it is "
        "good. Which makes it useless for the one thing you actually wanted help with. "
        "Deciding. So I built one that cannot agree with you."
    ),
    "openings": (
        "You give it a claim. Two agents are assigned opposite sides, and neither of them "
        "chose the side it defends. Both openings are written blind, so nobody is reacting "
        "yet."
    ),
    "rebuttal": (
        "Then they have to engage. Each side takes apart what the other actually said, "
        "quoting the exact phrase. Bringing a new argument of your own is forbidden."
    ),
    "rounds": (
        "And nobody decides how long a debate runs. After every round, a referee reads the "
        "transcript and answers one question. Is this still going somewhere?"
    ),
    "cross": (
        "Cross examination. One question each, and the answer has to lead with the answer. "
        "Evasion is visible here, and the judge is told to punish it."
    ),
    "referee": (
        "If the disagreement is exhausted, the referee closes it. If it is still live, it "
        "names the exact tension left open, and that sentence becomes the next round's "
        "instruction."
    ),
    "bench": (
        "The judge is not a spectator either. Before the closing statements, it can put one "
        "question to a side, or to both."
    ),
    "bench_scene": (
        "It is told to ask only when something load bearing has gone undefended. And a dodge "
        "to the judge's face costs more than a dodge to your opponent."
    ),
    "scoring": (
        "Then it scores how well they argued. Not whether the claim is true. A debater who "
        "defends a false claim skilfully beats one who defends a true claim badly."
    ),
    "verdict": (
        "Scores, confidence, the strongest argument, the weakest one, and the question "
        "neither side managed to settle."
    ),
    "challenge": "Still not convinced? Then argue back.",
    "challenge_scene": (
        "Both sides have to answer you, specifically. Your argument carries no authority just "
        "because you started the debate. And it can still move the verdict."
    ),
    "language": (
        "There is no language setting. It argues in the language of your claim, verdict "
        "included."
    ),
    "ai": (
        "All of it is one model behind four different system prompts. Two debaters, who "
        "stream their turns token by token. A referee that decides whether the argument is "
        "finished. And a judge, that asks its question and then returns the verdict as a "
        "validated object, not prose somebody has to parse hopefully."
    ),
    "tech": (
        "FastAPI, server sent events, one model behind four different system prompts, "
        "structured outputs for the verdict, no database, and thirty tests that need no "
        "network at all."
    ),
    "end": "Most assistants tell you what you want to hear. This one makes you earn it.",
}


async def speak() -> None:
    os.makedirs(RAW, exist_ok=True)
    for name, text in LINES.items():
        target = os.path.join(RAW, name + ".mp3")
        await edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH).save(target)
        print(f"  spoke  {name}")


def polish() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name in LINES:
        source = os.path.join(RAW, name + ".mp3")
        target = os.path.join(OUT, name + ".wav")
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", source,
             "-af", CHAIN, target],
            check=True,
        )
        length = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             target],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        print(f"  polished {name:16s} {float(length):5.1f}s")


if __name__ == "__main__":
    asyncio.run(speak())
    polish()
    lengths = {
        name: float(
            subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                 os.path.join(OUT, name + ".wav")],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        )
        for name in LINES
    }
    with open(os.path.join(HERE, "vo_lengths.json"), "w", encoding="utf-8") as handle:
        json.dump(lengths, handle, indent=1)
    print(f"\ntotal narration: {sum(lengths.values()):.0f}s")

"""Assemble the demo video: narration, animated cards, footage, captions, effects.

Every part is driven by its narration: a card is held for as long as its line takes, and
a scene is stretched or compressed to fit it. The edit therefore cannot drift out of
sync, and re-recording one line changes the length of one part and nothing else.

Audio per part: the voice on top, the synthesised keyboard bed under the footage, a soft
sweep on each cut into a card, and one bell where the verdict lands. Parts are rendered
separately and concatenated, so a bad scene costs one re-render rather than a re-cut.

    python cut.py            # writes demo.mp4
"""

from __future__ import annotations

import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "clean.mp4")
PARTS = os.path.join(HERE, "parts")
OUT = os.path.join(HERE, "demo.mp4")

FPS = 24
# 2560x1440 capture: drop the title bar and the taskbar, then the widest 16:9 inside.
CROP = "crop=2368:1332:96:36,scale=1920:1080:flags=lanczos"
AFORMAT = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"

BED_DB = -19      # keyboard, under the voice
WHOOSH_DB = -13   # the cut into a card
DING_DB = -15     # the verdict

LEAD = 0.45       # silence before a line starts
TAIL = 0.9        # air after it ends

# scene -> (source start, source end, narration, caption)
SCENES: dict[str, tuple[float, float, str, str]] = {
    "openings": (3.0, 24.0, "openings", "blind"),
    "rebuttal": (30.0, 52.0, "rebuttal", "rebuttal"),
    "cross": (60.0, 80.0, "cross", "cross"),
    "referee": (84.0, 96.0, "referee", "referee"),
    "bench": (96.0, 122.0, "bench_scene", "bench"),
    "verdict": (138.0, 162.0, "verdict", "verdict"),
    "challenge": (164.0, 190.0, "challenge_scene", "challenge"),
}

# card -> narration
CARDS: dict[str, str] = {
    "intro": "intro",
    "rounds": "rounds",
    "bench": "bench",
    "scoring": "scoring",
    "challenge": "challenge",
    "language": "language",
    "ai": "ai",
    "tech": "tech",
    "end": "end",
}

TIMELINE: list[tuple[str, str]] = [
    ("card", "intro"),
    ("scene", "openings"),
    ("scene", "rebuttal"),
    ("card", "rounds"),
    ("scene", "cross"),
    ("scene", "referee"),
    ("card", "bench"),
    ("scene", "bench"),
    ("card", "scoring"),
    ("scene", "verdict"),
    ("card", "challenge"),
    ("scene", "challenge"),
    ("card", "language"),
    ("card", "ai"),
    ("card", "tech"),
    ("card", "end"),
]

VOICE_LENGTHS: dict[str, float] = json.load(
    open(os.path.join(HERE, "vo_lengths.json"), encoding="utf-8")
)


def run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(args)}\n{result.stderr[-1200:]}")


def probe(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def voice(name: str) -> str:
    return os.path.join(HERE, "vo", name + ".wav")


def part_length(narration: str) -> float:
    return VOICE_LENGTHS[narration] + LEAD + TAIL


def card(name: str) -> str:
    narration = CARDS[name]
    folder = os.path.join(HERE, "anim", name)
    frames = len([f for f in os.listdir(folder) if f.endswith(".png")])
    animation = frames / FPS
    length = max(animation, part_length(narration))
    out = os.path.join(PARTS, f"card_{name}.mp4")

    if os.path.exists(out) and os.path.getsize(out) > 0:
        print(f"  card  {name:10s} kept")
        return out

    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(FPS), "-i", os.path.join(folder, "%04d.png"),
            "-i", voice(narration),
            "-i", os.path.join(HERE, "sfx_whoosh.wav")]

    video = (f"[0:v]tpad=stop_mode=clone:stop_duration={max(0.0, length - animation):.3f},"
             f"fps={FPS},format=yuv420p[v]")
    audio = (
        f"[1:a]adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},{AFORMAT}[vo];"
        f"[2:a]volume={WHOOSH_DB}dB,{AFORMAT}[sfx];"
        f"[vo][sfx]amix=inputs=2:duration=longest:dropout_transition=0,"
        f"apad,atrim=0:{length:.3f},asetpts=N/SR/TB,{AFORMAT}[a]"
    )

    args += ["-filter_complex", video + ";" + audio, "-map", "[v]", "-map", "[a]",
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "176k", "-ac", "2", "-ar", "44100",
             "-pix_fmt", "yuv420p", out]
    run(args)
    print(f"  card  {name:10s} {length:5.1f}s")
    return out


def scene(name: str, index: int) -> str:
    start, end, narration, caption = SCENES[name]
    length = part_length(narration)
    speed = (end - start) / length
    out = os.path.join(PARTS, f"scene_{name}.mp4")

    if os.path.exists(out) and os.path.getsize(out) > 0:
        print(f"  scene {name:10s} kept")
        return out

    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", SOURCE,
            "-i", voice(narration),
            "-ss", f"{(index * 17) % 150:.3f}", "-i", os.path.join(HERE, "keybed.wav"),
            "-loop", "1", "-t", f"{length:.3f}", "-i", os.path.join(HERE, f"cap_{caption}.png")]

    video = (f"[0:v]{CROP},setpts=PTS/{speed:.6f},fps={FPS},format=yuv420p[base];"
             f"[3:v]format=rgba,fade=t=in:st=0:d=0.5:alpha=1,"
             f"fade=t=out:st={length - 0.7:.3f}:d=0.5:alpha=1[cap];"
             f"[base][cap]overlay=x=0:y=H-165:eof_action=pass[v]")

    audio = (
        f"[1:a]adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},{AFORMAT}[vo];"
        f"[2:a]atrim=0:{length:.3f},asetpts=N/SR/TB,volume={BED_DB}dB,"
        f"afade=t=in:d=0.6,afade=t=out:st={max(0.1, length - 0.8):.3f}:d=0.6,{AFORMAT}[bed];"
        f"[vo][bed]amix=inputs=2:duration=longest:dropout_transition=0,"
        f"apad,atrim=0:{length:.3f},asetpts=N/SR/TB,{AFORMAT}[a]"
    )

    # The verdict is the one moment that earns a sound of its own.
    if name == "verdict":
        args += ["-i", os.path.join(HERE, "sfx_ding.wav")]
        audio = audio.replace(
            "[vo][bed]amix=inputs=2",
            f"[4:a]adelay=900|900,volume={DING_DB}dB,{AFORMAT}[ding];"
            f"[vo][bed][ding]amix=inputs=3",
        )

    args += ["-filter_complex", video + ";" + audio, "-map", "[v]", "-map", "[a]",
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "176k", "-ac", "2", "-ar", "44100",
             "-pix_fmt", "yuv420p", out]
    run(args)
    print(f"  scene {name:10s} {end - start:5.1f}s -> {length:4.1f}s  (x{speed:.2f})  [{caption}]")
    return out


def main() -> None:
    os.makedirs(PARTS, exist_ok=True)
    print(f"source: {probe(SOURCE):.0f}s of app-only capture")

    built: list[str] = []
    for index, (kind, name) in enumerate(TIMELINE):
        built.append(card(name) if kind == "card" else scene(name, index))

    listing = os.path.join(PARTS, "list.txt")
    with open(listing, "w", encoding="utf-8") as handle:
        for path in built:
            handle.write("file '" + path.replace("\\", "/") + "'\n")

    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", listing, "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT])

    print(f"\nwrote {OUT}  ({probe(OUT):.1f}s)")


if __name__ == "__main__":
    main()

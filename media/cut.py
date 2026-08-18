"""Assemble the demo video: animated cards, screen footage, captions, sound.

No narration except the hook and the closing line — the story is carried by the
animated cards and the lower-third captions, which is faster to produce and easier to
re-cut than a full voiceover. Audio under the footage is the synthesised keyboard bed,
so the typing the product is known for is audible even though the capture is silent.

Every part is rendered on its own and then concatenated: slower than one filter graph,
but when a single scene is wrong you re-render that scene instead of the film.

    python cut.py            # writes demo.mp4
"""

from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "clean.mp4")
PARTS = os.path.join(HERE, "parts")
OUT = os.path.join(HERE, "demo.mp4")

FPS = 24
# 2560x1440 capture: drop the title bar and the taskbar, then the widest 16:9 inside.
CROP = "crop=2368:1332:96:36,scale=1920:1080:flags=lanczos"
BED_DB = -17  # the keyboard, present but well under the eye

# Concat refuses parts whose audio differs, and the sources are a mono WAV, a mono mp3
# and a stereo silence generator - so every part is normalised to the same layout.
AFORMAT = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"

# (source start, source end, output length, caption)
SCENES: dict[str, tuple[float, float, float, str | None]] = {
    "openings": (3.0, 24.0, 20.0, "blind"),
    "rebuttal": (30.0, 52.0, 17.0, "rebuttal"),
    "cross": (60.0, 80.0, 15.0, "cross"),
    "referee": (84.0, 96.0, 12.0, "referee"),
    "bench": (96.0, 120.0, 18.0, "bench"),
    "verdict": (138.0, 162.0, 20.0, "verdict"),
    "challenge": (164.0, 190.0, 20.0, "challenge"),
}

# The film, in order. ("card", name) or ("scene", name).
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
    ("card", "tech"),
    ("card", "end"),
]

# Cards that carry a spoken line: the hook and the sign-off, nothing in between.
CARD_AUDIO = {"intro": ("01_hook.mp3", 4.6), "end": ("11_close.mp3", 0.6)}


def run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(args)}\n{result.stderr[-1500:]}")


def probe(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def card(name: str) -> str:
    """A frame sequence, held to the length of its narration if it has one."""
    folder = os.path.join(HERE, "anim", name)
    frames = len([f for f in os.listdir(folder) if f.endswith(".png")])
    animation = frames / FPS
    out = os.path.join(PARTS, f"card_{name}.mp4")

    voice, pad = CARD_AUDIO.get(name, (None, 0.0))
    length = animation
    if voice:
        length = max(animation, probe(os.path.join(HERE, "vo", voice)) + pad)

    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(FPS), "-i", os.path.join(folder, "%04d.png")]

    # Hold the last frame for whatever time the audio still needs.
    video = f"[0:v]tpad=stop_mode=clone:stop_duration={max(0.0, length - animation):.3f},format=yuv420p[v]"

    if voice:
        args += ["-i", os.path.join(HERE, "vo", voice)]
        audio = (f"[1:a]adelay=400|400,apad,atrim=0:{length:.3f},asetpts=N/SR/TB,"
                 f"{AFORMAT}[a]")
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio = f"[1:a]atrim=0:{length:.3f},asetpts=N/SR/TB,{AFORMAT}[a]"

    args += ["-filter_complex", video + ";" + audio, "-map", "[v]", "-map", "[a]",
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100",
             "-pix_fmt", "yuv420p", out]
    run(args)
    print(f"  card  {name:10s} {length:5.1f}s" + ("  + voice" if voice else ""))
    return out


def scene(name: str, index: int) -> str:
    start, end, length, caption = SCENES[name]
    speed = (end - start) / length
    out = os.path.join(PARTS, f"scene_{name}.mp4")

    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", SOURCE,
            "-ss", f"{(index * 23) % 120:.3f}", "-i", os.path.join(HERE, "keybed.wav")]

    video = f"[0:v]{CROP},setpts=PTS/{speed:.6f},fps={FPS},format=yuv420p"
    if caption:
        args += ["-loop", "1", "-i", os.path.join(HERE, f"cap_{caption}.png")]
        video += "[base];[2:v]format=rgba,fade=t=in:st=0:d=0.5:alpha=1,"
        video += f"fade=t=out:st={length - 0.6:.3f}:d=0.5:alpha=1[cap];"
        video += "[base][cap]overlay=x=0:y=H-165:eof_action=pass[v]"
    else:
        video += "[v]"

    audio = (
        f"[1:a]atrim=0:{length:.3f},asetpts=N/SR/TB,volume={BED_DB}dB,"
        f"afade=t=in:d=0.5,afade=t=out:st={length - 0.6:.3f}:d=0.5,{AFORMAT}[a]"
    )

    args += ["-filter_complex", video + ";" + audio, "-map", "[v]", "-map", "[a]",
             "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "44100",
             "-pix_fmt", "yuv420p", out]
    run(args)
    print(f"  scene {name:10s} {end - start:5.1f}s -> {length:4.1f}s  (x{speed:.2f})"
          f"  [{caption}]")
    return out


def main() -> None:
    os.makedirs(PARTS, exist_ok=True)
    print(f"source: {probe(SOURCE):.0f}s of app-only capture")

    built: list[str] = []
    for index, (kind, name) in enumerate(TIMELINE):
        built.append(card(name) if kind == "card" else scene(name, index))

    listing = os.path.join(PARTS, "list.txt")
    with open(listing, "w", encoding="utf-8") as handle:
        for part in built:
            handle.write("file '" + part.replace("\\", "/") + "'\n")

    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", listing, "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT])

    print(f"\nwrote {OUT}  ({probe(OUT):.1f}s)")


if __name__ == "__main__":
    main()

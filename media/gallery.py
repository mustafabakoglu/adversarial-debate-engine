"""Gallery images for the submission page, at the 3:2 ratio Devpost asks for.

Frames come from the same capture the video uses, so the gallery cannot show anything the
product does not do. Each one is padded to 3:2 on the app's own canvas colour and given a
one-line caption in the app's type, because a reviewer scrolling a gallery reads captions
and not much else.

    python gallery.py            # writes gallery/*.jpg
"""

from __future__ import annotations

import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "clean.mp4")
OUT = os.path.join(HERE, "gallery")

WIDTH, HEIGHT = 1800, 1200          # 3:2
CANVAS = (250, 250, 251)
INK = (42, 46, 53)
FAINT = (150, 156, 166)
FONT_DIR = "C:/Windows/Fonts"

# (file name, source seconds or animation frame, caption)
FROM_CAPTURE = [
    ("02-openings", 20.0, "Both openings are written blind — neither side can see the other"),
    ("03-rebuttal", 44.0, "Rebuttal: attack what they actually said, quoting the phrase"),
    ("04-cross", 74.0, "Cross examination — one question each, and the answer comes first"),
    ("05-bench", 100.0, "From the bench: the judge puts its own question to both sides"),
    ("06-verdict", 139.4, "The verdict scores how well each side argued, not who is right"),
    ("07-challenge", 178.0, "You argue back, and both sides have to answer you specifically"),
]

FROM_ANIMATION = [
    ("01-title", ("intro", 160), "Devil's Advocate — an AI built to argue against you"),
    ("08-architecture", ("ai", 330), "One model, four system prompts, and a referee that decides the length"),
]


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def compose(image: Image.Image, caption: str, path: str) -> None:
    """Fit a 16:9 frame into 3:2 and caption it."""
    canvas = Image.new("RGB", (WIDTH, HEIGHT), CANVAS)
    inner_width = WIDTH - 80
    inner_height = round(inner_width * image.height / image.width)
    canvas.paste(image.resize((inner_width, inner_height), Image.LANCZOS), (40, 40))

    draw = ImageDraw.Draw(canvas)
    label = font("seguisb.ttf", 34)
    y = 40 + inner_height + 46
    width = draw.textlength(caption, font=label)
    draw.text(((WIDTH - width) / 2, y), caption, font=label, fill=INK)

    mark = font("segoeui.ttf", 24)
    footer = "DEVIL'S ADVOCATE  ·  github.com/mustafabakoglu/adversarial-debate-engine"
    width = draw.textlength(footer, font=mark)
    draw.text(((WIDTH - width) / 2, HEIGHT - 62), footer, font=mark, fill=FAINT)

    canvas.save(path, quality=92, optimize=True)
    print(f"  {os.path.basename(path)}  {os.path.getsize(path) // 1024}KB")


def frame_at(seconds: float) -> Image.Image:
    temp = os.path.join(OUT, "_frame.png")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{seconds:.3f}",
         "-i", SOURCE, "-vf", "crop=2368:1332:96:36", "-frames:v", "1", "-update", "1", temp],
        check=True,
    )
    image = Image.open(temp).convert("RGB")
    return image


if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)

    for name, seconds, caption in FROM_CAPTURE:
        compose(frame_at(seconds), caption, os.path.join(OUT, name + ".jpg"))

    for name, (animation, index), caption in FROM_ANIMATION:
        source = os.path.join(HERE, "anim", animation, f"{index:04d}.png")
        compose(Image.open(source).convert("RGB"), caption, os.path.join(OUT, name + ".jpg"))

    os.remove(os.path.join(OUT, "_frame.png"))
    print(f"\n{len(FROM_CAPTURE) + len(FROM_ANIMATION)} images in {OUT}")

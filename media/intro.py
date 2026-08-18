"""The intro animation, and the animated cards that carry the story.

There is no voiceover, so every frame has to say something. Frames are drawn with PIL
rather than ffmpeg filters because the timing is easier to reason about one frame at a
time, and because the type has to match the app's own: same palette, same weights, same
restraint.

    python intro.py            # writes anim/intro/*.png and anim/<card>/*.png
"""

from __future__ import annotations

import math
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 24

CANVAS = (250, 250, 251)
INK = (42, 46, 53)
SOFT = (107, 114, 128)
FAINT = (163, 168, 178)
PROSECUTOR = (47, 107, 216)
DEFENDER = (208, 64, 47)

FONT_DIR = "C:/Windows/Fonts"
HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, "anim")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def ease(t: float) -> float:
    """Cubic ease-out: fast start, soft landing. Matches the app's own easing."""
    t = max(0.0, min(1.0, t))
    return 1 - pow(1 - t, 3)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def fade(colour: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Blend towards the canvas, so text can appear without an alpha layer."""
    amount = max(0.0, min(1.0, amount))
    return tuple(int(lerp(CANVAS[i], colour[i], amount)) for i in range(3))


def centred(draw: ImageDraw.ImageDraw, y: float, text: str, fnt, fill, spacing: float = 0) -> None:
    if spacing:
        width = sum(draw.textlength(char, font=fnt) + spacing for char in text) - spacing
        x = (W - width) / 2
        for char in text:
            draw.text((x, y), char, font=fnt, fill=fill)
            x += draw.textlength(char, font=fnt) + spacing
        return
    width = draw.textlength(text, font=fnt)
    draw.text(((W - width) / 2, y), text, font=fnt, fill=fill)


def write(frames: list[Image.Image], name: str) -> None:
    folder = os.path.join(ANIM, name)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(os.path.join(folder, f"{index:04d}.png"))
    print(f"  {name}: {len(frames)} frames ({len(frames) / FPS:.1f}s)")


# ---------------------------------------------------------------------------
# Intro
# ---------------------------------------------------------------------------


def intro(seconds: float = 7.0) -> None:
    """Two opposed rules draw outwards, the line lands, the promise follows."""
    total = int(seconds * FPS)
    frames: list[Image.Image] = []

    eyebrow = font("segoeui.ttf", 26)
    headline = font("seguisb.ttf", 108)
    sub = font("segoeui.ttf", 34)

    for index in range(total):
        t = index / (total - 1)
        image = Image.new("RGB", (W, H), CANVAS)
        draw = ImageDraw.Draw(image)

        # 0.00-0.25  the two sides draw apart from the centre
        rule = ease(min(1.0, t / 0.25))
        half = 240 * rule
        y_rule = 300
        if rule > 0:
            draw.line([(W / 2 - half, y_rule), (W / 2 - 24, y_rule)], fill=PROSECUTOR, width=6)
            draw.line([(W / 2 + 24, y_rule), (W / 2 + half, y_rule)], fill=DEFENDER, width=6)

        # 0.10-0.30  eyebrow
        if t > 0.10:
            centred(draw, 360, "DEVIL'S ADVOCATE", eyebrow,
                    fade(FAINT, ease((t - 0.10) / 0.20)), spacing=8)

        # 0.22-0.55  headline, two lines rising into place
        for line_index, line in enumerate(("This AI does not agree", "with you.")):
            start = 0.22 + line_index * 0.13
            progress = ease((t - start) / 0.28) if t > start else 0.0
            if progress <= 0:
                continue
            y = 440 + line_index * 122 + (1 - progress) * 26
            centred(draw, y, line, headline, fade(INK, progress))

        # 0.60-0.85  the promise
        if t > 0.60:
            amount = ease((t - 0.60) / 0.22)
            centred(draw, 730, "It argues against you, and it cannot do otherwise.", sub,
                    fade(SOFT, amount))
        if t > 0.72:
            amount = ease((t - 0.72) / 0.22)
            centred(draw, 782, "Two agents. Opposite sides. Neither of them chose which.", sub,
                    fade(SOFT, amount))

        frames.append(image)

    write(frames, "intro")


# ---------------------------------------------------------------------------
# How the AI is wired - the one thing a judging rubric always asks for
# ---------------------------------------------------------------------------


def pipeline_card(seconds: float = 15.0) -> None:
    """Build the architecture diagram a box at a time, then hold with the loop alive."""
    total = int(seconds * FPS)
    frames: list[Image.Image] = []

    title = font("seguisb.ttf", 46)
    label = font("seguisb.ttf", 30)
    note = font("segoeui.ttf", 23)
    small = font("segoeui.ttf", 25)

    #     name        x     w   colour        caption under the box
    boxes = [
        ("YOUR CLAIM", 96, 250, SOFT, "any language"),
        ("PROSECUTOR", 420, 250, PROSECUTOR, "argues it is false"),
        ("DEFENDER", 420, 250, DEFENDER, "argues it holds"),
        ("REFEREE", 776, 250, INK, "another round, or done?"),
        ("JUDGE", 1132, 250, INK, "asks, then scores"),
        ("VERDICT", 1488, 250, PROSECUTOR, "validated object"),
    ]

    def box(draw, x, y, w, h, colour, name, caption, amount):
        if amount <= 0:
            return
        edge = fade(colour, amount)
        draw.rounded_rectangle([x, y, x + w, y + h], radius=14, outline=edge, width=3)
        draw.text((x + 18, y + 18), name, font=label, fill=edge)
        draw.text((x + 18, y + 58), caption, font=note, fill=fade(SOFT, amount * 0.9))

    def arrow(draw, x1, y1, x2, y2, amount, colour=None):
        if amount <= 0:
            return
        colour = fade(colour or FAINT, amount)
        x = lerp(x1, x2, ease(amount))
        draw.line([(x1, y1), (x, y2)], fill=colour, width=3)
        if amount > 0.85:
            draw.polygon([(x2, y2), (x2 - 12, y2 - 7), (x2 - 12, y2 + 7)], fill=colour)

    for index in range(total):
        t = index / (total - 1)
        image = Image.new("RGB", (W, H), CANVAS)
        draw = ImageDraw.Draw(image)

        centred(draw, 150, "How the AI is wired", title, fade(INK, ease(t / 0.08)))
        if t > 0.06:
            centred(draw, 214, "ONE MODEL, FOUR SYSTEM PROMPTS", note,
                    fade(FAINT, ease((t - 0.06) / 0.08)), spacing=5)

        steps = [0.10, 0.20, 0.20, 0.34, 0.46, 0.58]
        rows = [430, 330, 530, 430, 430, 430]
        for (name, x, w, colour, caption), start, y in zip(boxes, steps, rows):
            box(draw, x, y, w, 110, colour, name, caption, ease((t - start) / 0.10))

        # claim -> both debaters, debaters -> referee, referee -> judge -> verdict
        arrow(draw, 350, 485, 414, 385, ease((t - 0.17) / 0.06))
        arrow(draw, 350, 485, 414, 585, ease((t - 0.17) / 0.06))
        arrow(draw, 674, 385, 770, 470, ease((t - 0.30) / 0.06))
        arrow(draw, 674, 585, 770, 500, ease((t - 0.30) / 0.06))
        arrow(draw, 1030, 485, 1126, 485, ease((t - 0.44) / 0.06), INK)
        arrow(draw, 1386, 485, 1482, 485, ease((t - 0.56) / 0.06), PROSECUTOR)

        # the loop that makes the length variable, drawn under the row
        if t > 0.38:
            amount = ease((t - 0.38) / 0.10)
            colour = fade(INK, amount)
            y = 690
            draw.line([(900, 545), (900, y)], fill=colour, width=3)
            draw.line([(900, y), (545, y)], fill=colour, width=3)
            draw.line([(545, y), (545, 645)], fill=colour, width=3)
            if amount > 0.9:
                draw.polygon([(545, 636), (538, 652), (552, 652)], fill=colour)
            pulse = 0.55 + 0.45 * abs(math.sin(t * 9))
            draw.text((610, y + 14), "still live → one more round, on the exact tension",
                      font=note, fill=fade(INK, amount * pulse))

        if t > 0.66:
            amount = ease((t - 0.66) / 0.12)
            centred(draw, 800, "Debater turns stream token by token over server-sent events.",
                    small, fade(SOFT, amount))
        if t > 0.74:
            amount = ease((t - 0.74) / 0.12)
            centred(draw, 838,
                    "Referee, bench question and verdict are structured outputs, not prose.",
                    small, fade(SOFT, amount))
        if t > 0.82:
            amount = ease((t - 0.82) / 0.12)
            centred(draw, 876,
                    "Two provider adapters. The debate protocol never knows which one it is on.",
                    small, fade(SOFT, amount))

        frames.append(image)

    write(frames, "ai")


# ---------------------------------------------------------------------------
# Story cards between the footage
# ---------------------------------------------------------------------------

CARDS: list[tuple[str, list[str], tuple[int, int, int], float]] = [
    (
        "rounds",
        [
            "Nobody decides how long a debate runs.",
            "A referee reads the transcript after every round and answers one question:",
            "is this still going somewhere?",
        ],
        INK,
        5.0,
    ),
    (
        "bench",
        [
            "The judge is not a spectator.",
            "Before closing statements it may put one question to a side, or to both,",
            "and a dodge to the judge's face costs more than a dodge to your opponent.",
        ],
        INK,
        5.0,
    ),
    (
        "scoring",
        [
            "It scores how well they argued.",
            "Not whether the claim is true.",
            "A debater who defends a false claim skilfully beats one who defends a true claim badly.",
        ],
        PROSECUTOR,
        5.0,
    ),
    (
        "challenge",
        [
            "Not convinced? Argue back.",
            "Both sides have to answer you, specifically.",
            "Your argument carries no authority — and it can still move the verdict.",
        ],
        DEFENDER,
        5.0,
    ),
    (
        "language",
        [
            "No language setting.",
            "It argues in the language of your claim — verdict included.",
            "",
            "PROSECUTOR, from a Turkish debate on the same claim:",
            "“Beş dakika önce öğrenmek, karar verme yetkisini elinden almaz.”",
            "“Learning five minutes earlier does not take the decision out of your hands.”",
        ],
        INK,
        6.5,
    ),
    (
        "tech",
        [
            "FastAPI · server-sent events · one model behind four system prompts",
            "structured outputs for the verdict · provider-agnostic · no database",
            "30 tests, no network required · recorded debates replay with no API key",
        ],
        SOFT,
        5.0,
    ),
]


def story_card(name: str, lines: list[str], accent: tuple[int, int, int], seconds: float) -> None:
    total = int(seconds * FPS)
    frames: list[Image.Image] = []

    big = font("seguisb.ttf", 60)
    small = font("segoeui.ttf", 34)

    for index in range(total):
        t = index / (total - 1)
        image = Image.new("RGB", (W, H), CANVAS)
        draw = ImageDraw.Draw(image)

        rule = ease(min(1.0, t / 0.18))
        draw.line([(W / 2 - 120 * rule, 330), (W / 2 + 120 * rule, 330)], fill=accent, width=6)

        y = 420
        for line_index, line in enumerate(lines):
            start = 0.12 + line_index * 0.12
            progress = ease((t - start) / 0.26) if t > start else 0.0
            if progress <= 0:
                y += 96 if line_index == 0 else 58
                continue
            fnt = big if line_index == 0 else small
            colour = accent if line_index == 0 else SOFT
            offset = (1 - progress) * 18
            centred(draw, y + offset, line, fnt, fade(colour, progress))
            y += 96 if line_index == 0 else 58

        # Hold, then release: a short fade to canvas so the cut into footage is soft.
        if t > 0.93:
            out = ease((t - 0.93) / 0.07)
            veil = Image.new("RGB", (W, H), CANVAS)
            image = Image.blend(image, veil, out * 0.45)

        frames.append(image)

    write(frames, name)


def end_card(seconds: float = 6.0) -> None:
    total = int(seconds * FPS)
    frames: list[Image.Image] = []

    big = font("seguisb.ttf", 74)
    url = font("seguisb.ttf", 40)
    small = font("segoeui.ttf", 26)

    for index in range(total):
        t = index / (total - 1)
        image = Image.new("RGB", (W, H), CANVAS)
        draw = ImageDraw.Draw(image)

        for line_index, line in enumerate(
            ("Most assistants tell you", "what you want to hear.")
        ):
            progress = ease((t - line_index * 0.10) / 0.24)
            if progress <= 0:
                continue
            centred(draw, 320 + line_index * 92, line, big, fade(INK, progress))

        if t > 0.34:
            centred(draw, 512, "This one makes you earn it.", big,
                    fade(PROSECUTOR, ease((t - 0.34) / 0.24)))

        if t > 0.58:
            amount = ease((t - 0.58) / 0.22)
            centred(draw, 686, "DEVIL'S ADVOCATE  ·  OPEN SOURCE, MIT", small,
                    fade(FAINT, amount), spacing=5)
            centred(draw, 734, "github.com/mustafabakoglu/adversarial-debate-engine", url,
                    fade(INK, amount))

        rule = ease(min(1.0, max(0.0, (t - 0.5) / 0.3)))
        if rule > 0:
            draw.line([(W / 2 - 200 * rule, 850), (W / 2 - 24, 850)], fill=PROSECUTOR, width=6)
            draw.line([(W / 2 + 24, 850), (W / 2 + 200 * rule, 850)], fill=DEFENDER, width=6)

        frames.append(image)

    write(frames, "end")


if __name__ == "__main__":
    os.makedirs(ANIM, exist_ok=True)
    print("rendering animation frames")
    intro()
    pipeline_card()
    for name, lines, accent, seconds in CARDS:
        story_card(name, lines, accent, seconds)
    end_card()
    print("done")

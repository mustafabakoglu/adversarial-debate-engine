"""Title card, end card and lower-third captions for the demo video.

Rendered with PIL rather than ffmpeg's drawtext so the type can be laid out properly,
and coloured from the app's own palette so the cards do not look bolted on.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
CANVAS = (250, 250, 251)
INK = (42, 46, 53)
SOFT = (107, 114, 128)
FAINT = (156, 163, 175)
PROSECUTOR = (47, 107, 216)
DEFENDER = (208, 64, 47)

FONT_DIR = "C:/Windows/Fonts"
OUT = os.path.dirname(os.path.abspath(__file__))


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def centre(draw: ImageDraw.ImageDraw, y: int, text: str, fnt, fill, spacing: int = 0) -> int:
    if spacing:
        width = sum(draw.textlength(char, font=fnt) + spacing for char in text) - spacing
        x = (W - width) / 2
        for char in text:
            draw.text((x, y), char, font=fnt, fill=fill)
            x += draw.textlength(char, font=fnt) + spacing
    else:
        width = draw.textlength(text, font=fnt)
        draw.text(((W - width) / 2, y), text, font=fnt, fill=fill)
    bbox = fnt.getbbox(text)
    return y + (bbox[3] - bbox[1])


def title_card() -> None:
    image = Image.new("RGB", (W, H), CANVAS)
    draw = ImageDraw.Draw(image)

    centre(draw, 300, "ADVERSARIAL AI DEBATE ENGINE", font("segoeui.ttf", 26), FAINT, spacing=6)
    centre(draw, 380, "This AI does not agree", font("seguisb.ttf", 104), INK)
    centre(draw, 500, "with you.", font("seguisb.ttf", 104), INK)
    centre(
        draw,
        680,
        "Two agents argue opposite sides of your claim. A referee decides when",
        font("segoeui.ttf", 34),
        SOFT,
    )
    centre(
        draw,
        730,
        "it is actually finished. A judge scores the argument, not the answer.",
        font("segoeui.ttf", 34),
        SOFT,
    )

    draw.line([(760, 830), (860, 830)], fill=PROSECUTOR, width=5)
    draw.line([(1060, 830), (1160, 830)], fill=DEFENDER, width=5)
    image.save(os.path.join(OUT, "card_title.png"))


def end_card() -> None:
    image = Image.new("RGB", (W, H), CANVAS)
    draw = ImageDraw.Draw(image)

    centre(draw, 300, "Most assistants tell you", font("seguisb.ttf", 76), INK)
    centre(draw, 390, "what you want to hear.", font("seguisb.ttf", 76), INK)
    centre(draw, 510, "This one makes you earn it.", font("seguisb.ttf", 76), PROSECUTOR)

    centre(draw, 700, "OPEN SOURCE, MIT", font("segoeui.ttf", 24), FAINT, spacing=5)
    centre(
        draw,
        750,
        "github.com/mustafabakoglu/adversarial-debate-engine",
        font("seguisb.ttf", 38),
        INK,
    )
    centre(
        draw,
        830,
        "FastAPI · server-sent events · one model, four system prompts · no database",
        font("segoeui.ttf", 26),
        SOFT,
    )
    image.save(os.path.join(OUT, "card_end.png"))


CAPTIONS = {
    "blind": "Openings are written blind — neither side can see the other",
    "rebuttal": "Rebuttal round: attack what they actually said, quote the phrase",
    "cross": "Cross examination: one question each, answer first",
    "referee": "The referee decides whether the debate is finished — not a fixed round count",
    "bench": "The judge asks its own question. Both sides must answer it",
    "verdict": "Scored on how well they argued — not on who is right",
    "challenge": "You argue back. Both sides must answer you, and it can move the verdict",
    "language": "No language setting — it argues in the language of your claim",
}


def captions() -> None:
    fnt = font("seguisb.ttf", 34)
    for name, text in CAPTIONS.items():
        image = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        width = draw.textlength(text, font=fnt)
        pad = 34
        box = [(W - width) / 2 - pad, 18, (W + width) / 2 + pad, 96]
        draw.rounded_rectangle(box, radius=39, fill=(26, 29, 34, 224))
        draw.text(((W - width) / 2, 36), text, font=fnt, fill=(245, 246, 248, 255))
        image.save(os.path.join(OUT, f"cap_{name}.png"))


if __name__ == "__main__":
    title_card()
    end_card()
    captions()
    print("cards and captions written")

"""
Generate synthetic test labels so the app is testable out of the box.

The brief invites you to "create or source additional test labels." These
Pillow-drawn labels are deterministic and cover the key cases the agents care
about: a fully compliant label, plus three Government-Warning failure modes
(title-case lead-in, reworded text, and a missing warning).

Run:  python samples/generate_samples.py
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
FONT_DIR = "/usr/share/fonts/truetype/dejavu"

GOOD_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)
TITLECASE_WARNING = GOOD_WARNING.replace("GOVERNMENT WARNING:", "Government Warning:")
ALTERED_WARNING = (
    "GOVERNMENT WARNING: Drinking during pregnancy can cause birth defects. "
    "Do not drive after drinking."
)


def font(size, bold=False):
    # Try a few common fonts so this runs on Linux, macOS, and Windows.
    candidates = [
        f"{FONT_DIR}/{'DejaVuSans-Bold' if bold else 'DejaVuSans'}.ttf",  # Linux
        "arialbd.ttf" if bold else "arial.ttf",                            # Windows (Fonts dir)
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",               # fallback by name
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def make_label(filename, *, warning, brand="OLD TOM DISTILLERY",
               class_type="Kentucky Straight Bourbon Whiskey",
               abv="45% Alc./Vol. (90 Proof)", net="750 mL",
               producer="Bottled by Old Tom Distillery, Bardstown, KY"):
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, W - 20, H - 20], outline="#222", width=3)
    cx, y = W // 2, 70

    def center(text, fnt, fill="#111", gap=14):
        nonlocal y
        w = d.textlength(text, font=fnt)
        d.text((cx - w / 2, y), text, font=fnt, fill=fill)
        y += fnt.size + gap

    center(brand, font(46, bold=True)); y += 6
    center(class_type, font(26)); y += 26
    center(abv, font(30, bold=True)); y += 8
    center(net, font(26)); y += 30
    for line in wrap(d, producer, font(22), W - 160):
        center(line, font(22), fill="#333", gap=6)

    if warning:
        y = H - 300
        wfont = font(20, bold=False)
        for line in wrap(d, warning, wfont, W - 130):
            d.text((70, y), line, font=wfont, fill="#000")
            y += wfont.size + 6

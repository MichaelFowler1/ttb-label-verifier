#!/usr/bin/env python3
"""
Generate docs/hero.png - the README image.

Runs the REAL pipeline (local Tesseract OCR -> matching rules) on the bundled
sample labels and renders the actual verdicts: a full per-field verification of
the compliant label, plus the strict Government-Warning check catching all three
evasion modes. Nothing here is mocked.

Run (needs Tesseract + pytesseract + rapidfuzz + pillow + matplotlib):
    python make_hero.py
"""
import io
import os
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from PIL import Image

from app.ocr import ocr_image
from app.matching import verify

EXPECTED = {
    "brand_name": "Old Tom Distillery",
    "class_type": "Kentucky Straight Bourbon Whiskey",
    "alcohol_content": "45%",
    "net_contents": "750 mL",
    "producer": "Bottled by Old Tom Distillery, Bardstown, KY",
}
SAMPLES = {
    "good_label.png": "compliant",
    "titlecase_warning.png": "title-case lead-in",
    "altered_warning.png": "reworded text",
    "missing_warning.png": "no warning",
}

BG, PANEL, INK, DIM = "#0d0f14", "#161a22", "#e6ebf2", "#8493a6"
OK, BAD = "#28c76f", "#ff4d4d"


def run(fn):
    t = time.time()
    r = verify(EXPECTED, ocr_image(open(f"samples/{fn}", "rb").read()))
    r["_ms"] = (time.time() - t) * 1000
    return r


main = run("good_label.png")

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
fig = plt.figure(figsize=(13, 7.6), facecolor=BG)
fig.text(0.04, 0.95, "TTB  ·  AI ALCOHOL-LABEL VERIFICATION",
         fontsize=17, fontweight="bold")
fig.text(0.04, 0.907, "upload a label  →  local OCR (on-prem, no cloud)  →  fuzzy field match "
                      "+ strict 27 CFR 16.21 Government-Warning check  →  per-field verdict",
         fontsize=9.5, color=DIM)

# ---------- left: the label image ----------
axi = fig.add_axes([0.04, 0.20, 0.24, 0.66])
axi.imshow(Image.open("samples/good_label.png"))
axi.set_xticks([]); axi.set_yticks([])
for s in axi.spines.values():
    s.set_edgecolor("#2a3140")
axi.set_title("input label", fontsize=9, color=DIM, loc="left", pad=6)

# ---------- middle: per-field verdict card ----------
axc = fig.add_axes([0.31, 0.20, 0.40, 0.66], facecolor=PANEL)
axc.axis("off")
axc.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
              transform=axc.transAxes, facecolor=PANEL, edgecolor="#2a3140", lw=1.5))

badge = OK if main["overall_pass"] else BAD
axc.text(0.05, 0.93, "PASS" if main["overall_pass"] else "FAIL",
         fontsize=22, fontweight="bold", color=badge, transform=axc.transAxes)
axc.text(0.30, 0.945, f"application vs. label   ·   {main['_ms']:.0f} ms  (SLA < 5 s)",
         fontsize=9, color=DIM, transform=axc.transAxes)

FIELD_LABEL = {"brand_name": "Brand name", "class_type": "Class / type",
               "alcohol_content": "Alcohol content", "net_contents": "Net contents",
               "producer": "Producer"}
y = 0.80
for f in main["fields"]:
    mark, col = ("✓", OK) if f["passed"] else ("✗", BAD)
    axc.text(0.05, y, mark, fontsize=13, fontweight="bold", color=col, transform=axc.transAxes)
    axc.text(0.11, y, FIELD_LABEL.get(f["field"], f["field"]), fontsize=10.5,
             color=INK, transform=axc.transAxes)
    axc.text(0.62, y, f"fuzzy {f['score']:.0f}%", fontsize=9.5, color=DIM,
             transform=axc.transAxes)
    y -= 0.088

# warning block
w = main["warning"]
wmark, wcol = ("✓", OK) if w["passed"] else ("✗", BAD)
axc.add_patch(FancyBboxPatch((0.04, 0.05), 0.92, 0.28, boxstyle="round,pad=0,rounding_size=0.02",
              transform=axc.transAxes, facecolor="#10141b",
              edgecolor=wcol, lw=1.4))
axc.text(0.07, 0.25, f"{wmark}  GOVERNMENT WARNING", fontsize=11, fontweight="bold",
         color=wcol, transform=axc.transAxes)
axc.text(0.07, 0.15, f"strict 27 CFR 16.21 check  ·  wording {w['score']:.0f}%  ·  "
                     "all-caps lead-in required", fontsize=8.6, color=DIM,
         transform=axc.transAxes)
axc.text(0.07, 0.075, "matched canonical text word-for-word" if w["passed"]
         else (w["issues"][0] if w["issues"] else ""), fontsize=8.4,
         color=OK if w["passed"] else BAD, transform=axc.transAxes, style="italic")

# ---------- right: the anti-evasion story ----------
axr = fig.add_axes([0.74, 0.20, 0.22, 0.66], facecolor=PANEL)
axr.axis("off")
axr.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02",
              transform=axr.transAxes, facecolor=PANEL, edgecolor="#2a3140", lw=1.5))
axr.text(0.08, 0.93, "WARNING EVASIONS\nCAUGHT", fontsize=11, fontweight="bold",
         color=INK, transform=axr.transAxes)
yy = 0.72
for fn, desc in SAMPLES.items():
    r = run(fn)
    ok = r["overall_pass"]
    mark, col = ("PASS", OK) if ok else ("FAIL", BAD)
    axr.text(0.08, yy, desc, fontsize=9.5, color=INK, transform=axr.transAxes)
    axr.text(0.08, yy - 0.05, f"warning {r['warning']['score']:.0f}%", fontsize=8,
             color=DIM, transform=axr.transAxes)
    axr.text(0.92, yy, mark, fontsize=10, fontweight="bold", color=col,
             ha="right", transform=axr.transAxes)
    yy -= 0.165

fig.text(0.04, 0.03, "Real output — local Tesseract OCR on the bundled sample labels, "
                     "no cloud calls. Regenerate with python make_hero.py",
         fontsize=8, color=DIM)

os.makedirs("docs", exist_ok=True)
fig.savefig("docs/hero.png", dpi=140, facecolor=BG)
print("[+] wrote docs/hero.png")

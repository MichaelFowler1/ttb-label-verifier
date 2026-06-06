"""
OCR with lightweight preprocessing.

Tesseract runs locally (no outbound calls): Marcus Williams flagged that the agency
firewall blocks external ML endpoints and killed the last vendor's cloud features, so
an on-box OCR engine is the safe architectural bet. Preprocessing is intentionally
light (EXIF rotation, grayscale, auto-contrast, upscale) to tolerate imperfect photos
cheaply; heavier correction (deskew, glare removal) is left as a documented next step.
"""
from __future__ import annotations

import io
import os
import shutil
import sys

import pytesseract
from PIL import Image, ImageOps

# On Windows, Tesseract is frequently not added to PATH by its installer. If the
# binary isn't discoverable, fall back to the default install location so the app
# works out of the box. No-op on Linux/macOS / Docker, where Tesseract is on PATH.
if shutil.which("tesseract") is None and sys.platform.startswith("win"):
    for _candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.exists(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break


def preprocess(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)      # respect camera orientation
    img = img.convert("L")                   # grayscale
    img = ImageOps.autocontrast(img)         # normalize lighting/contrast
    w, h = img.size
    if max(w, h) < 1000:                     # upscale small images for OCR
        scale = 1000.0 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)))
    return img


def ocr_image(data: bytes) -> str:
    """Return raw OCR text (case preserved, so casing checks stay meaningful)."""
    img = Image.open(io.BytesIO(data))
    img = preprocess(img)
    return pytesseract.image_to_string(img)

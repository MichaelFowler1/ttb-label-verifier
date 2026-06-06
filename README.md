# TTB AI-Powered Alcohol Label Verification

A prototype that helps a TTB compliance agent confirm that an alcohol label image
matches the data in its application — and that the mandatory Government Health
Warning is present and correctly formatted. Upload a label, enter the application
details, get an instant per-field verdict. Supports single labels and bulk
(peak-season) batches.

> Built as a take-home prototype. Standalone proof-of-concept — no COLA integration.

---

## What it checks

| Check | Logic | Why |
|---|---|---|
| Brand name, class/type, net contents, producer, country | **Fuzzy** match (case/punctuation-insensitive, similarity ≥ 85) | "STONE'S THROW" vs "Stone's Throw" is the same product — literal matching would wrongly reject it |
| Alcohol content (ABV) | Parsed from label text, compared within ±0.1 percentage points | Catches real mismatches without tripping on formatting |
| Government Health Warning | **Strict**: wording ≥ 90% match to the canonical 27 CFR 16.21 text **and** an all-caps `GOVERNMENT WARNING:` lead-in | Must be exact; producers evade with title case, reworded, or shrunken text |

The fuzzy-vs-strict split is deliberate — it's the central tension in the brief.

## Requirements reverse-engineered from the stakeholder interviews

The actual requirements are embedded in the interview notes, not the spec. What I
pulled out and how it's addressed:

- **≤ 5-second results (Sarah Chen).** Local OCR returns in ~0.2–0.8s per label on
  a modest box — measured, see Testing. The prior vendor's 30–40s is what got it
  abandoned, so this was treated as a hard SLA.
- **Firewall blocks external ML endpoints (Marcus Williams).** OCR runs **locally**
  via Tesseract — no outbound calls — so it works behind the agency firewall. This
  is the single biggest architectural decision.
- **Dead-simple UI, 73-year-old benchmark, half the team 50+ (Sarah Chen).** Large
  type, high contrast, big touch targets, plain-language results, keyboard- and
  screen-reader-friendly, pass/fail shown with words + icons (not color alone).
- **Fuzzy brand matching (Dave Morrison).** See table above.
- **Strict, exact warning with anti-evasion (Jenny Park).** See table above.
- **Batch uploads of 200–300 (Sarah Chen / Janet, Seattle).** `/api/verify-batch`
  + a batch tab; optional CSV maps each filename to its own application data.
- **Imperfect photos (Jenny Park).** EXIF-rotation, grayscale, auto-contrast, and
  upscaling handle orientation and lighting cheaply. Marked nice-to-have in the
  brief; heavier correction is listed under Next steps rather than over-built.
- **Standalone, minimal security for a prototype (Marcus Williams).** No COLA
  integration, nothing sensitive stored, images processed in memory.

## Architecture

```
app/
  main.py       FastAPI: routes, single + batch verification, serves the UI
  ocr.py        Image preprocessing + local Tesseract OCR
  matching.py   Normalization, fuzzy field matching, strict warning check
static/
  index.html    Single-file operator UI (no build step, vanilla JS)
samples/
  generate_samples.py   Creates 4 synthetic test labels (good + 3 failure modes)
tests/
  test_matching.py      Unit tests for the matching/warning rules
Dockerfile · requirements.txt
```

Clean separation: OCR (input), matching (rules), API/UI (delivery). The rules are
pure functions, which is why they're easy to unit-test.

## Run it locally

```bash
# Requires Tesseract (the OCR engine):
#   Ubuntu/Debian:  sudo apt-get install tesseract-ocr
#   macOS (brew):   brew install tesseract
#   Windows:        https://github.com/UB-Mannheim/tesseract/wiki

pip install -r requirements.txt
python samples/generate_samples.py        # optional: create test labels
uvicorn app.main:app --reload             # open http://127.0.0.1:8000
```

### Or with Docker (Tesseract included)

```bash
docker build -t ttb-label-verifier .
docker run -p 8000:8000 ttb-label-verifier
```

## Deploy a public URL

The included `Dockerfile` honors `$PORT`, so any Docker host works:

- **Render** – New → Web Service → connect the GitHub repo → it auto-detects the
  Dockerfile → Deploy. Free tier gives a public `*.onrender.com` URL (cold-starts).
- **Hugging Face Spaces** – New Space → SDK: *Docker* → push the repo.
- **Railway / Fly.io** – both deploy this Dockerfile directly.

## API

`POST /api/verify` — multipart form: `file` (image) + optional `brand_name`,
`class_type`, `alcohol_content`, `net_contents`, `producer`, `country_of_origin`.

```jsonc
{
  "overall_pass": true,
  "elapsed_ms": 796,
  "fields": [{"field":"brand_name","expected":"Old Tom Distillery",
              "found":"Old Tom Distillery","score":100.0,"passed":true,"note":"Match"}],
  "warning": {"passed": true, "score": 100.0, "issues": [], "found_text": "GOVERNMENT WARNING: ..."},
  "ocr_text": "..."
}
```

`POST /api/verify-batch` — `files` (many images) + optional `mapping_csv` and/or the
shared form fields. Returns `{summary, results[]}`.

**Batch CSV format** (header row): `filename, brand_name, class_type,
alcohol_content, net_contents, producer, country_of_origin`. Rows are matched to
images by filename; unmatched images fall back to the shared form fields, and with
neither they still get the mandatory Government Warning check.

## Testing

```bash
pytest -q          # 10 tests covering fuzzy match, ABV, and all warning cases
```

Covered: case/punctuation-insensitive brand match, brand mismatch, ABV parse +
tolerance, and the four warning states (valid, title-case, reworded, missing).

**Measured (synthetic labels, single CPU):** compliant label → pass, all fields
100%, in **~0.8s**; title-case warning → correctly failed; missing warning →
correctly failed. All well under the 5-second target.

## Assumptions, trade-offs & limitations

- **OCR vs. layout.** Reading text can't measure font *size*, so a warning printed
  legibly-but-tiny still reads as present. Production fix: use Tesseract's
  word-level bounding boxes (`image_to_data`) to flag a warning rendered much
  smaller than surrounding text. Noted, not built, to keep the prototype focused.
- **Thresholds are tunable constants** in `matching.py` (field 85, warning wording
  90). I'd calibrate these against a labeled sample set with the compliance team.
- **One language / Latin script.** English Tesseract only; imports in other scripts
  would need additional language packs.
- **Expected values are entered/uploaded**, not pulled from COLA — by design for a
  standalone prototype.
- **No persistence / auth.** A production deployment needs PII handling, retention
  policy, and access control (out of scope here per Marcus).

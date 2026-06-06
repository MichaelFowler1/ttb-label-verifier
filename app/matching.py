"""
Field matching and Government Warning verification.

The brief hides two *opposite* matching requirements in the stakeholder
interviews, and getting both right is the core of this exercise:

1. Most fields (brand name, class/type, producer ...) need FUZZY, judgment-based
   matching. Dave Morrison's example: "STONE'S THROW" on the label vs
   "Stone's Throw" in the application is obviously the same product, so a literal
   string comparison would wrongly reject it. We normalize aggressively (case,
   punctuation, whitespace) and score similarity against a tunable threshold.

2. The Government Health Warning needs the OPPOSITE — strict verification. Jenny
   Park: it must be present, word-for-word, with the "GOVERNMENT WARNING:" lead-in
   in ALL CAPS. Producers evade with title case, reworded text, or tiny fonts. So
   we (a) compare the wording closely to the canonical TTB text and (b) separately
   confirm the all-caps lead-in in the *raw* OCR output.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field as dc_field
from typing import Optional

from rapidfuzz import fuzz

# Canonical TTB Government Warning — 27 CFR 16.21
GOVERNMENT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to drive "
    "a car or operate machinery, and may cause health problems."
)

# Tunable thresholds (documented in the README so reviewers can see the trade-offs)
FIELD_MATCH_THRESHOLD = 85.0      # fuzzy fields: pass at/above this similarity
ABV_TOLERANCE = 0.1               # percentage points of allowed ABV drift
WARNING_PRESENT_THRESHOLD = 80.0  # below this, the warning is treated as absent
WARNING_WORDING_THRESHOLD = 90.0  # wording must be at least this close to canonical


# --------------------------------------------------------------------------- #
# normalization helpers
# --------------------------------------------------------------------------- #
def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace — for fuzzy comparison."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --------------------------------------------------------------------------- #
# result containers
# --------------------------------------------------------------------------- #
@dataclass
class FieldResult:
    field: str
    expected: Optional[str]
    found: Optional[str]
    score: float
    passed: bool
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WarningResult:
    passed: bool
    score: float
    issues: list
    found_text: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# field matchers
# --------------------------------------------------------------------------- #
def match_text_field(name: str, expected: str, full_text: str,
                     threshold: float = FIELD_MATCH_THRESHOLD) -> FieldResult:
    """Fuzzy-match an expected value against the full OCR text of the label."""
    if not expected:
        return FieldResult(name, expected, None, 0.0, False, "No expected value provided")
    ne, nt = normalize(expected), normalize(full_text)
    # partial_ratio finds the best-aligned window, so the expected value can sit
    # anywhere inside the label text.
    score = float(fuzz.partial_ratio(ne, nt))
    passed = score >= threshold
    note = "Match" if passed else "Not found on label, or differs from application"
    return FieldResult(name, expected, expected if passed else None, round(score, 1), passed, note)


ABV_PATTERNS = [
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:alc|abv)",        # 45% Alc / 45% ABV
    r"alc[^0-9]{0,8}(\d{1,2}(?:\.\d+)?)\s*%",         # Alc. by Vol ... 45%
    r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:by\s*vol|vol)",    # 45% by Vol
    r"(\d{1,2}(?:\.\d+)?)\s*%",                        # bare 45% (fallback)
]


def extract_abv(full_text: str) -> Optional[float]:
    t = (full_text or "").lower()
    for pat in ABV_PATTERNS:
        m = re.search(pat, t)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _parse_number(value: str) -> Optional[float]:
    m = re.search(r"(\d{1,2}(?:\.\d+)?)", str(value or ""))
    return float(m.group(1)) if m else None


def match_abv(expected: str, full_text: str, tolerance: float = ABV_TOLERANCE) -> FieldResult:
    found = extract_abv(full_text)
    exp_val = _parse_number(expected)
    if exp_val is None:
        return FieldResult("alcohol_content", str(expected), None, 0.0, False,
                           "No expected ABV provided")
    if found is None:
        return FieldResult("alcohol_content", f"{exp_val}%", None, 0.0, False,
                           "No alcohol content detected on label")
    passed = abs(found - exp_val) <= tolerance
    score = 100.0 if passed else max(0.0, 100.0 - abs(found - exp_val) * 20)
    note = "Match" if passed else f"Label shows {found}% but application says {exp_val}%"
    return FieldResult("alcohol_content", f"{exp_val}%", f"{found}%", round(score, 1), passed, note)


# --------------------------------------------------------------------------- #
# government warning — strict
# --------------------------------------------------------------------------- #
def _warning_snippet(raw_text: str) -> Optional[str]:
    m = re.search(r"government\s+warning", raw_text or "", re.IGNORECASE)
    if not m:
        return None
    return (raw_text[m.start():m.start() + 280]).strip()


def check_government_warning(raw_text: str) -> WarningResult:
    """Strict check: correct wording AND an all-caps 'GOVERNMENT WARNING:' lead-in."""
    raw_text = raw_text or ""
    issues: list[str] = []

    wording_score = float(fuzz.partial_ratio(normalize(GOVERNMENT_WARNING), normalize(raw_text)))
    has_caps_leadin = bool(re.search(r"GOVERNMENT WARNING\s*:", raw_text))
    has_any_leadin = bool(re.search(r"government\s+warning\s*:?", raw_text, re.IGNORECASE))

    present = wording_score >= WARNING_PRESENT_THRESHOLD or has_any_leadin
    if not present:
        issues.append("Government Warning statement not found on the label.")
        return WarningResult(False, round(wording_score, 1), issues, None)

    if not has_caps_leadin:
        if has_any_leadin:
            issues.append('"GOVERNMENT WARNING:" must be in all capital letters '
                          "(found different casing — e.g. title case).")
        else:
            issues.append('Missing the required "GOVERNMENT WARNING:" lead-in.')

    if wording_score < WARNING_WORDING_THRESHOLD:
        issues.append(f"Warning wording differs from the required statement "
                      f"(similarity {wording_score:.0f}%). Check for altered, "
                      f"shortened, or missing language.")

    passed = has_caps_leadin and wording_score >= WARNING_WORDING_THRESHOLD
    return WarningResult(passed, round(wording_score, 1), issues, _warning_snippet(raw_text))


# --------------------------------------------------------------------------- #
# top-level orchestration
# --------------------------------------------------------------------------- #
# fuzzy text fields we know how to check (everything except ABV, handled separately)
TEXT_FIELDS = ["brand_name", "class_type", "net_contents", "producer", "country_of_origin"]


def verify(expected: dict, raw_text: str) -> dict:
    """Run all applicable field checks plus the mandatory Government Warning check."""
    expected = expected or {}
    field_results: list[FieldResult] = []

    for name in TEXT_FIELDS:
        if expected.get(name):
            field_results.append(match_text_field(name, expected[name], raw_text))
    if expected.get("alcohol_content"):
        field_results.append(match_abv(expected["alcohol_content"], raw_text))

    warning = check_government_warning(raw_text)

    fields_pass = all(fr.passed for fr in field_results) if field_results else True
    overall = bool(fields_pass and warning.passed)

    return {
        "overall_pass": overall,
        "fields": [fr.to_dict() for fr in field_results],
        "warning": warning.to_dict(),
        "ocr_text": raw_text,
    }

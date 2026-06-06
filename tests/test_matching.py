"""
Unit tests for the matching/warning logic — the part most worth pinning down,
since it encodes the brief's subtle rules. Run:  pytest -q
"""
from app import matching as m

LABEL_TEXT = (
    "OLD TOM DISTILLERY\n"
    "Kentucky Straight Bourbon Whiskey\n"
    "45% Alc./Vol. (90 Proof)\n"
    "750 mL\n"
    "Bottled by Old Tom Distillery, Bardstown, KY\n"
    + m.GOVERNMENT_WARNING
)


# --- fuzzy field matching (Dave Morrison's "STONE'S THROW" case) ------------
def test_brand_case_and_punctuation_insensitive():
    label = "STONE'S THROW BOURBON 45% Alc./Vol."
    r = m.match_text_field("brand_name", "Stone's Throw", label)
    assert r.passed and r.score >= 90


def test_brand_mismatch_fails():
    r = m.match_text_field("brand_name", "Old Tom Distillery", "NEW CROW WHISKEY CO")
    assert not r.passed


# --- ABV parsing & tolerance ------------------------------------------------
def test_abv_parsed_and_matched():
    r = m.match_abv("45%", "45% Alc./Vol. (90 Proof)")
    assert r.passed and r.found == "45.0%"


def test_abv_mismatch_flagged():
    r = m.match_abv("40%", "45% Alc./Vol.")
    assert not r.passed


# --- Government Warning: strict ---------------------------------------------
def test_warning_valid_passes():
    w = m.check_government_warning(LABEL_TEXT)
    assert w.passed and not w.issues


def test_warning_titlecase_caught():
    text = LABEL_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    w = m.check_government_warning(text)
    assert not w.passed
    assert any("capital" in i.lower() for i in w.issues)


def test_warning_reworded_caught():
    text = "GOVERNMENT WARNING: Do not drink while pregnant. Do not drive."
    w = m.check_government_warning(text)
    assert not w.passed
    assert any("wording" in i.lower() for i in w.issues)


def test_warning_missing_caught():
    w = m.check_government_warning("OLD TOM DISTILLERY 45% Alc./Vol. 750 mL")
    assert not w.passed
    assert any("not found" in i.lower() for i in w.issues)


# --- end-to-end orchestration ----------------------------------------------
def test_verify_overall_pass():
    expected = {"brand_name": "Old Tom Distillery", "alcohol_content": "45%",
                "net_contents": "750 mL"}
    res = m.verify(expected, LABEL_TEXT)
    assert res["overall_pass"] is True


def test_verify_fails_on_bad_warning():
    text = LABEL_TEXT.replace("GOVERNMENT WARNING:", "Government Warning:")
    res = m.verify({"brand_name": "Old Tom Distillery"}, text)
    assert res["overall_pass"] is False

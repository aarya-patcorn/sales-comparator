"""Iteration 3 backend tests:
- /api/compare returns kamdhenu_advantage flag
- /api/pitch supports variant param + cache key includes variant
- Variant pitches differ
- Lines reference real-world tile contractor problems
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://adhesive-selector.preview.emergentagent.com").rstrip("/")


# -- /api/compare kamdhenu_advantage flag
def test_compare_returns_kamdhenu_advantage_flag():
    r = requests.post(f"{BASE_URL}/api/compare", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6", "mapei::8"],
        "custom_products": [],
    }, timeout=20)
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) > 0
    for row in rows:
        assert "kamdhenu_advantage" in row, f"Missing kamdhenu_advantage in row: {row}"
        assert isinstance(row["kamdhenu_advantage"], bool)
    # At least some rows should mark kamdhenu winning (numerical params)
    wins = [r for r in rows if r["kamdhenu_advantage"]]
    assert len(wins) >= 1, "Expected at least one kamdhenu_advantage=True row"


# -- /api/pitch variants
@pytest.fixture(scope="module")
def base_pitch_payload():
    return {
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6"],
        "custom_products": [],
    }


def _post_pitch(payload, variant):
    body = {**payload, "variant": variant}
    r = requests.post(f"{BASE_URL}/api/pitch", json=body, timeout=180)
    assert r.status_code == 200, r.text
    return r.json()["pitches"][0]["lines"]


def test_pitch_variant_1_durability(base_pitch_payload):
    lines = _post_pitch(base_pitch_payload, 1)
    assert len(lines) >= 1
    joined = " ".join(lines).lower()
    # Variant 1 = durability angle. Expect references to freeze-thaw / heat / water / aging
    keywords = ["freeze", "thaw", "heat", "water", "aging", "ageing", "durab", "shelf", "long"]
    assert any(k in joined for k in keywords), f"Variant1 lines lack durability keywords: {lines}"


def test_pitch_variant_2_safety_economics(base_pitch_payload):
    lines = _post_pitch(base_pitch_payload, 2)
    assert len(lines) >= 1
    joined = " ".join(lines).lower()
    keywords = ["voc", "coverage", "yield", "bag", "mix", "temperature", "economic", "safe", "indoor"]
    assert any(k in joined for k in keywords), f"Variant2 lines lack safety/economics keywords: {lines}"


def test_pitch_variant_0_vs_1_differ(base_pitch_payload):
    v0 = _post_pitch(base_pitch_payload, 0)
    v1 = _post_pitch(base_pitch_payload, 1)
    # Cache key includes variant => the two arrays should not be identical
    assert v0 != v1, f"Variant 0 and 1 are identical (cache key may not include variant). v0={v0}"


def test_pitch_lines_real_world_problems(base_pitch_payload):
    # Use variant 0 (default angle) — prompt explicitly asks for real-world problems
    lines = _post_pitch(base_pitch_payload, 0)
    joined = " ".join(lines).lower()
    real_world = [
        "debond", "slip", "freeze", "thaw", "callback", "sag", "vertical",
        "hollow", "pop", "crack", "bathroom", "pool", "kitchen", "facade",
        "vitrified", "porcelain", "large-format", "large format", "voc",
        "open time", "wet", "substrate",
    ]
    hits = [k for k in real_world if k in joined]
    assert len(hits) >= 1, f"No real-world problem keywords in pitch lines: {lines}"


def test_pitch_variant_default_when_omitted(base_pitch_payload):
    # variant field default = 0 -> endpoint should still return 200 without variant key
    r = requests.post(f"{BASE_URL}/api/pitch", json=base_pitch_payload, timeout=180)
    assert r.status_code == 200
    assert len(r.json()["pitches"][0]["lines"]) >= 1

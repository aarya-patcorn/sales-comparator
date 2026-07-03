"""Backend tests for /api/pitch (AI sales pitch generation + caching)."""
import os
import time
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://adhesive-selector.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def mongo_db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


# Compare regression
def test_compare_still_works():
    r = requests.post(f"{BASE_URL}/api/compare", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6"],
        "custom_products": [],
    }, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "columns" in d and "rows" in d
    assert len(d["columns"]) == 2
    assert d["columns"][0]["is_kamdhenu"] is True


# Single competitor pitch
def test_pitch_single_competitor(mongo_db):
    r = requests.post(f"{BASE_URL}/api/pitch", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6"],
        "custom_products": [],
    }, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "pitches" in d
    assert len(d["pitches"]) == 1
    p = d["pitches"][0]
    assert "competitor_brand" in p
    assert "competitor_name" in p
    assert "lines" in p
    assert isinstance(p["lines"], list)
    assert 1 <= len(p["lines"]) <= 3
    for ln in p["lines"]:
        assert isinstance(ln, str) and len(ln) > 5

    # Cache check
    cnt = mongo_db.pitch_cache.count_documents({"kamdhenu_code": "K90"})
    assert cnt >= 1


# Cache hit performance
def test_pitch_cache_hit_faster():
    payload = {
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6"],
        "custom_products": [],
    }
    # Warm
    requests.post(f"{BASE_URL}/api/pitch", json=payload, timeout=120)
    t0 = time.time()
    r2 = requests.post(f"{BASE_URL}/api/pitch", json=payload, timeout=30)
    elapsed = time.time() - t0
    assert r2.status_code == 200
    # Cache hit should be < 5s (LLM call typically > 5s)
    assert elapsed < 5.0, f"Cache hit took {elapsed:.2f}s, expected < 5s"


# Multiple competitors
def test_pitch_multiple_competitors():
    r = requests.post(f"{BASE_URL}/api/pitch", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6", "mapei::8"],
        "custom_products": [],
    }, timeout=180)
    assert r.status_code == 200
    d = r.json()
    assert len(d["pitches"]) == 2
    brands = {p["competitor_brand"] for p in d["pitches"]}
    assert "MYK Laticrete" in brands or "Myk Laticrete" in brands or any("Laticrete" in b for b in brands)
    assert any("Mapei" in b for b in brands)


# Custom products
def test_pitch_with_custom_product():
    r = requests.post(f"{BASE_URL}/api/pitch", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": [],
        "custom_products": [{"name": "TEST_CustomTile", "brand": "TEST_Brand", "is_type": "Type 2T", "en_type": "C2TE"}],
    }, timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert len(d["pitches"]) == 1
    assert d["pitches"][0]["competitor_brand"] == "TEST_Brand"
    assert len(d["pitches"][0]["lines"]) >= 1


# Invalid kamdhenu code
def test_pitch_invalid_code():
    r = requests.post(f"{BASE_URL}/api/pitch", json={
        "kamdhenu_code": "INVALID_X",
        "competitor_product_ids": [],
        "custom_products": [],
    }, timeout=15)
    assert r.status_code == 404


# Lines reference numerical params
def test_pitch_lines_cite_numbers():
    r = requests.post(f"{BASE_URL}/api/pitch", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": ["myk_laticrete::6"],
        "custom_products": [],
    }, timeout=120)
    assert r.status_code == 200
    lines = r.json()["pitches"][0]["lines"]
    joined = " ".join(lines).lower()
    # Expect at least one digit appears (citing parameter values)
    assert any(ch.isdigit() for ch in joined), f"No digits in pitch lines: {lines}"

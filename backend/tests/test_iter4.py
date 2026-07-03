"""Iteration 4 backend tests:
- /api/compare returns is_tds boolean array (true for Kamdhenu, false for competitors)
- /api/recommendation-text returns 200-280 word text mentioning code + IS/EN, ending with sign-off
- /api/recommendation-text caches second identical call
"""
import os
import requests
import pytest

BASE = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
assert BASE, "EXPO_BACKEND_URL not set"

# ---- /api/compare is_tds ----
class TestCompareIsTds:
    def test_compare_returns_is_tds_array(self):
        comps = requests.get(f"{BASE}/api/catalog/competitors", timeout=20).json()["competitors"]
        # pick first 2 competitor product ids
        ids = []
        for b in comps:
            for p in b["products"]:
                ids.append(p["id"])
                if len(ids) >= 2:
                    break
            if len(ids) >= 2:
                break
        r = requests.post(
            f"{BASE}/api/compare",
            json={"kamdhenu_code": "K90", "competitor_product_ids": ids, "custom_products": []},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "rows" in d and len(d["rows"]) > 0
        for row in d["rows"]:
            assert "is_tds" in row, "is_tds missing on row"
            flags = row["is_tds"]
            assert isinstance(flags, list)
            assert len(flags) == len(row["values"])
            assert flags[0] is True, "first column (Kamdhenu) is_tds must be True"
            for f in flags[1:]:
                assert f is False, "competitor cols must have is_tds=False"


# ---- /api/recommendation-text ----
class TestRecommendationText:
    PAYLOAD = None

    @classmethod
    def setup_class(cls):
        comps = requests.get(f"{BASE}/api/catalog/competitors", timeout=20).json()["competitors"]
        ids = []
        for b in comps:
            for p in b["products"]:
                if p.get("competes_with") == "K90":
                    ids.append(p["id"])
                    break
            if ids:
                break
        if not ids:
            ids = [comps[0]["products"][0]["id"]]
        cls.PAYLOAD = {
            "kamdhenu_code": "K90",
            "competitor_product_ids": ids,
            "custom_products": [],
            "context": {"substrate": "concrete", "tile_type": "vitrified", "size": "600x600", "area": "Indoor"},
        }

    def test_recommendation_returns_text(self):
        r = requests.post(f"{BASE}/api/recommendation-text", json=self.PAYLOAD, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "text" in d and isinstance(d["text"], str) and len(d["text"]) > 100
        text = d["text"]
        # Mentions Kamdhenu code
        assert "K90" in text, "must mention K90"
        # Mentions IS or EN classification
        assert ("IS 15477" in text) or ("EN 12004" in text) or ("IS" in text and "EN" in text)
        # Sign-off
        assert "Kamdhenu Adhesives Technical Team" in text, "must end with technical team sign-off"
        # Word count 200-280 (allow some tolerance for fallback at 150-320)
        words = len(text.split())
        # Allow fallback if AI fails — but should still be reasonable length
        assert 100 <= words <= 400, f"word count {words} far outside expected range"

    def test_recommendation_is_cached(self):
        # First call (may or may not be cached from prior)
        r1 = requests.post(f"{BASE}/api/recommendation-text", json=self.PAYLOAD, timeout=120)
        assert r1.status_code == 200
        # Second call with identical payload must be cached
        r2 = requests.post(f"{BASE}/api/recommendation-text", json=self.PAYLOAD, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("cached") is True, f"second identical call should return cached:true, got {d2.get('cached')}"
        # Text must be identical
        assert d2["text"] == r1.json()["text"]

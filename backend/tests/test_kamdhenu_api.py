"""Backend API tests for Kamdhenu Adhesive Comparator."""
import os
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://adhesive-selector.preview.emergentagent.com").rstrip("/")
DEV_TOKEN = "dev_session_kamdhenu_2026"
H = {"Authorization": f"Bearer {DEV_TOKEN}"}


# Catalog
def test_substrates():
    r = requests.get(f"{BASE_URL}/api/catalog/substrates", timeout=15)
    assert r.status_code == 200
    subs = r.json()["substrates"]
    assert len(subs) == 15
    assert any(s["id"] == "plywood" for s in subs)


def test_tile_types_filtered_plywood():
    r = requests.get(f"{BASE_URL}/api/catalog/tile-types", params={"substrate_id": "plywood"}, timeout=15)
    assert r.status_code == 200
    tt = r.json()["tile_types"]
    assert 0 < len(tt) < 14
    ids = [t["id"] for t in tt]
    assert "marble" not in ids and "vitrified" in ids


def test_tile_types_all():
    r = requests.get(f"{BASE_URL}/api/catalog/tile-types", timeout=15)
    assert r.status_code == 200
    assert len(r.json()["tile_types"]) == 14


def test_areas():
    r = requests.get(f"{BASE_URL}/api/catalog/areas", timeout=15)
    assert r.status_code == 200
    areas = r.json()["areas"]
    assert len(areas) == 8
    assert "Swimming Pool" in areas


def test_kamdhenu_catalog():
    r = requests.get(f"{BASE_URL}/api/catalog/kamdhenu", timeout=15)
    assert r.status_code == 200
    prods = r.json()["products"]
    codes = [p["code"] for p in prods]
    assert codes == ["K50", "K60", "K80", "K90", "KX"]
    for p in prods:
        assert "params" in p and len(p["params"]) >= 15
        assert "is_type" in p and "en_type" in p


def test_competitors():
    r = requests.get(f"{BASE_URL}/api/catalog/competitors", timeout=15)
    assert r.status_code == 200
    comps = r.json()["competitors"]
    assert len(comps) == 4
    names = [c["name"] for c in comps]
    assert "Mapei" in names and "Kerakoll" in names
    for c in comps:
        for p in c["products"]:
            assert "::" in p["id"]


# Recommendation
@pytest.mark.parametrize("payload,expected_in", [
    ({"substrate_id": "plywood", "tile_type_id": "vitrified", "tile_size": "48 x 96 in", "area": "Living Room"}, ["KX"]),
    ({"substrate_id": "plywood", "tile_type_id": "porcelain", "tile_size": "24 x 48 in", "area": "Living Room"}, ["K90"]),
    ({"substrate_id": "concrete", "tile_type_id": "marble", "tile_size": "48 x 48 in", "area": "Living Room"}, ["K90"]),
    ({"substrate_id": "concrete", "tile_type_id": "vitrified", "tile_size": "12 x 12 in", "area": "Swimming Pool"}, ["KX"]),
    ({"substrate_id": "concrete", "tile_type_id": "ceramic", "tile_size": "12 x 12 in", "area": "Kitchen"}, ["K50"]),
])
def test_recommend(payload, expected_in):
    r = requests.post(f"{BASE_URL}/api/recommend", json=payload, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["recommendation"]["code"] in expected_in
    assert isinstance(data["reasons"], list) and len(data["reasons"]) > 0


# Compare
def test_compare():
    # Get a competitor product id
    comps = requests.get(f"{BASE_URL}/api/catalog/competitors", timeout=15).json()["competitors"]
    cid = comps[0]["products"][0]["id"]
    r = requests.post(f"{BASE_URL}/api/compare", json={
        "kamdhenu_code": "K90",
        "competitor_product_ids": [cid],
        "custom_products": [{"name": "Test", "brand": "X", "is_type": "Type 2T", "en_type": "C2TE"}],
    }, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["columns"][0]["is_kamdhenu"] is True
    assert data["columns"][0]["brand"] == "Kamdhenu"
    assert len(data["columns"]) == 3
    assert len(data["rows"]) > 10
    assert isinstance(data["kamdhenu_pitches"], list) and len(data["kamdhenu_pitches"]) > 0


# Auth
def test_auth_me_with_token():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=H, timeout=15)
    assert r.status_code == 200
    u = r.json()
    assert u["email"] == "dev.sales@kamdhenu.test"
    assert u["name"] == "Dev Sales User"


def test_auth_me_no_token():
    r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 401


def test_admin_add_product_requires_auth():
    r = requests.post(f"{BASE_URL}/api/admin/products", json={"name": "X", "brand": "Y"}, timeout=15)
    assert r.status_code == 401


def test_admin_add_product_with_auth():
    r = requests.post(f"{BASE_URL}/api/admin/products", json={
        "name": "TEST_Custom", "brand": "TEST_Brand", "is_type": "Type 2T", "en_type": "C2TE"
    }, headers=H, timeout=15)
    assert r.status_code == 200
    assert r.json()["ok"] is True

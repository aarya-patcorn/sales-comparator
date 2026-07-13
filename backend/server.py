from fastapi import FastAPI, APIRouter, HTTPException, Header, Request, Query
import asyncio
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorClient
from openai import OpenAI
import os
import logging
import uuid
import requests as http_requests
from pathlib import Path
from pydantic import BaseModel, Field
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta

from seed_data import (
    SUBSTRATES, TILE_TYPES, AREAS, SUBSTRATE_TILE_MAP,
    KAMDHENU_PRODUCTS, COMPETITORS, recommend_kamdhenu, enrich_competitor_params
)
from competitor_tds import (
    COMPETITOR_TDS_COLLECTION,
    ensure_seeded as ensure_competitor_tds_seeded,
    list_docs as list_competitor_tds_docs,
    list_due_docs as list_due_competitor_tds_docs,
    list_changed_docs as list_changed_competitor_tds_docs,
    get_doc_or_raise as get_competitor_tds_doc_or_raise,
    resolve_competitor as resolve_tds_competitor,
    sync_doc as sync_competitor_tds_doc,
    approve_pending_report as approve_competitor_tds_report,
    reject_pending_report as reject_competitor_tds_report,
    start_scheduler as start_competitor_tds_scheduler,
    stop_scheduler as stop_competitor_tds_scheduler,
)
import hashlib

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
BACKEND_HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))
OPENAI_MODEL = "gpt-4.1-mini"
_openai_client: Optional[OpenAI] = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if _openai_client is None:
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


async def _generate_openai_text(prompt: str, system_message: str) -> str:
    def _run() -> str:
        response = _get_openai_client().responses.create(
            model=OPENAI_MODEL,
            instructions=system_message,
            input=prompt,
        )
        return (response.output_text or "").strip()

    return await asyncio.to_thread(_run)


def _parse_cors_origins() -> List[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    return origins or [
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://192.168.29.11:8081",
    ]


CORS_ORIGINS = _parse_cors_origins()

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ----------------- Auth helpers -----------------
EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Get current user from session_token cookie or Authorization header."""
    token = None
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        token = cookie_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session_doc.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ----------------- Models -----------------
class SessionRequest(BaseModel):
    session_id: str


class CompareRequest(BaseModel):
    kamdhenu_code: str
    competitor_product_ids: List[str] = Field(default_factory=list)
    custom_products: List[Dict[str, Any]] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    substrate_id: str
    tile_type_id: str
    tile_size: str
    area: str


class CustomProduct(BaseModel):
    name: str
    brand: str
    is_type: Optional[str] = ""
    en_type: Optional[str] = ""


# ----------------- Auth Endpoints -----------------
def _get_google_oauth_config() -> Dict[str, str]:
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    google_callback_url = os.environ.get("GOOGLE_CALLBACK_URL", "").strip()
    frontend_app_url = os.environ.get("FRONTEND_APP_URL", "").strip().rstrip("/")

    if not google_client_id or not google_client_secret or not google_callback_url:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured")

    return {
        "client_id": google_client_id,
        "client_secret": google_client_secret,
        "callback_url": google_callback_url,
        "frontend_app_url": frontend_app_url,
    }


def _build_google_redirect_url(base_redirect: str, params: Dict[str, str]) -> str:
    separator = "&" if "?" in base_redirect else "?"
    return f"{base_redirect}{separator}{urlencode(params)}"


def _get_default_frontend_callback(frontend_app_url: str) -> str:
    if not frontend_app_url:
        return ""
    return f"{frontend_app_url}/oauth/callback"


def _strip_query_and_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _derive_google_login_redirect(frontend_redirect: str, frontend_app_url: str) -> str:
    stripped = _strip_query_and_fragment(frontend_redirect)
    if stripped.endswith("/oauth/callback"):
        return f"{stripped[:-len('/oauth/callback')]}/login"
    if stripped.endswith(":/oauth/callback"):
        return f"{stripped[:-len('/oauth/callback')]}/login"
    if frontend_app_url:
        return f"{frontend_app_url}/login"
    return stripped


def _get_google_error_message(error_code: str) -> str:
    mapping = {
        "access_denied": "Google sign-in was cancelled before it completed.",
        "missing_code": "Google sign-in did not return an authorization code.",
        "google_token_exchange_failed": "Google sign-in could not be completed. Please try again.",
        "google_access_token_missing": "Google sign-in did not return an access token.",
        "google_profile_lookup_failed": "Could not load your Google profile. Please try again.",
        "google_email_missing": "Your Google account did not return an email address.",
        "google_provider_unavailable": "Google sign-in is temporarily unavailable.",
        "google_oauth_failed": "Google sign-in failed. Please try again.",
    }
    return mapping.get(error_code, "Google sign-in failed. Please try again.")


async def _upsert_user_record(
    email: str,
    name: str,
    picture: str = "",
    google_sub: str = "",
) -> Dict[str, Any]:
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc),
        }
        if google_sub:
            user["google_sub"] = google_sub
        await db.users.insert_one(user.copy())
        return user

    updates = {"name": name, "picture": picture}
    if google_sub:
        updates["google_sub"] = google_sub
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    user.update(updates)
    return user


async def _create_user_session(user_id: str, expires_at: datetime) -> str:
    session_token = f"google_session_{uuid.uuid4().hex}"
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return session_token


async def _complete_google_auth_code(code: str, redirect_uri: str) -> Dict[str, Any]:
    config = _get_google_oauth_config()
    token_payload = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    try:
        token_response = http_requests.post(
            "https://oauth2.googleapis.com/token",
            data=token_payload,
            timeout=10,
        )
        if token_response.status_code != 200:
            logger.error("Google token exchange failed: %s", token_response.text)
            raise HTTPException(status_code=401, detail="google_token_exchange_failed")
        token_data = token_response.json()

        access_token = token_data.get("access_token")
        id_token = token_data.get("id_token")
        if not access_token:
            raise HTTPException(status_code=401, detail="google_access_token_missing")

        userinfo_response = http_requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if userinfo_response.status_code != 200:
            logger.error("Google userinfo failed: %s", userinfo_response.text)
            raise HTTPException(status_code=401, detail="google_profile_lookup_failed")
        google_user = userinfo_response.json()
    except http_requests.RequestException as e:
        logger.error("Google OAuth request failed: %s", e)
        raise HTTPException(status_code=502, detail="google_provider_unavailable")

    email = google_user.get("email")
    name = google_user.get("name") or email
    picture = google_user.get("picture", "")
    google_sub = google_user.get("sub", "")
    if not email:
        raise HTTPException(status_code=401, detail="google_email_missing")

    user = await _upsert_user_record(email=email, name=name, picture=picture, google_sub=google_sub)
    expires_in = int(token_data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    session_token = await _create_user_session(user["user_id"], expires_at)

    return {
        "session_token": session_token,
        "google_access_token": access_token,
        "google_id_token": id_token,
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": expires_at.isoformat(),
        "user": {
            "user_id": user["user_id"],
            "email": email,
            "name": name,
            "picture": picture,
        },
    }


@api_router.post("/auth/session")
async def auth_session(payload: SessionRequest):
    """Exchange session_id from Emergent OAuth for a session_token."""
    try:
        r = http_requests.get(
            EMERGENT_AUTH_URL,
            headers={"X-Session-ID": payload.session_id},
            timeout=10,
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Auth exchange failed")
        data = r.json()
    except http_requests.RequestException as e:
        logger.error(f"Emergent auth error: {e}")
        raise HTTPException(status_code=502, detail="Auth provider unavailable")

    email = data.get("email")
    name = data.get("name")
    picture = data.get("picture", "")
    session_token = data["session_token"]

    user = await _upsert_user_record(email=email, name=name, picture=picture)

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )

    return {
        "session_token": session_token,
        "user": {"user_id": user["user_id"], "email": email, "name": name, "picture": picture},
    }


@api_router.get("/auth/google")
async def auth_google(redirect: Optional[str] = Query(default=None)):
    config = _get_google_oauth_config()
    final_redirect = redirect or _get_default_frontend_callback(config["frontend_app_url"])
    if not final_redirect:
        raise HTTPException(status_code=400, detail="Missing redirect URL")

    state = urlencode({"redirect": final_redirect})
    query = urlencode({
        "client_id": config["client_id"],
        "redirect_uri": config["callback_url"],
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    })
    google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    return RedirectResponse(url=google_url, status_code=307)


@api_router.get("/auth/google/callback")
async def auth_google_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
):
    config = _get_google_oauth_config()
    frontend_redirect = _get_default_frontend_callback(config["frontend_app_url"])
    if state:
        try:
            parsed_state = parse_qs(state)
            frontend_redirect = parsed_state.get("redirect", [frontend_redirect])[0]
        except Exception:
            frontend_redirect = _get_default_frontend_callback(config["frontend_app_url"])

    if not frontend_redirect:
        raise HTTPException(status_code=400, detail="Missing frontend redirect URL")

    login_redirect = _derive_google_login_redirect(frontend_redirect, config["frontend_app_url"])

    if error:
        return RedirectResponse(
            url=_build_google_redirect_url(
                login_redirect,
                {"error": _get_google_error_message(error)},
            ),
            status_code=307,
        )

    if not code:
        return RedirectResponse(
            url=_build_google_redirect_url(
                login_redirect,
                {"error": _get_google_error_message("missing_code")},
            ),
            status_code=307,
        )

    try:
        session = await _complete_google_auth_code(code, config["callback_url"])
    except HTTPException as exc:
        logger.error("Google auth callback failed: %s", exc.detail)
        return RedirectResponse(
            url=_build_google_redirect_url(
                login_redirect,
                {"error": _get_google_error_message(str(exc.detail or "google_oauth_failed"))},
            ),
            status_code=307,
        )

    redirect_to = _build_google_redirect_url(frontend_redirect, {"token": session["session_token"]})
    response = RedirectResponse(url=redirect_to, status_code=307)
    response.set_cookie(
        "session_token",
        session["session_token"],
        httponly=True,
        samesite="lax",
        secure=config["callback_url"].startswith("https://"),
    )
    return response


@api_router.get("/auth/me")
async def auth_me(request: Request, authorization: Optional[str] = Header(default=None)):
    user = await get_current_user(request, authorization)
    return {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture", "")}


@api_router.post("/auth/logout")
async def auth_logout(request: Request, authorization: Optional[str] = Header(default=None)):
    token = None
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        token = cookie_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    return {"ok": True}

# ----------------- Catalog Endpoints -----------------
@api_router.get("/catalog/substrates")
async def list_substrates():
    return {"substrates": SUBSTRATES}


@api_router.get("/catalog/tile-types")
async def list_tile_types(substrate_id: Optional[str] = None):
    if substrate_id:
        allowed = SUBSTRATE_TILE_MAP.get(substrate_id, [])
        result = [t for t in TILE_TYPES if t["id"] in allowed]
        return {"tile_types": result}
    return {"tile_types": TILE_TYPES}


@api_router.get("/catalog/areas")
async def list_areas():
    return {"areas": AREAS}


@api_router.get("/catalog/kamdhenu")
async def list_kamdhenu():
    return {"products": KAMDHENU_PRODUCTS}


@api_router.get("/catalog/competitors")
async def list_competitors():
    docs = {
        (doc["competitor_id"], doc["product_name"]): doc
        for doc in await list_competitor_tds_docs(db)
    }
    enriched = []
    for c in COMPETITORS:
        prods = []
        for idx, p in enumerate(c["products"]):
            product = {
                "id": f"{c['id']}::{idx}",
                **p,
            }
            doc = docs.get((c["id"], p["name"]))
            if doc:
                product.update({
                    "tds_url": doc.get("tds_url", ""),
                    "tds_file_hash": doc.get("tds_file_hash", ""),
                    "tds_text_hash": doc.get("tds_text_hash", ""),
                    "last_checked_at": doc.get("last_checked_at"),
                    "last_updated_at": doc.get("last_updated_at"),
                    "next_check_at": doc.get("next_check_at"),
                    "update_frequency_days": doc.get("update_frequency_days", p.get("update_frequency_days", 15)),
                    "report_status": doc.get("report_status", p.get("report_status", "due")),
                    "technical_report": doc.get("technical_report"),
                    "pending_technical_report": doc.get("pending_technical_report"),
                    "tds_source_version": doc.get("tds_source_version", p.get("tds_source_version", "seed-v1")),
                })
            prods.append(product)
        enriched.append({"id": c["id"], "name": c["name"], "products": prods})
    return {"competitors": enriched}


# ----------------- Recommendation -----------------
@api_router.post("/recommend")
async def recommend(req: RecommendRequest):
    code = recommend_kamdhenu(req.substrate_id, req.tile_type_id, req.tile_size, req.area)
    product = next((p for p in KAMDHENU_PRODUCTS if p["code"] == code), None)
    if not product:
        raise HTTPException(status_code=404, detail="No recommendation")

    # Reasoning bullets
    reasons = []
    if req.substrate_id in ("plywood", "gypsum_boards", "mdf", "metallic", "glass", "rubber_pvc_lino"):
        reasons.append(f"Substrate '{req.substrate_id.replace('_', ' ')}' requires high-flexibility S1/S2 adhesive.")
    if req.area in ("Outdoor / Facade", "Elevation", "Swimming Pool", "Industrial Floor"):
        reasons.append(f"Application area '{req.area}' demands deformable, freeze-thaw resistant adhesive.")
    if req.tile_type_id in ("marble", "granite", "stone", "limestone", "travertine"):
        reasons.append(f"Natural stone ({req.tile_type_id}) needs non-staining, non-slip stone adhesive.")
    if req.tile_type_id in ("vitrified", "porcelain"):
        reasons.append(f"Low-porosity {req.tile_type_id} tiles require enhanced polymer-modified bond.")
    reasons.append(f"Recommended for tile size {req.tile_size}.")

    return {"recommendation": product, "reasons": reasons}


# ----------------- Comparison -----------------
@api_router.post("/compare")
async def compare(req: CompareRequest):
    kamdhenu = next((p for p in KAMDHENU_PRODUCTS if p["code"] == req.kamdhenu_code), None)
    if not kamdhenu:
        raise HTTPException(status_code=404, detail="Kamdhenu product not found")

    # Build columns: Kamdhenu first, then competitors
    columns = [{
        "brand": "Kamdhenu",
        "name": kamdhenu["name"],
        "code": kamdhenu["code"],
        "is_type": kamdhenu["is_type"],
        "en_type": kamdhenu["en_type"],
        "is_kamdhenu": True,
        "params": kamdhenu["params"],
        "tagline": kamdhenu["tagline"],
        "max_tile_size": kamdhenu["max_tile_size"],
    }]

    # Resolve competitor products by composite id
    for cid in req.competitor_product_ids:
        competitor = await resolve_tds_competitor(db, cid)
        if not competitor:
            continue
        columns.append({
            "brand": competitor["brand"],
            "name": competitor["name"],
            "code": "",
            "is_type": competitor.get("is_type", ""),
            "en_type": competitor.get("en_type", ""),
            "is_kamdhenu": False,
            "params": competitor["params"],
            "tagline": "",
            "max_tile_size": "",
            "report_status": competitor.get("report_status", "due"),
            "tds_url": competitor.get("tds_url", ""),
        })

    # Custom products
    for cp in req.custom_products:
        params = enrich_competitor_params(cp)
        columns.append({
            "brand": cp.get("brand", "Custom"),
            "name": cp.get("name", "Custom Product"),
            "code": "",
            "is_type": cp.get("is_type", ""),
            "en_type": cp.get("en_type", ""),
            "is_kamdhenu": False,
            "params": params,
            "tagline": "",
            "max_tile_size": "",
            "is_custom": True,
        })

    # Collect all parameter keys preserving Kamdhenu order
    keys = list(kamdhenu["params"].keys())
    for col in columns[1:]:
        for k in col["params"].keys():
            if k not in keys:
                keys.append(k)

    rows = []
    for k in keys:
        kam_val = columns[0]["params"].get(k, "—")
        comp_vals = [col["params"].get(k, "—") for col in columns[1:]]
        wins = _kamdhenu_wins(k, kam_val, comp_vals)
        # is_tds: True for Kamdhenu (sourced from TDS), False for competitors (typical IS/EN-class reference)
        is_tds_flags = [True] + [False] * (len(columns) - 1)
        rows.append({
            "param": k,
            "values": [col["params"].get(k, "—") for col in columns],
            "is_tds": is_tds_flags,
            "kamdhenu_advantage": wins,
        })

    # Pitch points - Why Kamdhenu wins
    pitches = []
    pitches.append(f"{kamdhenu['code']} is classified {kamdhenu['is_type']} ({kamdhenu['en_type']}) per Indian & EN standards.")
    pitches.append(kamdhenu["tagline"])
    pitches.append(f"Pot life of {kamdhenu['params'].get('Pot Life', 'N/A')} — extended workability vs typical competitors.")
    pitches.append(f"Initial bond strength {kamdhenu['params'].get('Initial Tensile Adhesion (IS)', 'N/A')} meets/exceeds IS 15477:2019.")
    pitches.append(f"Coverage of {kamdhenu['params'].get('Coverage', 'N/A')} — better material economy on site.")
    pitches.append("Made in India, with pan-India supply chain and dedicated technical support for sales pitches.")

    return {
        "columns": columns,
        "rows": rows,
        "kamdhenu_pitches": pitches,
    }


# ----------------- Admin: Add Custom Product -----------------
@api_router.post("/admin/products")
async def add_custom_product(
    payload: CustomProduct,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    user = await get_current_user(request, authorization)
    doc = {
        "product_id": f"custom_{uuid.uuid4().hex[:8]}",
        "name": payload.name,
        "brand": payload.brand,
        "is_type": payload.is_type or "",
        "en_type": payload.en_type or "",
        "added_by": user["user_id"],
        "created_at": datetime.now(timezone.utc),
    }
    await db.custom_products.insert_one(doc.copy())
    return {"ok": True, "product_id": doc["product_id"]}


@api_router.get("/admin/products")
async def list_custom_products():
    docs = await db.custom_products.find({}, {"_id": 0}).to_list(500)
    return {"products": docs}


class PitchRequest(BaseModel):
    kamdhenu_code: str
    competitor_product_ids: List[str] = Field(default_factory=list)
    custom_products: List[Dict[str, Any]] = Field(default_factory=list)
    variant: int = 0  # 0 = default angle, 1+ = alternative angles


# Direction of advantage for each comparable parameter
# higher = bigger number is better, lower = smaller number is better
PARAM_DIRECTIONS = {
    "Open Time": "higher",
    "Pot Life": "higher",
    "Adjustability Time": "higher",
    "Initial Tensile Adhesion (IS)": "higher",
    "Tensile Adhesion after Water Immersion": "higher",
    "Tensile Adhesion after Heat Aging": "higher",
    "Tensile Adhesion after Freeze-Thaw": "higher",
    "Slip Resistance": "lower",
    "Shear Adhesion (Dry)": "higher",
    "Shear Adhesion (Wet)": "higher",
    "Shear Adhesion (Heat Ageing)": "higher",
    "Coverage": "higher",
    "Transverse Deformation (S1)": "higher",
    "Deformability (S2)": "higher",
    "VOC Content": "lower",
    "Tensile Adhesion Strength after 28 days": "higher",
    "Tensile Adhesion (Dry)": "higher",
    "Tensile Adhesion (Wet)": "higher",
}


def _extract_max_number(s: str):
    """Extract the highest representative number from a parameter string.
    Handles ranges like '1.25-1.35', prefixes '≥', '≤', '~', units, etc.
    Returns float or None."""
    import re
    if not s or not isinstance(s, str):
        return None
    nums = re.findall(r"\d+\.?\d*", s)
    if not nums:
        return None
    try:
        return max(float(n) for n in nums)
    except ValueError:
        return None


def _extract_min_number(s: str):
    import re
    if not s or not isinstance(s, str):
        return None
    nums = re.findall(r"\d+\.?\d*", s)
    if not nums:
        return None
    try:
        return min(float(n) for n in nums)
    except ValueError:
        return None


def _kamdhenu_wins(param: str, kam_val: str, comp_vals: List[str]) -> bool:
    """Returns True if Kamdhenu strictly beats ALL competitor values on this param."""
    direction = PARAM_DIRECTIONS.get(param)
    if not direction:
        return False
    if not kam_val or kam_val == "—":
        return False
    if direction == "higher":
        kam_num = _extract_max_number(kam_val)
        if kam_num is None:
            return False
        for cv in comp_vals:
            cn = _extract_max_number(cv)
            if cn is None:
                continue
            if cn >= kam_num:
                return False
        return True
    else:  # lower better
        kam_num = _extract_min_number(kam_val)
        if kam_num is None:
            return False
        for cv in comp_vals:
            cn = _extract_min_number(cv)
            if cn is None:
                continue
            if cn <= kam_num:
                return False
        return True


async def _resolve_competitor(cid: str):
    return await resolve_tds_competitor(db, cid)


@api_router.post("/pitch")
async def generate_pitch(req: PitchRequest):
    """Generates AI-powered per-competitor sales pitch (2-3 punchy one-liners).
    Cached by hash of (kamdhenu_code, competitor_id)."""
    kam = next((p for p in KAMDHENU_PRODUCTS if p["code"] == req.kamdhenu_code), None)
    if not kam:
        raise HTTPException(status_code=404, detail="Kamdhenu product not found")

    _get_openai_client()

    pitches: List[Dict[str, Any]] = []

    # Resolve all competitors (catalog + custom)
    competitors: List[Dict[str, Any]] = []
    for cid in req.competitor_product_ids:
        c = await _resolve_competitor(cid)
        if c:
            competitors.append(c)
    for idx, cp in enumerate(req.custom_products):
        competitors.append({
            "id": f"custom::{idx}::{cp.get('name', '')}",
            "brand": cp.get("brand", "Custom"),
            "name": cp.get("name", "Custom Product"),
            "is_type": cp.get("is_type", ""),
            "en_type": cp.get("en_type", ""),
            "params": enrich_competitor_params(cp),
        })

    for comp in competitors:
        cache_key = hashlib.md5(
            f"{kam['code']}|{comp['brand']}|{comp['name']}|{comp['is_type']}|{comp['en_type']}|v3|var{req.variant}".encode()
        ).hexdigest()

        cached = await db.pitch_cache.find_one({"cache_key": cache_key}, {"_id": 0})
        if cached:
            pitches.append({
                "competitor_id": comp["id"],
                "competitor_brand": comp["brand"],
                "competitor_name": comp["name"],
                "lines": cached["lines"],
            })
            continue

        # Build prompt
        kam_params_str = "\n".join([f"  - {k}: {v}" for k, v in kam["params"].items()])
        comp_params_str = "\n".join([f"  - {k}: {v}" for k, v in comp["params"].items()])
        # Variant-specific guidance
        variant_hints = [
            "",  # 0 = default
            "ANGLE FOR THIS REQUEST: Focus on durability and longevity — freeze-thaw, heat aging, water immersion strength, and shelf life. Avoid repeating common open-time / coverage talking points.",
            "ANGLE FOR THIS REQUEST: Focus on safety, environment, and worksite economics — VOC content, application temperature window, mixing ratio efficiency, coverage, and per-bag yield.",
            "ANGLE FOR THIS REQUEST: Focus on premium / large-format / facade applications — slip resistance, deformability/transverse deformation, shear adhesion under wet & heat conditions, and adjustability time.",
            "ANGLE FOR THIS REQUEST: Focus on the standards classification gap (IS 15477 / EN 12004) and what that means in real-world performance — superior bond, specifier-grade product, lower callback rate.",
        ]
        variant_hint = variant_hints[req.variant % len(variant_hints)]

        prompt = f"""You are a senior B2B sales coach for Kamdhenu Adhesives (India). A sales rep is pitching a tile contractor / architect / designer who is currently using a competitor product.

Generate EXACTLY 3 punchy one-liner sales pitches (max 28 words each) for the rep to use. Each line MUST:
- Frame around a REAL-WORLD problem tile contractors face with weak adhesives — examples: tiles debonding in wet areas (bathrooms, pools, kitchens), vertical slip on facades during install, hollow-sound failures in tile-on-tile, pop-outs from freeze-thaw, large-format slabs sliding on walls, cracks from substrate movement, weak grab on low-porosity vitrified/porcelain, costly callbacks from short open time, VOC complaints on indoor jobs.
- Pick ONE such problem per line, then name a SPECIFIC parameter & exact number from the data showing how Kamdhenu's spec PREVENTS it vs the competitor's weaker spec.
- Use confident, direct, sales-floor language. No hedging, no clichés ("end of the day", "trust me"), no emojis, no markdown, no bullet symbols.
- Use percentages or multipliers wherever possible to quantify the advantage.

{variant_hint}

Output EXACTLY 3 lines, separated by newlines. No preamble, no numbering, no extra text.

KAMDHENU PRODUCT: {kam['code']} — {kam['name']}
Type: {kam['is_type']} / {kam['en_type']}
Tagline: {kam['tagline']}
Technical Specs:
{kam_params_str}

COMPETITOR PRODUCT: {comp['brand']} — {comp['name']}
Type: {comp['is_type']} / {comp['en_type']}
Technical Specs:
{comp_params_str}
"""

        try:
            text = await _generate_openai_text(
                prompt,
                "You are a precise, persuasive B2B sales coach. Output exactly what is asked, nothing more.",
            )
            lines = [ln.strip(" -•*\t") for ln in text.split("\n") if ln.strip()]
            # Take first 3 lines
            lines = lines[:3] if len(lines) >= 3 else lines
            if not lines:
                raise ValueError("Empty AI response")

            await db.pitch_cache.update_one(
                {"cache_key": cache_key},
                {"$set": {
                    "cache_key": cache_key,
                    "kamdhenu_code": kam["code"],
                    "competitor_brand": comp["brand"],
                    "competitor_name": comp["name"],
                    "lines": lines,
                    "created_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            pitches.append({
                "competitor_id": comp["id"],
                "competitor_brand": comp["brand"],
                "competitor_name": comp["name"],
                "lines": lines,
            })
        except Exception as e:
            logger.error(f"Pitch gen failed for {comp['name']}: {e}")
            # Deterministic fallback
            fb = []
            try:
                fb.append(f"{kam['code']} ({kam['en_type']}) outperforms {comp['brand']}'s {comp['name']} ({comp['en_type']}) on the standards classification itself.")
                fb.append(f"Kamdhenu open time {kam['params'].get('Open Time', 'N/A')} vs typical {comp['params'].get('Open Time', 'N/A')} — more workable on site.")
                fb.append(f"Kamdhenu coverage {kam['params'].get('Coverage', 'N/A')} delivers better material economy than {comp['brand']}.")
            except Exception:
                fb = [f"Kamdhenu {kam['code']} delivers superior performance vs {comp['name']}."]
            # Cache fallback briefly so repeats don't re-hit the LLM in a budget-exceeded loop
            await db.pitch_cache.update_one(
                {"cache_key": cache_key},
                {"$set": {
                    "cache_key": cache_key,
                    "kamdhenu_code": kam["code"],
                    "competitor_brand": comp["brand"],
                    "competitor_name": comp["name"],
                    "lines": fb,
                    "is_fallback": True,
                    "created_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            pitches.append({
                "competitor_id": comp["id"],
                "competitor_brand": comp["brand"],
                "competitor_name": comp["name"],
                "lines": fb,
            })

    return {"pitches": pitches}


class RecommendationTextRequest(BaseModel):
    kamdhenu_code: str
    competitor_product_ids: List[str] = Field(default_factory=list)
    custom_products: List[Dict[str, Any]] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None  # optional substrate/tile/size/area


@api_router.post("/recommendation-text")
async def generate_recommendation_text(req: RecommendationTextRequest):
    """Generates a professional 2-3 paragraph technical recommendation suitable for client sharing."""
    kam = next((p for p in KAMDHENU_PRODUCTS if p["code"] == req.kamdhenu_code), None)
    if not kam:
        raise HTTPException(status_code=404, detail="Kamdhenu product not found")

    _get_openai_client()

    competitors: List[Dict[str, Any]] = []
    for cid in req.competitor_product_ids:
        c = await _resolve_competitor(cid)
        if c:
            competitors.append(c)
    for idx, cp in enumerate(req.custom_products):
        competitors.append({
            "brand": cp.get("brand", "Custom"),
            "name": cp.get("name", "Custom Product"),
            "is_type": cp.get("is_type", ""),
            "en_type": cp.get("en_type", ""),
        })

    cache_payload = f"{kam['code']}|" + "|".join(sorted([f"{c['brand']}::{c['name']}" for c in competitors])) + f"|ctx{req.context}"
    cache_key = hashlib.md5(cache_payload.encode()).hexdigest()
    cached = await db.recommendation_cache.find_one({"cache_key": cache_key}, {"_id": 0})
    if cached:
        return {"text": cached["text"], "cached": True}

    comp_lines = "\n".join([f"  - {c['brand']} {c['name']} ({c.get('is_type','')} / {c.get('en_type','')})" for c in competitors]) or "  - (none)"
    ctx_str = ""
    if req.context:
        ctx_str = f"\nApplication context: substrate={req.context.get('substrate','-')}, tile={req.context.get('tile_type','-')}, size={req.context.get('size','-')}, area={req.context.get('area','-')}."

    prompt = f"""Write a professional 3-paragraph TECHNICAL RECOMMENDATION letter that a Kamdhenu Adhesives sales representative will share with a tile contractor / architect / interior designer.

Audience: a B2B customer who is currently considering competitor products. The tone must be confident, factual, and consultative — NOT salesy. No exclamation marks. No hyperbole. Suitable to attach to an email.

REQUIREMENTS:
- Paragraph 1: One-line summary of the recommendation (Kamdhenu {kam['code']}), the IS 15477 / EN 12004 classification, and why this class is the right fit for the application.
- Paragraph 2: Quantitative justification — cite 3-4 specific spec advantages of Kamdhenu over the competitor product(s) using exact numbers. Tie each advantage to a real installation outcome (longer life on facades, lower callback risk in wet zones, better hold on large-format vitrified, etc.).
- Paragraph 3: Closing assurance — IS standards compliance, technical support availability, and invitation to schedule a site visit / demo. End with a professional sign-off "— Kamdhenu Adhesives Technical Team".

Constraints:
- 200-280 words total.
- Plain text. No markdown, no bullets, no emojis.
- Do not invent numbers; use only the spec values provided.

KAMDHENU PRODUCT: {kam['code']} — {kam['name']}
Type: {kam['is_type']} / {kam['en_type']}
Tagline: {kam['tagline']}
Description: {kam.get('description','')}
Key Specs:
  - Open Time: {kam['params'].get('Open Time','-')}
  - Pot Life: {kam['params'].get('Pot Life','-')}
  - Initial Tensile Adhesion: {kam['params'].get('Initial Tensile Adhesion (IS)','-')}
  - Tensile after Water: {kam['params'].get('Tensile Adhesion after Water Immersion','-')}
  - Tensile after Heat: {kam['params'].get('Tensile Adhesion after Heat Aging','-')}
  - Tensile after Freeze-Thaw: {kam['params'].get('Tensile Adhesion after Freeze-Thaw','-')}
  - Slip Resistance: {kam['params'].get('Slip Resistance','-')}
  - Coverage: {kam['params'].get('Coverage','-')}
  - VOC: {kam['params'].get('VOC Content','-')}

COMPETITOR PRODUCTS BEING COMPARED:
{comp_lines}
{ctx_str}
"""
    try:
        text = await _generate_openai_text(
            prompt,
            "You are a senior technical writer for Kamdhenu Adhesives. Write professional, factual, B2B-grade technical recommendations.",
        )
        if not text:
            raise ValueError("Empty response")
        await db.recommendation_cache.update_one(
            {"cache_key": cache_key},
            {"$set": {"cache_key": cache_key, "text": text, "created_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return {"text": text, "cached": False}
    except Exception as e:
        logger.error(f"Recommendation gen failed: {e}")
        # Deterministic fallback
        comp_names = ", ".join([f"{c['brand']} {c['name']}" for c in competitors]) or "the alternatives evaluated"
        text = (
            f"Following our technical evaluation of the application requirement, we recommend "
            f"Kamdhenu {kam['code']} — {kam['name']}, classified as {kam['is_type']} per IS 15477:2019 and "
            f"{kam['en_type']} per EN 12004. This classification is purpose-built for the demands of your project.\n\n"
            f"Compared with {comp_names}, Kamdhenu {kam['code']} offers a measurable performance margin: "
            f"open time of {kam['params'].get('Open Time','-')}, pot life of {kam['params'].get('Pot Life','-')}, "
            f"and tensile bond strength after water immersion of {kam['params'].get('Tensile Adhesion after Water Immersion','-')}. "
            f"Slip resistance is rated {kam['params'].get('Slip Resistance','-')}, ensuring secure fixing of "
            f"large-format and heavy tiles on vertical surfaces. These parameters translate directly into longer "
            f"installation life, reduced callback risk in wet and exterior zones, and consistent on-site execution.\n\n"
            f"Kamdhenu {kam['code']} is fully compliant with Indian and international adhesive standards, backed "
            f"by pan-India technical support and a dedicated field application team. We would be happy to arrange a site "
            f"visit or a hands-on demonstration at your convenience.\n\n— Kamdhenu Adhesives Technical Team"
        )
        return {"text": text, "cached": False, "fallback": True}


@api_router.get("/competitor-tds/due")
async def list_due_competitor_tds():
    docs = await list_due_competitor_tds_docs(db)
    return {"products": docs, "count": len(docs), "checked_at": datetime.now(timezone.utc)}


@api_router.get("/competitor-tds/changed")
async def list_changed_competitor_tds():
    docs = await list_changed_competitor_tds_docs(db)
    return {"products": docs, "count": len(docs)}


@api_router.get("/competitor-tds/{competitor_id}/{product_name}")
async def get_competitor_tds(competitor_id: str, product_name: str):
    try:
        return await get_competitor_tds_doc_or_raise(db, competitor_id, product_name)
    except LookupError:
        raise HTTPException(status_code=404, detail="Competitor product not found")


@api_router.post("/competitor-tds/{competitor_id}/{product_name}/sync")
async def sync_competitor_tds(competitor_id: str, product_name: str):
    try:
        return await sync_competitor_tds_doc(db, competitor_id, product_name)
    except LookupError:
        raise HTTPException(status_code=404, detail="Competitor product not found")


@api_router.patch("/competitor-tds/{competitor_id}/{product_name}/approve")
async def approve_competitor_tds(
    competitor_id: str,
    product_name: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    user = await get_current_user(request, authorization)
    try:
        product = await approve_competitor_tds_report(db, competitor_id, product_name, user["user_id"])
    except LookupError:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "product": product}


@api_router.patch("/competitor-tds/{competitor_id}/{product_name}/reject")
async def reject_competitor_tds(
    competitor_id: str,
    product_name: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    user = await get_current_user(request, authorization)
    try:
        product = await reject_competitor_tds_report(db, competitor_id, product_name, user["user_id"])
    except LookupError:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "product": product}


@api_router.get("/")
async def root():
    return {"app": "Kamdhenu Adhesive Comparator", "version": "1.0"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def seed_dev_user():
    """Seed a dev test user/session for testing agent."""
    dev_user = {
        "user_id": "dev_user_kamdhenu",
        "email": "dev.sales@kamdhenu.test",
        "name": "Dev Sales User",
        "picture": "",
        "created_at": datetime.now(timezone.utc),
    }
    await db.users.update_one(
        {"user_id": "dev_user_kamdhenu"},
        {"$set": dev_user},
        upsert=True,
    )
    await db.user_sessions.update_one(
        {"session_token": "dev_session_kamdhenu_2026"},
        {"$set": {
            "user_id": "dev_user_kamdhenu",
            "session_token": "dev_session_kamdhenu_2026",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=365),
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    await ensure_competitor_tds_seeded(db)
    start_competitor_tds_scheduler(db, logger)
    logger.info("Dev session seeded.")


@app.on_event("shutdown")
async def shutdown_db_client():
    await stop_competitor_tds_scheduler()
    client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=True)


from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError
from starlette.middleware.cors import CORSMiddleware

from competitor_tds import (
    COMPETITOR_TDS_COLLECTION,
    approve_pending_report as approve_competitor_tds_report,
    ensure_seeded as ensure_competitor_tds_seeded,
    get_doc_or_raise as get_competitor_tds_doc_or_raise,
    list_changed_docs as list_changed_competitor_tds_docs,
    list_docs as list_competitor_tds_docs,
    list_due_docs as list_due_competitor_tds_docs,
    reject_pending_report as reject_competitor_tds_report,
    resolve_competitor as resolve_tds_competitor,
    start_scheduler as start_competitor_tds_scheduler,
    stop_scheduler as stop_competitor_tds_scheduler,
    sync_doc as sync_competitor_tds_doc,
)
from seed_data import (
    AREAS,
    COMPETITORS,
    KAMDHENU_PRODUCTS,
    SUBSTRATES,
    SUBSTRATE_TILE_MAP,
    TILE_TYPES,
    enrich_competitor_params,
    recommend_kamdhenu,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

APP_NAME = "Kamdhenu Adhesive Comparator"
APP_VERSION = "1.0"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_SESSION_TTL_DAYS = 7
DEFAULT_ADMIN_SESSION_TTL_HOURS = 12
DEFAULT_PASSWORD_HASH_ITERATIONS = 310000
DEFAULT_MONGO_TIMEOUT_MS = 10000
DEFAULT_RM_SEED_PASSWORD = "ChangeMe123!"
DEFAULT_ADMIN_SEED_PASSWORD = "AdminChangeMe123!"
DEFAULT_CORS_ORIGINS = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
]
VALID_SUBSTRATE_IDS = {item["id"] for item in SUBSTRATES}
VALID_TILE_TYPE_IDS = {item["id"] for item in TILE_TYPES}
VALID_AREAS = set(AREAS)
KAMDHENU_PRODUCTS_BY_CODE = {product["code"]: product for product in KAMDHENU_PRODUCTS}
logger = logging.getLogger("kamdhenu.backend")
_openai_client: Optional[OpenAI] = None
_openai_api_key: Optional[str] = None
SESSION_TOKEN_INDEX_NAME = "session_token_hash_1"
SESSION_TTL_INDEX_NAME = "expires_at_1"
USER_LOGIN_ID_INDEX_NAME = "login_id_normalized_1"
USER_ID_INDEX_NAME = "user_id_1"
PRODUCT_CODE_INDEX_NAME = "code_normalized_active_unique"
PRODUCT_NAME_INDEX_NAME = "name_normalized_active_1"
PRODUCT_STATUS_INDEX_NAME = "is_active_1_is_deleted_1"
USER_STATUS_INDEX_NAME = "role_1_is_active_1"
PRODUCT_PARAM_KEYS = sorted({key for product in KAMDHENU_PRODUCTS for key in product["params"].keys()})


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mongo_url: str = Field(min_length=1)
    db_name: str = Field(min_length=1)
    backend_host: str = "0.0.0.0"
    backend_port: int = Field(default=8000, ge=1, le=65535)
    backend_reload: bool = False
    cors_origins: List[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))
    openai_api_key: str = ""
    openai_model: str = DEFAULT_OPENAI_MODEL
    session_ttl_days: int = Field(default=DEFAULT_SESSION_TTL_DAYS, ge=1, le=90)
    admin_session_ttl_hours: int = Field(default=DEFAULT_ADMIN_SESSION_TTL_HOURS, ge=1, le=168)
    password_hash_iterations: int = Field(default=DEFAULT_PASSWORD_HASH_ITERATIONS, ge=100000, le=1000000)
    rm_default_user_id: str = "rm_demo"
    rm_default_password: str = DEFAULT_RM_SEED_PASSWORD
    rm_default_name: str = "Demo RM"
    rm_default_email: str = "rm.demo@kamdhenu.test"
    rm_seed_users_json: str = ""
    rm_force_seed_password_reset: bool = False
    admin_default_user_id: str = "admin"
    admin_default_password: str = DEFAULT_ADMIN_SEED_PASSWORD
    admin_default_name: str = "Admin User"
    admin_default_email: str = "admin@kamdhenu.test"
    admin_seed_users_json: str = ""
    mongo_server_selection_timeout_ms: int = Field(default=DEFAULT_MONGO_TIMEOUT_MS, ge=1000, le=60000)
    mongo_connect_timeout_ms: int = Field(default=DEFAULT_MONGO_TIMEOUT_MS, ge=1000, le=60000)
    log_level: str = "INFO"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=512)


class AdminUserBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(default="", max_length=320)
    role: str = Field(default="RM", min_length=2, max_length=16)
    is_active: bool = True

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"RM", "ADMIN"}:
            raise ValueError("Role must be RM or ADMIN")
        return normalized


class AdminUserCreateRequest(AdminUserBase):
    password: Optional[str] = Field(default=None, min_length=8, max_length=512)


class AdminUserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    role: Optional[str] = Field(default=None, min_length=2, max_length=16)
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        if normalized not in {"RM", "ADMIN"}:
            raise ValueError("Role must be RM or ADMIN")
        return normalized


class AdminUserPasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    password: Optional[str] = Field(default=None, min_length=8, max_length=512)


class AdminProductBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    is_type: str = Field(default="", max_length=100)
    en_type: str = Field(default="", max_length=100)
    tagline: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=2000)
    max_tile_size: str = Field(default="", max_length=200)
    areas: List[str] = Field(default_factory=list, max_length=20)
    params: Dict[str, str] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("areas")
    @classmethod
    def validate_areas(cls, values: List[str]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for value in values:
            candidate = value.strip()
            if candidate not in VALID_AREAS:
                raise ValueError(f"Invalid area: {candidate}")
            if candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped

    @field_validator("params")
    @classmethod
    def validate_params(cls, values: Dict[str, str]) -> Dict[str, str]:
        normalized: Dict[str, str] = {}
        for key, value in values.items():
            normalized_key = str(key).strip()
            normalized_value = str(value).strip()
            if not normalized_key or not normalized_value:
                raise ValueError("Product params must have non-empty keys and values")
            if normalized_key not in PRODUCT_PARAM_KEYS:
                raise ValueError(f"Unsupported product param: {normalized_key}")
            normalized[normalized_key] = normalized_value
        if not normalized:
            raise ValueError("Product params are required")
        return normalized


class AdminProductCreateRequest(AdminProductBase):
    pass


class AdminProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: Optional[str] = Field(default=None, min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    is_type: Optional[str] = Field(default=None, max_length=100)
    en_type: Optional[str] = Field(default=None, max_length=100)
    tagline: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=2000)
    max_tile_size: Optional[str] = Field(default=None, max_length=200)
    areas: Optional[List[str]] = Field(default=None, max_length=20)
    params: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None

    @field_validator("areas")
    @classmethod
    def validate_areas(cls, values: Optional[List[str]]) -> Optional[List[str]]:
        if values is None:
            return values
        deduped: List[str] = []
        seen = set()
        for value in values:
            candidate = value.strip()
            if candidate not in VALID_AREAS:
                raise ValueError(f"Invalid area: {candidate}")
            if candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped

    @field_validator("params")
    @classmethod
    def validate_params(cls, values: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if values is None:
            return values
        normalized: Dict[str, str] = {}
        for key, value in values.items():
            normalized_key = str(key).strip()
            normalized_value = str(value).strip()
            if not normalized_key or not normalized_value:
                raise ValueError("Product params must have non-empty keys and values")
            if normalized_key not in PRODUCT_PARAM_KEYS:
                raise ValueError(f"Unsupported product param: {normalized_key}")
            normalized[normalized_key] = normalized_value
        if not normalized:
            raise ValueError("Product params are required")
        return normalized


class AdminCompetitorProductBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    is_type: str = Field(default="", max_length=100)
    en_type: str = Field(default="", max_length=100)
    competes_with: str = Field(default="", max_length=32)
    is_active: bool = True

class AdminCompetitorProductCreateRequest(AdminCompetitorProductBase):
    pass

class AdminCompetitorProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    is_type: Optional[str] = Field(default=None, max_length=100)
    en_type: Optional[str] = Field(default=None, max_length=100)
    competes_with: Optional[str] = Field(default=None, max_length=32)
    is_active: Optional[bool] = None

class AdminCompetitorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True

class AdminCompetitorUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    is_active: Optional[bool] = None

class CustomProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    brand: str = Field(min_length=1, max_length=200)
    is_type: Optional[str] = Field(default="", max_length=100)
    en_type: Optional[str] = Field(default="", max_length=100)


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kamdhenu_code: str = Field(min_length=1, max_length=32)
    competitor_product_ids: List[str] = Field(default_factory=list, max_length=20)
    custom_products: List[CustomProductInput] = Field(default_factory=list, max_length=10)

    @field_validator("competitor_product_ids")
    @classmethod
    def dedupe_competitor_product_ids(cls, values: List[str]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for value in values:
            candidate = value.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    substrate_id: str = Field(min_length=1, max_length=64)
    tile_type_id: str = Field(min_length=1, max_length=64)
    tile_size: str = Field(min_length=1, max_length=64)
    area: str = Field(min_length=1, max_length=128)

    @field_validator("substrate_id")
    @classmethod
    def validate_substrate_id(cls, value: str) -> str:
        if value not in VALID_SUBSTRATE_IDS:
            raise ValueError("Invalid substrate_id")
        return value

    @field_validator("tile_type_id")
    @classmethod
    def validate_tile_type_id(cls, value: str) -> str:
        if value not in VALID_TILE_TYPE_IDS:
            raise ValueError("Invalid tile_type_id")
        return value

    @field_validator("area")
    @classmethod
    def validate_area(cls, value: str) -> str:
        if value not in VALID_AREAS:
            raise ValueError("Invalid area")
        return value


class PitchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kamdhenu_code: str = Field(min_length=1, max_length=32)
    competitor_product_ids: List[str] = Field(default_factory=list, max_length=20)
    custom_products: List[CustomProductInput] = Field(default_factory=list, max_length=10)
    variant: int = Field(default=0, ge=0, le=20)


class RecommendationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    substrate: Optional[str] = Field(default=None, max_length=128)
    tile_type: Optional[str] = Field(default=None, max_length=128)
    size: Optional[str] = Field(default=None, max_length=128)
    area: Optional[str] = Field(default=None, max_length=128)


class RecommendationTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kamdhenu_code: str = Field(min_length=1, max_length=32)
    competitor_product_ids: List[str] = Field(default_factory=list, max_length=20)
    custom_products: List[CustomProductInput] = Field(default_factory=list, max_length=10)
    context: Optional[RecommendationContext] = None


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

def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.setLevel(level)


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_cors_origins(raw: str) -> List[str]:
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def load_settings() -> AppSettings:
    data = {
        "mongo_url": os.environ.get("MONGO_URL", "").strip(),
        "db_name": os.environ.get("DB_NAME", "").strip(),
        "backend_host": os.environ.get("BACKEND_HOST", "0.0.0.0").strip() or "0.0.0.0",
        "backend_port": int(os.environ.get("BACKEND_PORT", "8000")),
        "backend_reload": _parse_bool(os.environ.get("BACKEND_RELOAD"), False),
        "cors_origins": _parse_cors_origins(os.environ.get("CORS_ORIGINS", "")),
        "openai_api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
        "openai_model": os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL,
        "session_ttl_days": int(os.environ.get("SESSION_TTL_DAYS", str(DEFAULT_SESSION_TTL_DAYS))),
        "admin_session_ttl_hours": int(os.environ.get("ADMIN_SESSION_TTL_HOURS", str(DEFAULT_ADMIN_SESSION_TTL_HOURS))),
        "password_hash_iterations": int(os.environ.get("RM_PASSWORD_HASH_ITERATIONS", str(DEFAULT_PASSWORD_HASH_ITERATIONS))),
        "rm_default_user_id": os.environ.get("RM_DEFAULT_USER_ID", "rm_demo").strip() or "rm_demo",
        "rm_default_password": os.environ.get("RM_DEFAULT_PASSWORD", DEFAULT_RM_SEED_PASSWORD).strip() or DEFAULT_RM_SEED_PASSWORD,
        "rm_default_name": os.environ.get("RM_DEFAULT_NAME", "Demo RM").strip() or "Demo RM",
        "rm_default_email": os.environ.get("RM_DEFAULT_EMAIL", "rm.demo@kamdhenu.test").strip() or "rm.demo@kamdhenu.test",
        "rm_seed_users_json": os.environ.get("RM_SEED_USERS_JSON", "").strip(),
        "rm_force_seed_password_reset": _parse_bool(os.environ.get("RM_FORCE_SEED_PASSWORD_RESET"), False),
        "admin_default_user_id": os.environ.get("ADMIN_DEFAULT_USER_ID", "admin").strip() or "admin",
        "admin_default_password": os.environ.get("ADMIN_DEFAULT_PASSWORD", DEFAULT_ADMIN_SEED_PASSWORD).strip() or DEFAULT_ADMIN_SEED_PASSWORD,
        "admin_default_name": os.environ.get("ADMIN_DEFAULT_NAME", "Admin User").strip() or "Admin User",
        "admin_default_email": os.environ.get("ADMIN_DEFAULT_EMAIL", "admin@kamdhenu.test").strip() or "admin@kamdhenu.test",
        "admin_seed_users_json": os.environ.get("ADMIN_SEED_USERS_JSON", "").strip(),
        "mongo_server_selection_timeout_ms": int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", str(DEFAULT_MONGO_TIMEOUT_MS))),
        "mongo_connect_timeout_ms": int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", str(DEFAULT_MONGO_TIMEOUT_MS))),
        "log_level": os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO",
    }
    return AppSettings.model_validate(data)


async def _generate_openai_text(settings: AppSettings, prompt: str, system_message: str) -> str:
    def _run() -> str:
        client = _get_openai_client(settings)
        response = client.responses.create(
            model=settings.openai_model,
            instructions=system_message,
            input=prompt,
        )
        return (response.output_text or "").strip()

    return await asyncio.to_thread(_run)


def _get_openai_client(settings: AppSettings) -> OpenAI:
    global _openai_client, _openai_api_key
    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    if _openai_client is None or _openai_api_key != api_key:
        _openai_client = OpenAI(api_key=api_key)
        _openai_api_key = api_key
    return _openai_client


async def get_db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return db


def get_settings_from_request(request: Request) -> AppSettings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise HTTPException(status_code=503, detail="Application settings not initialized")
    return settings


def _normalize_login_id(user_id: str) -> str:
    return user_id.strip().lower()


def _normalize_role_label(role: Any) -> str:
    return str(role or "").strip().upper()


def _role_for_storage(role: str) -> str:
    normalized = _normalize_role_label(role)
    if normalized == "RM":
        return "rm"
    if normalized == "ADMIN":
        return "ADMIN"
    raise ValueError("Unsupported role")


def _is_rm_role(role: Any) -> bool:
    return _normalize_role_label(role) == "RM"


def _is_admin_role(role: Any) -> bool:
    return _normalize_role_label(role) == "ADMIN"


def _normalize_product_code(code: str) -> str:
    return code.strip().upper()


def _normalize_product_name(name: str) -> str:
    return name.strip().lower()


def _generate_temporary_password(length: int = 16) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%*+-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _hash_password(password: str, salt_hex: str, iterations: int) -> str:
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    )
    return derived_key.hex()


def _create_password_record(password: str, iterations: int) -> Dict[str, Any]:
    salt_hex = secrets.token_hex(16)
    return {
        "password_salt": salt_hex,
        "password_hash": _hash_password(password, salt_hex, iterations),
        "password_hash_algorithm": "pbkdf2_sha256",
        "password_hash_iterations": iterations,
        "password_updated_at": datetime.now(timezone.utc),
    }


def _verify_password(password: str, user: Dict[str, Any], settings: AppSettings) -> bool:
    salt_hex = str(user.get("password_salt", ""))
    expected_hash = str(user.get("password_hash", ""))
    iterations = int(user.get("password_hash_iterations") or settings.password_hash_iterations)
    if not salt_hex or not expected_hash:
        return False
    calculated_hash = _hash_password(password, salt_hex, iterations)
    return hmac.compare_digest(calculated_hash, expected_hash)


def _hash_session_token(token: str) -> str:
    token_value = token.strip()
    if not token_value:
        raise ValueError("Session token must be non-empty")
    return hashlib.sha256(token_value.encode("utf-8")).hexdigest()


def _is_valid_session_token_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _session_token_partial_filter() -> Dict[str, Any]:
    return {"session_token_hash": {"$type": "string", "$gt": ""}}


def _extract_session_token(request: Request, authorization: Optional[str]) -> Optional[str]:
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        return cookie_token.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    role = "ADMIN" if _is_admin_role(user.get("role")) else "rm"
    return {
        "user_id": user["user_id"],
        "email": user.get("email", ""),
        "name": user.get("name", user["user_id"]),
        "picture": user.get("picture", ""),
        "role": role,
    }


def _serialize_admin_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": user["user_id"],
        "name": user.get("name", user["user_id"]),
        "email": user.get("email", ""),
        "role": _normalize_role_label(user.get("role") or "RM"),
        "is_active": bool(user.get("is_active", True)),
        "status": "active" if user.get("is_active", True) else "inactive",
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
        "last_login_at": user.get("last_login_at"),
        "must_change_password": bool(user.get("must_change_password", False)),
    }


def _serialize_product(product: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "code": product["code"],
        "name": product.get("name", ""),
        "is_type": product.get("is_type", ""),
        "en_type": product.get("en_type", ""),
        "tagline": product.get("tagline", ""),
        "description": product.get("description", ""),
        "max_tile_size": product.get("max_tile_size", ""),
        "areas": list(product.get("areas", [])),
        "params": dict(product.get("params", {})),
        "is_active": bool(product.get("is_active", True)),
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
        "created_by": product.get("created_by"),
        "updated_by": product.get("updated_by"),
        "source": product.get("source", "seed"),
    }


def _parse_seed_rm_users(settings: AppSettings) -> List[Dict[str, Any]]:
    if settings.rm_seed_users_json:
        try:
            parsed = json.loads(settings.rm_seed_users_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid RM_SEED_USERS_JSON: {exc}") from exc
        if not isinstance(parsed, list):
            raise RuntimeError("RM_SEED_USERS_JSON must be a JSON array")
        seed_users = [entry for entry in parsed if isinstance(entry, dict)]
        if not seed_users:
            raise RuntimeError("RM_SEED_USERS_JSON did not contain any valid user objects")
        return seed_users

    return [
        {
            "user_id": settings.rm_default_user_id,
            "password": settings.rm_default_password,
            "name": settings.rm_default_name,
            "email": settings.rm_default_email,
            "role": "rm",
            "is_active": True,
        }
    ]


async def _upsert_seed_rm_user(db: AsyncIOMotorDatabase, seed_user: Dict[str, Any], settings: AppSettings) -> bool:
    login_id = str(seed_user.get("user_id", "")).strip()
    password = str(seed_user.get("password", "")).strip()
    if not login_id or not password:
        logger.warning("Skipping invalid RM seed user without user_id/password")
        return False

    normalized_login_id = _normalize_login_id(login_id)
    now = datetime.now(timezone.utc)
    existing = await db.users.find_one({"login_id_normalized": normalized_login_id}, {"_id": 0})
    update_fields: Dict[str, Any] = {
        "user_id": login_id,
        "login_id_normalized": normalized_login_id,
        "email": str(seed_user.get("email", "")).strip(),
        "name": str(seed_user.get("name", login_id)).strip() or login_id,
        "picture": str(seed_user.get("picture", "")).strip(),
        "role": _role_for_storage(str(seed_user.get("role", "RM"))),
        "is_active": bool(seed_user.get("is_active", True)),
        "auth_provider": "rm_credentials",
        "must_change_password": bool(seed_user.get("must_change_password", False)),
        "updated_at": now,
        "updated_by": "system_seed",
    }

    should_reset_password = settings.rm_force_seed_password_reset or not existing or not existing.get("password_hash")
    if should_reset_password:
        update_fields.update(_create_password_record(password, settings.password_hash_iterations))

    await db.users.update_one(
        {"login_id_normalized": normalized_login_id},
        {
            "$set": update_fields,
            "$setOnInsert": {
                "created_at": now,
                "created_by": "system_seed",
                "last_login_at": None,
            },
        },
        upsert=True,
    )
    return True


async def _ensure_collection_validator(db: AsyncIOMotorDatabase, collection_name: str, validator: Dict[str, Any]) -> None:
    collection_names = await db.list_collection_names(filter={"name": collection_name})
    if collection_name in collection_names:
        await db.command(
            {
                "collMod": collection_name,
                "validator": validator,
                "validationLevel": "moderate",
                "validationAction": "error",
            }
        )
        logger.info("Updated validator for MongoDB collection %s.", collection_name)
        return

    await db.create_collection(
        collection_name,
        validator=validator,
        validationLevel="moderate",
        validationAction="error",
    )
    logger.info("Created MongoDB collection %s with validator.", collection_name)


async def ensure_collection_validators(db: AsyncIOMotorDatabase) -> None:
    user_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "login_id_normalized", "name", "role", "is_active", "created_at", "updated_at"],
            "properties": {
                "user_id": {"bsonType": "string", "minLength": 1},
                "login_id_normalized": {"bsonType": "string", "minLength": 1},
                "name": {"bsonType": "string", "minLength": 1},
                "email": {"bsonType": ["string", "null"]},
                "role": {"enum": ["rm", "ADMIN"]},
                "is_active": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "last_login_at": {"bsonType": ["date", "null"]},
                "must_change_password": {"bsonType": ["bool", "null"]},
            },
        }
    }
    product_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["code", "code_normalized", "name", "name_normalized", "areas", "params", "is_active", "is_deleted", "created_at", "updated_at"],
            "properties": {
                "code": {"bsonType": "string", "minLength": 1},
                "code_normalized": {"bsonType": "string", "minLength": 1},
                "name": {"bsonType": "string", "minLength": 1},
                "name_normalized": {"bsonType": "string", "minLength": 1},
                "areas": {"bsonType": "array"},
                "params": {"bsonType": "object"},
                "is_active": {"bsonType": "bool"},
                "is_deleted": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        }
    }
    await _ensure_collection_validator(db, "users", user_validator)
    await _ensure_collection_validator(db, "products", product_validator)
    await _ensure_collection_validator(db, "competitors", {"$jsonSchema": {"bsonType": "object", "required": ["id", "name", "is_active", "is_deleted", "created_at", "updated_at"], "properties": {"id": {"bsonType": "string", "minLength": 1}, "name": {"bsonType": "string", "minLength": 1}, "is_active": {"bsonType": "bool"}, "is_deleted": {"bsonType": "bool"}, "created_at": {"bsonType": "date"}, "updated_at": {"bsonType": "date"}}}})
    await _ensure_collection_validator(db, "competitor_products", {"$jsonSchema": {"bsonType": "object", "required": ["id", "competitor_id", "name", "is_active", "is_deleted", "created_at", "updated_at"], "properties": {"id": {"bsonType": "string", "minLength": 1}, "competitor_id": {"bsonType": "string", "minLength": 1}, "name": {"bsonType": "string", "minLength": 1}, "is_active": {"bsonType": "bool"}, "is_deleted": {"bsonType": "bool"}, "created_at": {"bsonType": "date"}, "updated_at": {"bsonType": "date"}}}})


def _build_seed_product_document(product: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "code": _normalize_product_code(product["code"]),
        "code_normalized": _normalize_product_code(product["code"]),
        "name": str(product.get("name", "")).strip(),
        "name_normalized": _normalize_product_name(str(product.get("name", "")).strip()),
        "is_type": str(product.get("is_type", "")).strip(),
        "en_type": str(product.get("en_type", "")).strip(),
        "tagline": str(product.get("tagline", "")).strip(),
        "description": str(product.get("description", "")).strip(),
        "max_tile_size": str(product.get("max_tile_size", "")).strip(),
        "areas": list(product.get("areas", [])),
        "params": dict(product.get("params", {})),
        "is_active": bool(product.get("is_active", True)),
        "is_deleted": False,
        "source": "seed",
        "created_at": now,
        "updated_at": now,
        "created_by": "system_seed",
        "updated_by": "system_seed",
    }


async def seed_kamdhenu_products(db: AsyncIOMotorDatabase) -> None:
    inserted_count = 0
    for product in KAMDHENU_PRODUCTS:
        seed_document = _build_seed_product_document(product)
        existing = await db.products.find_one({"code_normalized": seed_document["code_normalized"]}, {"_id": 0})
        if not existing:
            await db.products.insert_one(seed_document)
            inserted_count += 1
            continue

        patch: Dict[str, Any] = {}
        for key in ("code", "code_normalized", "name_normalized"):
            if existing.get(key) != seed_document[key]:
                patch[key] = seed_document[key]
        if "is_deleted" not in existing:
            patch["is_deleted"] = False
        if "source" not in existing:
            patch["source"] = existing.get("source") or "seed"
        if patch:
            patch["updated_at"] = datetime.now(timezone.utc)
            patch["updated_by"] = "system_seed"
            await db.products.update_one({"code_normalized": seed_document["code_normalized"]}, {"$set": patch})

    logger.info("Seeded or verified %s Kamdhenu product document(s).", inserted_count)


async def _list_kamdhenu_products(db: AsyncIOMotorDatabase, include_inactive: bool = False) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {"is_deleted": {"$ne": True}}
    if not include_inactive:
        filters["is_active"] = True
    products = await db.products.find(filters, {"_id": 0, "code_normalized": 0, "name_normalized": 0, "is_deleted": 0}).sort("code", ASCENDING).to_list(length=None)
    if products:
        return products
    return [dict(product) for product in KAMDHENU_PRODUCTS if include_inactive or product.get("is_active", True)]


async def _get_kamdhenu_product_or_404(db: AsyncIOMotorDatabase, code: str, include_inactive: bool = False) -> Dict[str, Any]:
    filters: Dict[str, Any] = {
        "code_normalized": _normalize_product_code(code),
        "is_deleted": {"$ne": True},
    }
    if not include_inactive:
        filters["is_active"] = True
    product = await db.products.find_one(filters, {"_id": 0, "code_normalized": 0, "name_normalized": 0, "is_deleted": 0})
    if product:
        return product

    fallback = KAMDHENU_PRODUCTS_BY_CODE.get(_normalize_product_code(code))
    if fallback and (include_inactive or fallback.get("is_active", True)):
        return fallback
    raise HTTPException(status_code=404, detail="Kamdhenu product not found")


async def seed_rm_users(db: AsyncIOMotorDatabase, settings: AppSettings) -> None:
    seed_users = _parse_seed_rm_users(settings)
    seeded_count = 0
    for seed_user in seed_users:
        if await _upsert_seed_rm_user(db, seed_user, settings):
            seeded_count += 1

    if settings.rm_default_password == DEFAULT_RM_SEED_PASSWORD:
        logger.warning("RM_DEFAULT_PASSWORD is using the default demo password. Change it for production deployments.")

    logger.info("Seeded or verified %s RM credential user(s).", seeded_count)


def _parse_seed_admin_users(settings: AppSettings) -> List[Dict[str, Any]]:
    if settings.admin_seed_users_json:
        try:
            parsed = json.loads(settings.admin_seed_users_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid ADMIN_SEED_USERS_JSON: {exc}") from exc
        if not isinstance(parsed, list):
            raise RuntimeError("ADMIN_SEED_USERS_JSON must be a JSON array")
        seed_users = [entry for entry in parsed if isinstance(entry, dict)]
        if not seed_users:
            raise RuntimeError("ADMIN_SEED_USERS_JSON did not contain any valid user objects")
        return seed_users

    return [{"user_id": settings.admin_default_user_id, "password": settings.admin_default_password, "name": settings.admin_default_name, "email": settings.admin_default_email, "role": "ADMIN", "is_active": True}]


async def _upsert_seed_admin_user(db: AsyncIOMotorDatabase, seed_user: Dict[str, Any], settings: AppSettings) -> bool:
    login_id = str(seed_user.get("user_id", "")).strip()
    password = str(seed_user.get("password", "")).strip()
    if not login_id or not password:
        logger.warning("Skipping invalid admin seed user without user_id/password")
        return False

    normalized_login_id = _normalize_login_id(login_id)
    now = datetime.now(timezone.utc)
    existing = await db.users.find_one({"login_id_normalized": normalized_login_id}, {"_id": 0})
    update_fields: Dict[str, Any] = {
        "user_id": login_id,
        "login_id_normalized": normalized_login_id,
        "email": str(seed_user.get("email", "")).strip(),
        "name": str(seed_user.get("name", login_id)).strip() or login_id,
        "picture": str(seed_user.get("picture", "")).strip(),
        "role": "ADMIN",
        "is_active": bool(seed_user.get("is_active", True)),
        "auth_provider": "admin_credentials",
        "must_change_password": bool(seed_user.get("must_change_password", False)),
        "updated_at": now,
        "updated_by": "system_seed",
    }
    if not existing or not existing.get("password_hash"):
        update_fields.update(_create_password_record(password, settings.password_hash_iterations))

    await db.users.update_one(
        {"login_id_normalized": normalized_login_id},
        {
            "$set": update_fields,
            "$setOnInsert": {"created_at": now, "created_by": "system_seed", "last_login_at": None},
        },
        upsert=True,
    )
    return True


async def seed_admin_users(db: AsyncIOMotorDatabase, settings: AppSettings) -> None:
    seed_users = _parse_seed_admin_users(settings)
    seeded_count = 0
    for seed_user in seed_users:
        if await _upsert_seed_admin_user(db, seed_user, settings):
            seeded_count += 1

    if settings.admin_default_password == DEFAULT_ADMIN_SEED_PASSWORD:
        logger.warning("ADMIN_DEFAULT_PASSWORD is using the default demo password. Change it for production deployments.")

    logger.info("Seeded or verified %s admin credential user(s).", seeded_count)


async def _create_user_session(db: AsyncIOMotorDatabase, user_id: str, expires_at: datetime) -> str:
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise ValueError("Cannot create a session without a user_id")

    for attempt in range(3):
        session_token = f"rm_session_{secrets.token_urlsafe(32)}"
        session_token_hash = _hash_session_token(session_token)
        if not _is_valid_session_token_hash(session_token_hash):
            raise RuntimeError("Generated an invalid session token hash")

        session_doc = {
            "user_id": normalized_user_id,
            "session_token_hash": session_token_hash,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await db.user_sessions.insert_one(session_doc)
            return session_token
        except DuplicateKeyError:
            logger.warning("Session token hash collision for user_id=%s on attempt %s", normalized_user_id, attempt + 1)
        except PyMongoError:
            logger.exception("Failed to persist session for user_id=%s", normalized_user_id)
            raise

    raise RuntimeError("Failed to create a unique session token after 3 attempts")


async def _delete_session_by_id(db: AsyncIOMotorDatabase, session_id: Any, reason: str) -> None:
    await db.user_sessions.delete_one({"_id": session_id})
    logger.warning("Deleted invalid session document _id=%s: %s", session_id, reason)


def _normalize_index_key(index_document: Dict[str, Any]) -> Tuple[Tuple[str, int], ...]:
    key_document = index_document.get("key") or {}
    return tuple((field, int(direction)) for field, direction in key_document.items())


def _is_expected_session_token_index(index_document: Dict[str, Any]) -> bool:
    return (
        _normalize_index_key(index_document) == (("session_token_hash", ASCENDING),)
        and index_document.get("unique") is True
        and index_document.get("partialFilterExpression") == _session_token_partial_filter()
    )


def _is_expected_session_ttl_index(index_document: Dict[str, Any]) -> bool:
    return (
        _normalize_index_key(index_document) == (("expires_at", ASCENDING),)
        and index_document.get("expireAfterSeconds") == 0
        and index_document.get("unique") is not True
    )


async def _drop_index_with_logging(collection: Any, index_name: str, reason: str) -> None:
    logger.warning("Dropping conflicting index %s on %s: %s", index_name, collection.name, reason)
    try:
        await collection.drop_index(index_name)
    except OperationFailure as exc:
        if "index not found" in str(exc).lower():
            return
        raise


async def _cleanup_invalid_user_sessions(collection: Any) -> int:
    invalid_filter = {
        "$or": [
            {"session_token_hash": {"$exists": False}},
            {"session_token_hash": None},
            {"session_token_hash": ""},
            {"session_token_hash": {"$regex": r"^\s+$"}},
        ]
    }
    result = await collection.delete_many(invalid_filter)
    deleted_count = int(result.deleted_count)
    if deleted_count:
        logger.warning(
            "Deleted %s invalid session document(s) with missing or empty session_token_hash.",
            deleted_count,
        )
    else:
        logger.info("No invalid session documents required cleanup before index reconciliation.")
    return deleted_count


async def _find_duplicate_session_token_hashes(collection: Any) -> List[Dict[str, Any]]:
    pipeline = [
        {"$match": _session_token_partial_filter()},
        {
            "$group": {
                "_id": "$session_token_hash",
                "count": {"$sum": 1},
                "session_ids": {"$push": "$_id"},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
        {"$limit": 5},
    ]
    return await collection.aggregate(pipeline).to_list(length=5)


async def ensure_user_session_indexes(db: AsyncIOMotorDatabase) -> None:
    collection = db.user_sessions
    logger.info("Reconciling MongoDB indexes for %s.", collection.name)

    await _cleanup_invalid_user_sessions(collection)

    duplicates = await _find_duplicate_session_token_hashes(collection)
    if duplicates:
        duplicate_hashes = [entry["_id"] for entry in duplicates]
        logger.error("Duplicate valid session_token_hash values remain in %s: %s", collection.name, duplicate_hashes)
        raise RuntimeError(
            "Cannot create a unique session token index because duplicate valid session_token_hash values still exist"
        )

    session_index_present = False
    ttl_index_present = False
    for index_document in await collection.list_indexes().to_list(length=None):
        index_name = index_document.get("name", "<unnamed>")
        index_key = _normalize_index_key(index_document)
        if index_name == "_id_":
            continue

        if index_key == (("session_token_hash", ASCENDING),) or index_name == SESSION_TOKEN_INDEX_NAME:
            if _is_expected_session_token_index(index_document):
                session_index_present = True
                logger.info("Verified session token index %s on %s.", index_name, collection.name)
            else:
                await _drop_index_with_logging(
                    collection,
                    index_name,
                    "replacing legacy session_token_hash index with partial unique index",
                )
            continue

        if index_key == (("expires_at", ASCENDING),) or index_name == SESSION_TTL_INDEX_NAME:
            if _is_expected_session_ttl_index(index_document):
                ttl_index_present = True
                logger.info("Verified session TTL index %s on %s.", index_name, collection.name)
            else:
                await _drop_index_with_logging(
                    collection,
                    index_name,
                    "replacing legacy expires_at index with TTL index",
                )

    if not session_index_present:
        logger.info("Creating partial unique session token index on %s.session_token_hash.", collection.name)
        try:
            await collection.create_index(
                [("session_token_hash", ASCENDING)],
                name=SESSION_TOKEN_INDEX_NAME,
                unique=True,
                background=True,
                partialFilterExpression=_session_token_partial_filter(),
            )
        except (DuplicateKeyError, OperationFailure) as exc:
            logger.exception("Failed to create partial unique session token index on %s", collection.name)
            raise RuntimeError("Failed to create the partial unique session token index") from exc

    if not ttl_index_present:
        logger.info("Creating TTL session expiry index on %s.expires_at.", collection.name)
        try:
            await collection.create_index(
                [("expires_at", ASCENDING)],
                name=SESSION_TTL_INDEX_NAME,
                expireAfterSeconds=0,
                background=True,
            )
        except OperationFailure as exc:
            logger.exception("Failed to create TTL session expiry index on %s", collection.name)
            raise RuntimeError("Failed to create the session expiry TTL index") from exc

    logger.info("Finished reconciling MongoDB indexes for %s.", collection.name)


async def _get_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    token = _extract_session_token(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        session_token_hash = _hash_session_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    session_doc = await db.user_sessions.find_one({"session_token_hash": session_token_hash})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")

    stored_token_hash = session_doc.get("session_token_hash")
    if not _is_valid_session_token_hash(stored_token_hash):
        await _delete_session_by_id(db, session_doc["_id"], "missing or empty session_token_hash")
        raise HTTPException(status_code=401, detail="Session invalid")

    expires_at = session_doc.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not isinstance(expires_at, datetime):
        await _delete_session_by_id(db, session_doc["_id"], "invalid expires_at value")
        raise HTTPException(status_code=401, detail="Session invalid")
    if expires_at <= datetime.now(timezone.utc):
        await _delete_session_by_id(db, session_doc["_id"], "session expired")
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User is inactive")
    return user


async def get_current_user(user: Dict[str, Any] = Depends(_get_authenticated_user)) -> Dict[str, Any]:
    if not _is_rm_role(user.get("role")):
        raise HTTPException(status_code=403, detail="RM access required")
    return user


async def get_current_admin_user(user: Dict[str, Any] = Depends(_get_authenticated_user)) -> Dict[str, Any]:
    if not _is_admin_role(user.get("role")):
        raise HTTPException(status_code=403, detail="ADMIN access required")
    return user


async def _record_user_login(db: AsyncIOMotorDatabase, user_id: str) -> None:
    now = datetime.now(timezone.utc)
    await db.users.update_one({"user_id": user_id}, {"$set": {"last_login_at": now, "updated_at": now}})


async def seed_competitors(db: AsyncIOMotorDatabase) -> None:
    now = datetime.now(timezone.utc)
    for competitor in COMPETITORS:
        competitor_doc = {"id": competitor["id"], "name": competitor["name"], "is_active": True, "is_deleted": False, "created_at": now, "updated_at": now, "created_by": "system_seed", "updated_by": "system_seed"}
        await db.competitors.update_one({"id": competitor["id"]}, {"$setOnInsert": competitor_doc}, upsert=True)
        for product in competitor.get("products", []):
            product_id = f"{competitor['id']}::{product['name']}"
            product_doc = {"id": product_id, "competitor_id": competitor["id"], "name": product["name"], "is_type": product.get("is_type", ""), "en_type": product.get("en_type", ""), "competes_with": product.get("competes_with", ""), "is_active": True, "is_deleted": False, "created_at": now, "updated_at": now, "created_by": "system_seed", "updated_by": "system_seed"}
            await db.competitor_products.update_one({"id": product_id}, {"$setOnInsert": product_doc}, upsert=True)

async def ensure_database_indexes(db: AsyncIOMotorDatabase) -> None:
    logger.info("Ensuring MongoDB indexes for core collections.")
    await ensure_collection_validators(db)
    await db.users.create_index([("login_id_normalized", ASCENDING)], name=USER_LOGIN_ID_INDEX_NAME, unique=True, background=True)
    await db.users.create_index([("user_id", ASCENDING)], name=USER_ID_INDEX_NAME, unique=True, background=True)
    await db.users.create_index([("role", ASCENDING), ("is_active", ASCENDING)], name=USER_STATUS_INDEX_NAME, background=True)
    await ensure_user_session_indexes(db)
    await db.products.create_index(
        [("code_normalized", ASCENDING)],
        name=PRODUCT_CODE_INDEX_NAME,
        unique=True,
        background=True,
        partialFilterExpression={"is_deleted": False},
    )
    await db.products.create_index([("name_normalized", ASCENDING)], name=PRODUCT_NAME_INDEX_NAME, background=True)
    await db.competitors.create_index([("id", ASCENDING)], name="competitor_id_unique", unique=True, background=True)
    await db.competitor_products.create_index([("id", ASCENDING)], name="competitor_product_id_unique", unique=True, background=True)
    await db.competitor_products.create_index([("competitor_id", ASCENDING), ("is_deleted", ASCENDING)], name="competitor_product_owner", background=True)
    await db.products.create_index([("is_active", ASCENDING), ("is_deleted", ASCENDING)], name=PRODUCT_STATUS_INDEX_NAME, background=True)
    await seed_competitors(db)
    await db.custom_products.create_index([("product_id", ASCENDING)], unique=True, background=True)
    await db.pitch_cache.create_index([("cache_key", ASCENDING)], unique=True, background=True)
    await db.recommendation_cache.create_index([("cache_key", ASCENDING)], unique=True, background=True)
    await db[COMPETITOR_TDS_COLLECTION].create_index(
        [("competitor_id", ASCENDING), ("product_name", ASCENDING)],
        unique=True,
        background=True,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    configure_logging(settings.log_level)
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

    if not settings.mongo_url or not settings.db_name:
        raise RuntimeError("MONGO_URL and DB_NAME must be configured before starting the backend")

    client = AsyncIOMotorClient(
        settings.mongo_url,
        serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
        connectTimeoutMS=settings.mongo_connect_timeout_ms,
        uuidRepresentation="standard",
    )
    db = client[settings.db_name]

    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB database %s.", settings.db_name)
        await ensure_database_indexes(db)
        await seed_rm_users(db, settings)
        await seed_admin_users(db, settings)
        await seed_kamdhenu_products(db)
        await ensure_competitor_tds_seeded(db)
        start_competitor_tds_scheduler(db, logger)
        app.state.settings = settings
        app.state.mongo_client = client
        app.state.db = db
        logger.info("Backend startup completed successfully.")
        yield
    except Exception:
        logger.exception("Backend startup failed")
        await stop_competitor_tds_scheduler()
        client.close()
        raise
    finally:
        logger.info("Shutting down backend services.")
        await stop_competitor_tds_scheduler()
        client.close()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
api_router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_parse_cors_origins(os.environ.get("CORS_ORIGINS", "")),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request payload",
            "errors": exc.errors(),
        },
    )


async def _resolve_competitor(db: AsyncIOMotorDatabase, cid: str) -> Optional[Dict[str, Any]]:
    return await resolve_tds_competitor(db, cid)


def _extract_max_number(value: str) -> Optional[float]:
    import re

    if not value or not isinstance(value, str):
        return None
    numbers = re.findall(r"\d+\.?\d*", value)
    if not numbers:
        return None
    try:
        return max(float(number) for number in numbers)
    except ValueError:
        return None


def _extract_min_number(value: str) -> Optional[float]:
    import re

    if not value or not isinstance(value, str):
        return None
    numbers = re.findall(r"\d+\.?\d*", value)
    if not numbers:
        return None
    try:
        return min(float(number) for number in numbers)
    except ValueError:
        return None


def _kamdhenu_wins(param: str, kam_val: str, comp_vals: List[str]) -> bool:
    direction = PARAM_DIRECTIONS.get(param)
    if not direction or not kam_val or kam_val == "-":
        return False

    if direction == "higher":
        kam_num = _extract_max_number(kam_val)
        if kam_num is None:
            return False
        for comp_val in comp_vals:
            comp_num = _extract_max_number(comp_val)
            if comp_num is not None and comp_num >= kam_num:
                return False
        return True

    kam_num = _extract_min_number(kam_val)
    if kam_num is None:
        return False
    for comp_val in comp_vals:
        comp_num = _extract_min_number(comp_val)
        if comp_num is not None and comp_num <= kam_num:
            return False
    return True


@api_router.post("/auth/login")
async def auth_login(
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: AppSettings = Depends(get_settings_from_request),
):
    user = await db.users.find_one(
        {"login_id_normalized": _normalize_login_id(payload.user_id)},
        {"_id": 0},
    )
    if not user or not _is_rm_role(user.get("role")) or not user.get("is_active", True):
        logger.warning("RM login failed for user_id=%s: invalid user", payload.user_id)
        raise HTTPException(status_code=401, detail="Invalid user ID or password")

    if not _verify_password(payload.password, user, settings):
        logger.warning("RM login failed for user_id=%s: invalid password", payload.user_id)
        raise HTTPException(status_code=401, detail="Invalid user ID or password")

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_ttl_days)
    session_token = await _create_user_session(db, user["user_id"], expires_at)
    await _record_user_login(db, user["user_id"])
    logger.info("RM login succeeded for user_id=%s", user["user_id"])
    return {
        "session_token": session_token,
        "token_type": "Bearer",
        "expires_at": expires_at.isoformat(),
        "user": _public_user(user),
    }


@api_router.post("/admin/auth/login")
async def admin_auth_login(
    payload: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: AppSettings = Depends(get_settings_from_request),
):
    user = await db.users.find_one(
        {"login_id_normalized": _normalize_login_id(payload.user_id)},
        {"_id": 0},
    )
    if not user or not _is_admin_role(user.get("role")) or not user.get("is_active", True):
        logger.warning("Admin login failed for user_id=%s: invalid user", payload.user_id)
        raise HTTPException(status_code=401, detail="Invalid user ID or password")

    if not _verify_password(payload.password, user, settings):
        logger.warning("Admin login failed for user_id=%s: invalid password", payload.user_id)
        raise HTTPException(status_code=401, detail="Invalid user ID or password")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.admin_session_ttl_hours)
    session_token = await _create_user_session(db, user["user_id"], expires_at)
    await _record_user_login(db, user["user_id"])
    logger.info("Admin login succeeded for user_id=%s", user["user_id"])
    return {
        "session_token": session_token,
        "token_type": "Bearer",
        "expires_at": expires_at.isoformat(),
        "user": _public_user(user),
    }


@api_router.get("/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(get_current_user)):
    return _public_user(user)


@api_router.get("/admin/auth/me")
async def admin_auth_me(user: Dict[str, Any] = Depends(get_current_admin_user)):
    return _public_user(user)


@api_router.post("/auth/logout")
async def auth_logout(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    token = _extract_session_token(request, authorization)
    if token:
        try:
            await db.user_sessions.delete_one({"session_token_hash": _hash_session_token(token)})
        except ValueError:
            logger.warning("Ignoring logout request with an empty session token payload")
    return {"ok": True}


@api_router.post("/admin/auth/logout")
async def admin_auth_logout(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await auth_logout(request=request, authorization=authorization, db=db)


@api_router.get("/catalog/substrates")
async def list_substrates():
    return {"substrates": SUBSTRATES}


@api_router.get("/catalog/tile-types")
async def list_tile_types(substrate_id: Optional[str] = None):
    if substrate_id:
        allowed = SUBSTRATE_TILE_MAP.get(substrate_id, [])
        return {"tile_types": [item for item in TILE_TYPES if item["id"] in allowed]}
    return {"tile_types": TILE_TYPES}


@api_router.get("/catalog/areas")
async def list_areas():
    return {"areas": AREAS}


@api_router.get("/catalog/kamdhenu")
async def list_kamdhenu(db: AsyncIOMotorDatabase = Depends(get_db)):
    return {"products": await _list_kamdhenu_products(db)}


@api_router.get("/catalog/competitors")
async def list_competitors(db: AsyncIOMotorDatabase = Depends(get_db)):
    docs = {
        (doc["competitor_id"], doc["product_name"]): doc
        for doc in await list_competitor_tds_docs(db)
    }
    enriched = []
    for competitor in COMPETITORS:
        products = []
        for index, product in enumerate(competitor["products"]):
            item = {
                "id": f"{competitor['id']}::{index}",
                **product,
            }
            doc = docs.get((competitor["id"], product["name"]))
            if doc:
                item.update(
                    {
                        "tds_url": doc.get("tds_url", ""),
                        "tds_file_hash": doc.get("tds_file_hash", ""),
                        "tds_text_hash": doc.get("tds_text_hash", ""),
                        "last_checked_at": doc.get("last_checked_at"),
                        "last_updated_at": doc.get("last_updated_at"),
                        "next_check_at": doc.get("next_check_at"),
                        "update_frequency_days": doc.get("update_frequency_days", product.get("update_frequency_days", 15)),
                        "report_status": doc.get("report_status", product.get("report_status", "due")),
                        "technical_report": doc.get("technical_report"),
                        "pending_technical_report": doc.get("pending_technical_report"),
                        "tds_source_version": doc.get("tds_source_version", product.get("tds_source_version", "seed-v1")),
                    }
                )
            products.append(item)
        enriched.append({"id": competitor["id"], "name": competitor["name"], "products": products})
    return {"competitors": enriched}


@api_router.post("/recommend")
async def recommend(req: RecommendRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    code = recommend_kamdhenu(req.substrate_id, req.tile_type_id, req.tile_size, req.area)
    product = await _get_kamdhenu_product_or_404(db, code)

    reasons: List[str] = []
    if req.substrate_id in {"plywood", "gypsum_boards", "mdf", "metallic", "glass", "rubber_pvc_lino"}:
        reasons.append(f"Substrate '{req.substrate_id.replace('_', ' ')}' needs a high-flexibility S1/S2 adhesive.")
    if req.area in {"Outdoor / Facade", "Elevation", "Swimming Pool", "Industrial Floor"}:
        reasons.append(f"Application area '{req.area}' demands a deformable, weather-resistant adhesive.")
    if req.tile_type_id in {"marble", "granite", "stone", "limestone", "travertine"}:
        reasons.append(f"Natural stone category '{req.tile_type_id}' benefits from a non-staining stone adhesive.")
    if req.tile_type_id in {"vitrified", "porcelain"}:
        reasons.append(f"Low-porosity {req.tile_type_id} tiles need enhanced polymer-modified bonding.")
    reasons.append(f"Recommended for tile size {req.tile_size}.")
    return {"recommendation": product, "reasons": reasons}


@api_router.post("/compare")
async def compare(req: CompareRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    kamdhenu = await _get_kamdhenu_product_or_404(db, req.kamdhenu_code)
    columns: List[Dict[str, Any]] = [
        {
            "brand": "Kamdhenu",
            "name": kamdhenu["name"],
            "code": kamdhenu["code"],
            "is_type": kamdhenu["is_type"],
            "en_type": kamdhenu["en_type"],
            "is_kamdhenu": True,
            "params": kamdhenu["params"],
            "tagline": kamdhenu["tagline"],
            "max_tile_size": kamdhenu["max_tile_size"],
        }
    ]

    for competitor_id in req.competitor_product_ids:
        competitor = await _resolve_competitor(db, competitor_id)
        if not competitor:
            logger.warning("Skipping unknown competitor_product_id=%s", competitor_id)
            continue
        columns.append(
            {
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
            }
        )

    for custom_product in req.custom_products:
        custom_payload = custom_product.model_dump()
        columns.append(
            {
                "brand": custom_payload.get("brand", "Custom"),
                "name": custom_payload.get("name", "Custom Product"),
                "code": "",
                "is_type": custom_payload.get("is_type", ""),
                "en_type": custom_payload.get("en_type", ""),
                "is_kamdhenu": False,
                "params": enrich_competitor_params(custom_payload),
                "tagline": "",
                "max_tile_size": "",
                "is_custom": True,
            }
        )

    keys = list(kamdhenu["params"].keys())
    for column in columns[1:]:
        for key in column["params"].keys():
            if key not in keys:
                keys.append(key)

    rows = []
    for key in keys:
        kam_value = columns[0]["params"].get(key, "-")
        competitor_values = [column["params"].get(key, "-") for column in columns[1:]]
        rows.append(
            {
                "param": key,
                "values": [column["params"].get(key, "-") for column in columns],
                "is_tds": [True] + [False] * (len(columns) - 1),
                "kamdhenu_advantage": _kamdhenu_wins(key, kam_value, competitor_values),
            }
        )

    pitches = [
        f"{kamdhenu['code']} is classified {kamdhenu['is_type']} ({kamdhenu['en_type']}) per Indian and EN standards.",
        kamdhenu["tagline"],
        f"Pot life of {kamdhenu['params'].get('Pot Life', 'N/A')} supports longer workable time on site.",
        f"Initial bond strength {kamdhenu['params'].get('Initial Tensile Adhesion (IS)', 'N/A')} aligns with IS 15477:2019 expectations.",
        f"Coverage of {kamdhenu['params'].get('Coverage', 'N/A')} supports better material economy.",
        "Made in India with pan-India supply support and technical assistance.",
    ]

    return {"columns": columns, "rows": rows, "kamdhenu_pitches": pitches}


@api_router.get("/admin/dashboard")
async def admin_dashboard(
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del admin_user
    total_users = await db.users.count_documents({"role": "rm"})
    active_users = await db.users.count_documents({"role": "rm", "is_active": True})
    total_products = await db.products.count_documents({"is_deleted": {"$ne": True}})
    active_products = await db.products.count_documents({"is_deleted": {"$ne": True}, "is_active": True})
    return {"metrics": {"total_rm_users": total_users, "active_rm_users": active_users, "total_products": total_products, "active_products": active_products}}


@api_router.get("/admin/meta")
async def admin_meta(admin_user: Dict[str, Any] = Depends(get_current_admin_user)):
    del admin_user
    return {"roles": ["RM", "ADMIN"], "areas": AREAS, "product_param_keys": PRODUCT_PARAM_KEYS, "seed_product_codes": [product["code"] for product in KAMDHENU_PRODUCTS]}


@api_router.get("/admin/users")
async def admin_list_users(
    page: int = 1,
    page_size: int = 10,
    search: str = "",
    status_filter: str = "all",
    role_filter: str = "RM",
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del admin_user
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters: Dict[str, Any] = {}
    normalized_role = _normalize_role_label(role_filter)
    if normalized_role in {"RM", "ADMIN"}:
        filters["role"] = _role_for_storage(normalized_role)
    if status_filter == "active":
        filters["is_active"] = True
    elif status_filter == "inactive":
        filters["is_active"] = False
    if search.strip():
        filters["$or"] = [
            {"user_id": {"$regex": search.strip(), "$options": "i"}},
            {"name": {"$regex": search.strip(), "$options": "i"}},
            {"email": {"$regex": search.strip(), "$options": "i"}},
        ]

    total = await db.users.count_documents(filters)
    cursor = db.users.find(filters, {"_id": 0}).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    users = [_serialize_admin_user(user) for user in await cursor.to_list(length=page_size)]
    return {"items": users, "total": total, "page": page, "page_size": page_size}


@api_router.post("/admin/users")
async def admin_create_user(
    payload: AdminUserCreateRequest,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: AppSettings = Depends(get_settings_from_request),
):
    now = datetime.now(timezone.utc)
    password = payload.password or _generate_temporary_password()
    document = {
        "user_id": payload.user_id.strip(),
        "login_id_normalized": _normalize_login_id(payload.user_id),
        "name": payload.name.strip(),
        "email": payload.email.strip(),
        "picture": "",
        "role": _role_for_storage(payload.role),
        "is_active": payload.is_active,
        "must_change_password": payload.password is None,
        "auth_provider": "credentials",
        "created_at": now,
        "updated_at": now,
        "created_by": admin_user["user_id"],
        "updated_by": admin_user["user_id"],
        "last_login_at": None,
    }
    document.update(_create_password_record(password, settings.password_hash_iterations))
    try:
        await db.users.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="User ID already exists") from exc
    response = {"item": _serialize_admin_user(document)}
    if payload.password is None:
        response["temporary_password"] = password
    return response


@api_router.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    existing = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    clear_sessions = False
    if payload.user_id is not None:
        update_fields["user_id"] = payload.user_id.strip()
        update_fields["login_id_normalized"] = _normalize_login_id(payload.user_id)
        clear_sessions = payload.user_id.strip() != user_id
    if payload.name is not None:
        update_fields["name"] = payload.name.strip()
    if payload.email is not None:
        update_fields["email"] = payload.email.strip()
    if payload.role is not None:
        update_fields["role"] = _role_for_storage(payload.role)
        clear_sessions = True
    if payload.is_active is not None:
        update_fields["is_active"] = payload.is_active
        if not payload.is_active:
            clear_sessions = True

    try:
        await db.users.update_one({"user_id": user_id}, {"$set": update_fields})
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="User ID already exists") from exc

    if clear_sessions:
        await db.user_sessions.delete_many({"user_id": user_id})

    updated = await db.users.find_one({"user_id": update_fields.get("user_id", user_id)}, {"_id": 0})
    return {"item": _serialize_admin_user(updated)}


@api_router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: str,
    payload: AdminUserPasswordResetRequest,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: AppSettings = Depends(get_settings_from_request),
):
    existing = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    password = payload.password or _generate_temporary_password()
    update_fields = _create_password_record(password, settings.password_hash_iterations)
    update_fields.update({"must_change_password": payload.password is None, "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]})
    await db.users.update_one({"user_id": user_id}, {"$set": update_fields})
    await db.user_sessions.delete_many({"user_id": user_id})
    response = {"ok": True}
    if payload.password is None:
        response["temporary_password"] = password
    return response


@api_router.post("/admin/users/{user_id}/activate")
async def admin_activate_user(
    user_id: str,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    update = {"is_active": True, "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    result = await db.users.update_one({"user_id": user_id}, {"$set": update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="User not found")
    current = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"item": _serialize_admin_user(current)}


@api_router.post("/admin/users/{user_id}/deactivate")
async def admin_deactivate_user(
    user_id: str,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    update = {"is_active": False, "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    result = await db.users.update_one({"user_id": user_id}, {"$set": update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="User not found")
    await db.user_sessions.delete_many({"user_id": user_id})
    current = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"item": _serialize_admin_user(current)}


@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if user_id == admin_user["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own admin account")
    result = await db.users.delete_one({"user_id": user_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="User not found")
    await db.user_sessions.delete_many({"user_id": user_id})
    return {"ok": True}


@api_router.get("/admin/products")
async def admin_list_products(
    page: int = 1,
    page_size: int = 10,
    search: str = "",
    status_filter: str = "all",
    area_filter: str = "all",
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del admin_user
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters: Dict[str, Any] = {"is_deleted": {"$ne": True}}
    if status_filter == "active":
        filters["is_active"] = True
    elif status_filter == "inactive":
        filters["is_active"] = False
    if area_filter != "all":
        filters["areas"] = area_filter
    if search.strip():
        filters["$or"] = [
            {"code": {"$regex": search.strip(), "$options": "i"}},
            {"name": {"$regex": search.strip(), "$options": "i"}},
            {"tagline": {"$regex": search.strip(), "$options": "i"}},
        ]

    total = await db.products.count_documents(filters)
    cursor = db.products.find(filters, {"_id": 0, "code_normalized": 0, "name_normalized": 0, "is_deleted": 0}).sort("code", ASCENDING).skip((page - 1) * page_size).limit(page_size)
    products = [_serialize_product(product) for product in await cursor.to_list(length=page_size)]
    return {"items": products, "total": total, "page": page, "page_size": page_size}


@api_router.post("/admin/products")
async def admin_create_product(
    payload: AdminProductCreateRequest,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    document = {
        "code": _normalize_product_code(payload.code),
        "code_normalized": _normalize_product_code(payload.code),
        "name": payload.name.strip(),
        "name_normalized": _normalize_product_name(payload.name),
        "is_type": payload.is_type.strip(),
        "en_type": payload.en_type.strip(),
        "tagline": payload.tagline.strip(),
        "description": payload.description.strip(),
        "max_tile_size": payload.max_tile_size.strip(),
        "areas": payload.areas,
        "params": payload.params,
        "is_active": payload.is_active,
        "is_deleted": False,
        "source": "admin",
        "created_at": now,
        "updated_at": now,
        "created_by": admin_user["user_id"],
        "updated_by": admin_user["user_id"],
    }
    try:
        await db.products.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Product code already exists") from exc
    return {"item": _serialize_product(document)}


@api_router.put("/admin/products/{code}")
async def admin_update_product(
    code: str,
    payload: AdminProductUpdateRequest,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    existing = await db.products.find_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    update_fields: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    if payload.code is not None:
        update_fields["code"] = _normalize_product_code(payload.code)
        update_fields["code_normalized"] = _normalize_product_code(payload.code)
    if payload.name is not None:
        update_fields["name"] = payload.name.strip()
        update_fields["name_normalized"] = _normalize_product_name(payload.name)
    if payload.is_type is not None:
        update_fields["is_type"] = payload.is_type.strip()
    if payload.en_type is not None:
        update_fields["en_type"] = payload.en_type.strip()
    if payload.tagline is not None:
        update_fields["tagline"] = payload.tagline.strip()
    if payload.description is not None:
        update_fields["description"] = payload.description.strip()
    if payload.max_tile_size is not None:
        update_fields["max_tile_size"] = payload.max_tile_size.strip()
    if payload.areas is not None:
        update_fields["areas"] = payload.areas
    if payload.params is not None:
        update_fields["params"] = payload.params
    if payload.is_active is not None:
        update_fields["is_active"] = payload.is_active

    try:
        await db.products.update_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"$set": update_fields})
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Product code already exists") from exc

    updated = await db.products.find_one({"code_normalized": update_fields.get("code_normalized", _normalize_product_code(code)), "is_deleted": {"$ne": True}}, {"_id": 0})
    return {"item": _serialize_product(updated)}


@api_router.post("/admin/products/{code}/activate")
async def admin_activate_product(
    code: str,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    update = {"is_active": True, "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    result = await db.products.update_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"$set": update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Product not found")
    current = await db.products.find_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"_id": 0})
    return {"item": _serialize_product(current)}


@api_router.post("/admin/products/{code}/deactivate")
async def admin_deactivate_product(
    code: str,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    update = {"is_active": False, "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    result = await db.products.update_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"$set": update})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Product not found")
    current = await db.products.find_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"_id": 0})
    return {"item": _serialize_product(current)}


@api_router.delete("/admin/products/{code}")
async def admin_delete_product(
    code: str,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.products.update_one({"code_normalized": _normalize_product_code(code), "is_deleted": {"$ne": True}}, {"$set": {"is_deleted": True, "is_active": False, "updated_at": now, "updated_by": admin_user["user_id"], "deleted_at": now, "deleted_by": admin_user["user_id"]}})
    if not result.modified_count:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"ok": True}


def _serialize_competitor_product(product: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": product["id"],
        "competitor_id": product["competitor_id"],
        "name": product.get("name", ""),
        "is_type": product.get("is_type", ""),
        "en_type": product.get("en_type", ""),
        "competes_with": product.get("competes_with", ""),
        "is_active": bool(product.get("is_active", True)),
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
        "created_by": product.get("created_by"),
        "updated_by": product.get("updated_by"),
    }


def _serialize_competitor(competitor: Dict[str, Any], product_count: int = 0) -> Dict[str, Any]:
    return {
        "id": competitor["id"],
        "name": competitor.get("name", ""),
        "is_active": bool(competitor.get("is_active", True)),
        "product_count": product_count,
        "created_at": competitor.get("created_at"),
        "updated_at": competitor.get("updated_at"),
        "created_by": competitor.get("created_by"),
        "updated_by": competitor.get("updated_by"),
    }


@api_router.get("/admin/competitors")
async def admin_list_competitors(page: int = 1, page_size: int = 10, search: str = "", status_filter: str = "all", admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    del admin_user
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters: Dict[str, Any] = {"is_deleted": {"$ne": True}}
    if status_filter == "active": filters["is_active"] = True
    elif status_filter == "inactive": filters["is_active"] = False
    if search.strip(): filters["name"] = {"$regex": search.strip(), "$options": "i"}
    total = await db.competitors.count_documents(filters)
    docs = await db.competitors.find(filters, {"_id": 0}).sort("name", ASCENDING).skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    items = []
    for doc in docs:
        count = await db.competitor_products.count_documents({"competitor_id": doc["id"], "is_deleted": {"$ne": True}})
        items.append(_serialize_competitor(doc, count))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@api_router.post("/admin/competitors")
async def admin_create_competitor(payload: AdminCompetitorCreateRequest, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    now = datetime.now(timezone.utc)
    competitor_id = (payload.id or payload.name).strip().lower().replace(" ", "_")
    document = {"id": competitor_id, "name": payload.name.strip(), "is_active": payload.is_active, "is_deleted": False, "created_at": now, "updated_at": now, "created_by": admin_user["user_id"], "updated_by": admin_user["user_id"]}
    try: await db.competitors.insert_one(document)
    except DuplicateKeyError as exc: raise HTTPException(status_code=409, detail="Competitor ID already exists") from exc
    return {"item": _serialize_competitor(document)}


@api_router.put("/admin/competitors/{competitor_id}")
async def admin_update_competitor(competitor_id: str, payload: AdminCompetitorUpdateRequest, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    update = {"updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    if payload.name is not None: update["name"] = payload.name.strip()
    if payload.is_active is not None: update["is_active"] = payload.is_active
    result = await db.competitors.update_one({"id": competitor_id, "is_deleted": {"$ne": True}}, {"$set": update})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Competitor not found")
    current = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    count = await db.competitor_products.count_documents({"competitor_id": competitor_id, "is_deleted": {"$ne": True}})
    return {"item": _serialize_competitor(current, count)}


@api_router.post("/admin/competitors/{competitor_id}/action/{action}")
async def admin_set_competitor_active(competitor_id: str, action: str, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    if action not in {"activate", "deactivate"}: raise HTTPException(status_code=400, detail="Invalid competitor action")
    update = {"is_active": action == "activate", "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    result = await db.competitors.update_one({"id": competitor_id, "is_deleted": {"$ne": True}}, {"$set": update})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Competitor not found")
    current = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    count = await db.competitor_products.count_documents({"competitor_id": competitor_id, "is_deleted": {"$ne": True}})
    return {"item": _serialize_competitor(current, count)}


@api_router.delete("/admin/competitors/{competitor_id}")
async def admin_delete_competitor(competitor_id: str, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.competitors.update_one({"id": competitor_id, "is_deleted": {"$ne": True}}, {"$set": {"is_deleted": True, "is_active": False, "updated_at": now, "updated_by": admin_user["user_id"]}})
    if not result.modified_count: raise HTTPException(status_code=404, detail="Competitor not found")
    await db.competitor_products.update_many({"competitor_id": competitor_id, "is_deleted": {"$ne": True}}, {"$set": {"is_deleted": True, "is_active": False, "updated_at": now, "updated_by": admin_user["user_id"]}})
    return {"ok": True}


@api_router.get("/admin/competitors/{competitor_id}/products")
async def admin_list_competitor_products(competitor_id: str, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    del admin_user
    if not await db.competitors.find_one({"id": competitor_id, "is_deleted": {"$ne": True}}): raise HTTPException(status_code=404, detail="Competitor not found")
    docs = await db.competitor_products.find({"competitor_id": competitor_id, "is_deleted": {"$ne": True}}, {"_id": 0}).sort("name", ASCENDING).to_list(length=500)
    return {"items": [_serialize_competitor_product(doc) for doc in docs]}


@api_router.post("/admin/competitors/{competitor_id}/products")
async def admin_create_competitor_product(competitor_id: str, payload: AdminCompetitorProductCreateRequest, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    if not await db.competitors.find_one({"id": competitor_id, "is_deleted": {"$ne": True}}): raise HTTPException(status_code=404, detail="Competitor not found")
    now = datetime.now(timezone.utc)
    document = {"id": str(uuid.uuid4()), "competitor_id": competitor_id, "name": payload.name.strip(), "is_type": payload.is_type.strip(), "en_type": payload.en_type.strip(), "competes_with": payload.competes_with.strip(), "is_active": payload.is_active, "is_deleted": False, "created_at": now, "updated_at": now, "created_by": admin_user["user_id"], "updated_by": admin_user["user_id"]}
    await db.competitor_products.insert_one(document)
    return {"item": _serialize_competitor_product(document)}


@api_router.put("/admin/competitors/{competitor_id}/products/{product_id}")
async def admin_update_competitor_product(competitor_id: str, product_id: str, payload: AdminCompetitorProductUpdateRequest, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    update = {"updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    for field in ("name", "is_type", "en_type", "competes_with", "is_active"):
        value = getattr(payload, field)
        if value is not None: update[field] = value.strip() if isinstance(value, str) else value
    result = await db.competitor_products.update_one({"id": product_id, "competitor_id": competitor_id, "is_deleted": {"$ne": True}}, {"$set": update})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Competitor product not found")
    current = await db.competitor_products.find_one({"id": product_id}, {"_id": 0})
    return {"item": _serialize_competitor_product(current)}


@api_router.delete("/admin/competitors/{competitor_id}/products/{product_id}")
async def admin_delete_competitor_product(competitor_id: str, product_id: str, admin_user: Dict[str, Any] = Depends(get_current_admin_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    update = {"is_deleted": True, "is_active": False, "updated_at": datetime.now(timezone.utc), "updated_by": admin_user["user_id"]}
    result = await db.competitor_products.update_one({"id": product_id, "competitor_id": competitor_id, "is_deleted": {"$ne": True}}, {"$set": update})
    if not result.modified_count: raise HTTPException(status_code=404, detail="Competitor product not found")
    return {"ok": True}

@api_router.post("/pitch")
async def generate_pitch(
    req: PitchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: AppSettings = Depends(get_settings_from_request),
):
    kam = await _get_kamdhenu_product_or_404(db, req.kamdhenu_code)
    pitches: List[Dict[str, Any]] = []

    competitors: List[Dict[str, Any]] = []
    for competitor_id in req.competitor_product_ids:
        competitor = await _resolve_competitor(db, competitor_id)
        if competitor:
            competitors.append(competitor)
    for index, custom_product in enumerate(req.custom_products):
        payload = custom_product.model_dump()
        competitors.append(
            {
                "id": f"custom::{index}::{payload.get('name', '')}",
                "brand": payload.get("brand", "Custom"),
                "name": payload.get("name", "Custom Product"),
                "is_type": payload.get("is_type", ""),
                "en_type": payload.get("en_type", ""),
                "params": enrich_competitor_params(payload),
            }
        )

    for competitor in competitors:
        cache_key = hashlib.md5(
            f"{kam['code']}|{competitor['brand']}|{competitor['name']}|{competitor['is_type']}|{competitor['en_type']}|v3|var{req.variant}".encode("utf-8")
        ).hexdigest()
        cached = await db.pitch_cache.find_one({"cache_key": cache_key}, {"_id": 0})
        if cached:
            pitches.append(
                {
                    "competitor_id": competitor["id"],
                    "competitor_brand": competitor["brand"],
                    "competitor_name": competitor["name"],
                    "lines": cached["lines"],
                }
            )
            continue

        kam_params_str = "\n".join([f"  - {key}: {value}" for key, value in kam["params"].items()])
        competitor_params_str = "\n".join([f"  - {key}: {value}" for key, value in competitor["params"].items()])
        variant_hints = [
            "",
            "ANGLE FOR THIS REQUEST: Focus on durability and longevity - freeze-thaw, heat aging, water immersion strength, and shelf life. Avoid repeating generic open-time or coverage talking points.",
            "ANGLE FOR THIS REQUEST: Focus on safety, environment, and worksite economics - VOC content, application temperature window, mixing ratio efficiency, coverage, and per-bag yield.",
            "ANGLE FOR THIS REQUEST: Focus on premium large-format or facade applications - slip resistance, deformability, shear adhesion under wet and heat conditions, and adjustability time.",
            "ANGLE FOR THIS REQUEST: Focus on the standards classification gap (IS 15477 / EN 12004) and what it means in real-world performance - superior bond, specifier-grade product, and lower callback risk.",
        ]
        variant_hint = variant_hints[req.variant % len(variant_hints)]
        prompt = f"""You are a senior B2B sales coach for Kamdhenu Adhesives (India). A sales rep is pitching a tile contractor, architect, or designer who is currently using a competitor product.

Generate EXACTLY 3 punchy one-line sales pitches (max 28 words each) for the rep to use. Each line must:
- Frame around a real-world tile adhesive problem.
- Use one specific parameter and exact number from the data to show how Kamdhenu prevents that problem versus the competitor.
- Use direct sales-floor language without markdown, bullets, or filler.
- Quantify the advantage when possible.

{variant_hint}

Output EXACTLY 3 lines separated by newlines. No preamble or numbering.

KAMDHENU PRODUCT: {kam['code']} - {kam['name']}
Type: {kam['is_type']} / {kam['en_type']}
Tagline: {kam['tagline']}
Technical Specs:
{kam_params_str}

COMPETITOR PRODUCT: {competitor['brand']} - {competitor['name']}
Type: {competitor['is_type']} / {competitor['en_type']}
Technical Specs:
{competitor_params_str}
"""
        try:
            text = await _generate_openai_text(
                settings,
                prompt,
                "You are a precise, persuasive B2B sales coach. Output exactly what is asked, nothing more.",
            )
            lines = [line.strip(" -*\t") for line in text.split("\n") if line.strip()]
            lines = lines[:3]
            if not lines:
                raise ValueError("Empty AI response")
            await db.pitch_cache.update_one(
                {"cache_key": cache_key},
                {
                    "$set": {
                        "cache_key": cache_key,
                        "kamdhenu_code": kam["code"],
                        "competitor_brand": competitor["brand"],
                        "competitor_name": competitor["name"],
                        "lines": lines,
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            pitches.append(
                {
                    "competitor_id": competitor["id"],
                    "competitor_brand": competitor["brand"],
                    "competitor_name": competitor["name"],
                    "lines": lines,
                }
            )
        except Exception as exc:
            logger.exception("Pitch generation failed for %s", competitor["name"])
            fallback_lines = [
                f"{kam['code']} ({kam['en_type']}) holds a stronger standards position than {competitor['brand']} {competitor['name']} ({competitor['en_type']}).",
                f"Kamdhenu open time {kam['params'].get('Open Time', 'N/A')} vs typical {competitor['params'].get('Open Time', 'N/A')} gives crews more working margin.",
                f"Kamdhenu coverage {kam['params'].get('Coverage', 'N/A')} improves material economy compared with {competitor['brand']}.",
            ]
            await db.pitch_cache.update_one(
                {"cache_key": cache_key},
                {
                    "$set": {
                        "cache_key": cache_key,
                        "kamdhenu_code": kam["code"],
                        "competitor_brand": competitor["brand"],
                        "competitor_name": competitor["name"],
                        "lines": fallback_lines,
                        "is_fallback": True,
                        "fallback_reason": str(exc),
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            pitches.append(
                {
                    "competitor_id": competitor["id"],
                    "competitor_brand": competitor["brand"],
                    "competitor_name": competitor["name"],
                    "lines": fallback_lines,
                }
            )

    return {"pitches": pitches}

@api_router.post("/recommendation-text")
async def generate_recommendation_text(
    req: RecommendationTextRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: AppSettings = Depends(get_settings_from_request),
):
    kam = await _get_kamdhenu_product_or_404(db, req.kamdhenu_code)

    competitors: List[Dict[str, Any]] = []
    for competitor_id in req.competitor_product_ids:
        competitor = await _resolve_competitor(db, competitor_id)
        if competitor:
            competitors.append(competitor)
    for custom_product in req.custom_products:
        payload = custom_product.model_dump()
        competitors.append(
            {
                "brand": payload.get("brand", "Custom"),
                "name": payload.get("name", "Custom Product"),
                "is_type": payload.get("is_type", ""),
                "en_type": payload.get("en_type", ""),
            }
        )

    context_payload = req.context.model_dump() if req.context else None
    cache_payload = f"{kam['code']}|" + "|".join(sorted([f"{item['brand']}::{item['name']}" for item in competitors])) + f"|ctx{context_payload}"
    cache_key = hashlib.md5(cache_payload.encode("utf-8")).hexdigest()
    cached = await db.recommendation_cache.find_one({"cache_key": cache_key}, {"_id": 0})
    if cached:
        return {"text": cached["text"], "cached": True}

    competitor_lines = "\n".join(
        [f"  - {item['brand']} {item['name']} ({item.get('is_type', '')} / {item.get('en_type', '')})" for item in competitors]
    ) or "  - (none)"
    context_line = ""
    if context_payload:
        context_line = (
            f"\nApplication context: substrate={context_payload.get('substrate', '-')}, "
            f"tile={context_payload.get('tile_type', '-')}, size={context_payload.get('size', '-')}, "
            f"area={context_payload.get('area', '-')}"
        )

    prompt = f"""Write a professional 3-paragraph technical recommendation letter that a Kamdhenu Adhesives sales representative will share with a tile contractor, architect, or interior designer.

Audience: a B2B customer considering competitor products. The tone must be confident, factual, and consultative, not salesy.

Requirements:
- Paragraph 1: summarize the recommendation (Kamdhenu {kam['code']}), the IS 15477 / EN 12004 classification, and why it suits the application.
- Paragraph 2: cite 3-4 exact spec advantages using numbers and connect them to installation outcomes.
- Paragraph 3: close with standards compliance, technical support, and an invitation for a site visit or demo. End with '- Kamdhenu Adhesives Technical Team'.
- 200-280 words total.
- Plain text only.
- Do not invent numbers.

KAMDHENU PRODUCT: {kam['code']} - {kam['name']}
Type: {kam['is_type']} / {kam['en_type']}
Tagline: {kam['tagline']}
Description: {kam.get('description', '')}
Key Specs:
  - Open Time: {kam['params'].get('Open Time', '-')}
  - Pot Life: {kam['params'].get('Pot Life', '-')}
  - Initial Tensile Adhesion: {kam['params'].get('Initial Tensile Adhesion (IS)', '-')}
  - Tensile after Water: {kam['params'].get('Tensile Adhesion after Water Immersion', '-')}
  - Tensile after Heat: {kam['params'].get('Tensile Adhesion after Heat Aging', '-')}
  - Tensile after Freeze-Thaw: {kam['params'].get('Tensile Adhesion after Freeze-Thaw', '-')}
  - Slip Resistance: {kam['params'].get('Slip Resistance', '-')}
  - Coverage: {kam['params'].get('Coverage', '-')}
  - VOC: {kam['params'].get('VOC Content', '-')}

COMPETITOR PRODUCTS BEING COMPARED:
{competitor_lines}
{context_line}
"""
    try:
        text = await _generate_openai_text(
            settings,
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
    except Exception as exc:
        logger.exception("Recommendation generation failed")
        competitor_names = ", ".join([f"{item['brand']} {item['name']}" for item in competitors]) or "the alternatives evaluated"
        text = (
            f"Following our technical evaluation of the application requirement, we recommend Kamdhenu {kam['code']} - {kam['name']}, "
            f"classified as {kam['is_type']} per IS 15477:2019 and {kam['en_type']} per EN 12004. "
            f"This classification is suited to the demands of the project.\n\n"
            f"Compared with {competitor_names}, Kamdhenu {kam['code']} offers measurable performance margins: open time of {kam['params'].get('Open Time', '-')}, "
            f"pot life of {kam['params'].get('Pot Life', '-')}, tensile bond strength after water immersion of {kam['params'].get('Tensile Adhesion after Water Immersion', '-')}, "
            f"and slip resistance of {kam['params'].get('Slip Resistance', '-')}. These values support longer installation life, lower callback risk in wet and exterior zones, "
            f"and more consistent execution for large-format or low-porosity tiles.\n\n"
            f"Kamdhenu {kam['code']} is aligned with Indian and international adhesive standards, backed by pan-India technical support and field application assistance. "
            f"We can also arrange a site visit or live product demonstration at your convenience.\n\n- Kamdhenu Adhesives Technical Team"
        )
        await db.recommendation_cache.update_one(
            {"cache_key": cache_key},
            {
                "$set": {
                    "cache_key": cache_key,
                    "text": text,
                    "is_fallback": True,
                    "fallback_reason": str(exc),
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        return {"text": text, "cached": False, "fallback": True}


@api_router.get("/competitor-tds/due")
async def list_due_competitor_tds(
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del user
    docs = await list_due_competitor_tds_docs(db)
    return {"products": docs, "count": len(docs), "checked_at": datetime.now(timezone.utc)}


@api_router.get("/competitor-tds/changed")
async def list_changed_competitor_tds(
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del user
    docs = await list_changed_competitor_tds_docs(db)
    return {"products": docs, "count": len(docs)}


@api_router.get("/competitor-tds/{competitor_id}/{product_name}")
async def get_competitor_tds(
    competitor_id: str,
    product_name: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del user
    try:
        return await get_competitor_tds_doc_or_raise(db, competitor_id, product_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Competitor product not found") from exc


@api_router.post("/competitor-tds/{competitor_id}/{product_name}/sync")
async def sync_competitor_tds(
    competitor_id: str,
    product_name: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    del user
    try:
        return await sync_competitor_tds_doc(db, competitor_id, product_name)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Competitor product not found") from exc


@api_router.patch("/competitor-tds/{competitor_id}/{product_name}/approve")
async def approve_competitor_tds(
    competitor_id: str,
    product_name: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        product = await approve_competitor_tds_report(db, competitor_id, product_name, user["user_id"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Competitor product not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "product": product}


@api_router.patch("/competitor-tds/{competitor_id}/{product_name}/reject")
async def reject_competitor_tds(
    competitor_id: str,
    product_name: str,
    user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        product = await reject_competitor_tds_report(db, competitor_id, product_name, user["user_id"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Competitor product not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "product": product}

@api_router.get("/health")
async def api_health(db: AsyncIOMotorDatabase = Depends(get_db)):
    await db.command("ping")
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


@api_router.get("/")
async def api_root():
    return {"app": APP_NAME, "version": APP_VERSION}


@app.get("/")
async def root():
    return {"app": APP_NAME, "version": APP_VERSION}


@app.get("/health")
async def health(db: AsyncIOMotorDatabase = Depends(get_db)):
    await db.command("ping")
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    settings = load_settings()
    uvicorn.run(
        "server:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.backend_reload,
    )


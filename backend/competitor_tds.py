from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional

from seed_data import (
    COMPETITORS,
    DEFAULT_TDS_UPDATE_FREQUENCY_DAYS,
    enrich_competitor_params,
)
from tds_sync import build_pending_report, fetch_tds_source, next_check_time, utcnow

COMPETITOR_TDS_COLLECTION = "competitor_tds"
COMPETITOR_TDS_RETRY_DAYS = 1
STATIC_COMPETITOR_BY_ID = {competitor["id"]: competitor for competitor in COMPETITORS}
STATIC_COMPETITOR_BY_NAME = {
    (competitor["id"], product["name"]): (competitor, index, product)
    for competitor in COMPETITORS
    for index, product in enumerate(competitor["products"])
}
_scheduler_task: Optional[asyncio.Task] = None


def build_seed_doc(competitor: Dict[str, Any], product: Dict[str, Any], index: int) -> Dict[str, Any]:
    now = utcnow()
    technical_report = product.get("technical_report") or enrich_competitor_params(product)
    next_check_at = now if product.get("tds_url") else None
    return {
        "product_id": f"{competitor['id']}::{index}",
        "product_index": index,
        "competitor_id": competitor["id"],
        "competitor_name": competitor["name"],
        "product_name": product["name"],
        "name": product["name"],
        "is_type": product.get("is_type", ""),
        "en_type": product.get("en_type", ""),
        "competes_with": product.get("competes_with", ""),
        "tds_url": product.get("tds_url", ""),
        "tds_file_hash": product.get("tds_file_hash", ""),
        "tds_text_hash": product.get("tds_text_hash", ""),
        "last_checked_at": product.get("last_checked_at"),
        "last_updated_at": product.get("last_updated_at"),
        "next_check_at": product.get("next_check_at") or next_check_at,
        "update_frequency_days": product.get("update_frequency_days", DEFAULT_TDS_UPDATE_FREQUENCY_DAYS),
        "report_status": product.get("report_status", "due"),
        "technical_report": technical_report,
        "pending_technical_report": product.get("pending_technical_report"),
        "tds_source_version": product.get("tds_source_version", "seed-v1"),
        "pending_tds_file_hash": "",
        "pending_tds_text_hash": "",
        "pending_tds_source_version": "",
        "last_error": None,
        "created_at": now,
        "updated_at": now,
    }


async def ensure_seeded(db) -> None:
    collection = db[COMPETITOR_TDS_COLLECTION]
    for competitor in COMPETITORS:
        for index, product in enumerate(competitor["products"]):
            seed_doc = build_seed_doc(competitor, product, index)
            existing = await collection.find_one(
                {"competitor_id": competitor["id"], "product_name": product["name"]},
                {"_id": 0},
            )
            if not existing:
                await collection.insert_one(seed_doc.copy())
                continue

            update_fields: Dict[str, Any] = {}
            for key in (
                "product_id",
                "product_index",
                "competitor_name",
                "name",
                "is_type",
                "en_type",
                "competes_with",
                "update_frequency_days",
            ):
                if existing.get(key) in (None, ""):
                    update_fields[key] = seed_doc[key]
            if not existing.get("technical_report"):
                update_fields["technical_report"] = seed_doc["technical_report"]
            if not existing.get("tds_source_version"):
                update_fields["tds_source_version"] = seed_doc["tds_source_version"]
            if existing.get("next_check_at") is None and existing.get("tds_url"):
                update_fields["next_check_at"] = next_check_time(existing.get("update_frequency_days", DEFAULT_TDS_UPDATE_FREQUENCY_DAYS))
            if update_fields:
                update_fields["updated_at"] = utcnow()
                await collection.update_one(
                    {"competitor_id": competitor["id"], "product_name": product["name"]},
                    {"$set": update_fields},
                )


async def list_docs(db) -> List[Dict[str, Any]]:
    await ensure_seeded(db)
    return await db[COMPETITOR_TDS_COLLECTION].find({}, {"_id": 0}).to_list(1000)


async def find_doc(db, competitor_id: str, product_name: str) -> Optional[Dict[str, Any]]:
    await ensure_seeded(db)
    doc = await db[COMPETITOR_TDS_COLLECTION].find_one(
        {"competitor_id": competitor_id, "product_name": product_name},
        {"_id": 0},
    )
    if doc:
        return doc

    static = STATIC_COMPETITOR_BY_NAME.get((competitor_id, product_name))
    if not static:
        return None
    competitor, index, product = static
    return build_seed_doc(competitor, product, index)


async def get_doc_or_raise(db, competitor_id: str, product_name: str) -> Dict[str, Any]:
    doc = await find_doc(db, competitor_id, product_name)
    if not doc:
        raise LookupError("Competitor product not found")
    return doc


async def resolve_competitor(db, cid: str) -> Optional[Dict[str, Any]]:
    try:
        competitor_id, index_str = cid.split("::")
        competitor = STATIC_COMPETITOR_BY_ID.get(competitor_id)
        if not competitor:
            return None
        index = int(index_str)
        product = competitor["products"][index]
        doc = await get_doc_or_raise(db, competitor_id, product["name"])
        params = doc.get("technical_report") or enrich_competitor_params(doc)
        return {
            "id": cid,
            "brand": competitor["name"],
            "name": product["name"],
            "is_type": doc.get("is_type", product.get("is_type", "")),
            "en_type": doc.get("en_type", product.get("en_type", "")),
            "params": params,
            "report_status": doc.get("report_status", "due"),
            "tds_url": doc.get("tds_url", ""),
            "technical_report": doc.get("technical_report"),
            "pending_technical_report": doc.get("pending_technical_report"),
        }
    except (LookupError, ValueError, IndexError):
        return None


async def sync_doc(db, competitor_id: str, product_name: str) -> Dict[str, Any]:
    collection = db[COMPETITOR_TDS_COLLECTION]
    doc = await get_doc_or_raise(db, competitor_id, product_name)
    now = utcnow()
    update_frequency_days = doc.get("update_frequency_days", DEFAULT_TDS_UPDATE_FREQUENCY_DAYS)

    try:
        fetch_result = await asyncio.to_thread(fetch_tds_source, doc.get("tds_url", ""))
    except Exception as exc:
        message = str(exc)
        await collection.update_one(
            {"competitor_id": competitor_id, "product_name": product_name},
            {
                "$set": {
                    "last_checked_at": now,
                    "report_status": "failed",
                    "next_check_at": now + timedelta(days=COMPETITOR_TDS_RETRY_DAYS),
                    "last_error": message,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        return {
            "ok": False,
            "status": "failed",
            "error": message,
            "product": await get_doc_or_raise(db, competitor_id, product_name),
        }

    if fetch_result.text_hash == (doc.get("tds_text_hash") or ""):
        await collection.update_one(
            {"competitor_id": competitor_id, "product_name": product_name},
            {
                "$set": {
                    "tds_file_hash": fetch_result.file_hash,
                    "last_checked_at": now,
                    "next_check_at": now + timedelta(days=update_frequency_days),
                    "report_status": "fresh",
                    "last_error": None,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        return {
            "ok": True,
            "status": "fresh",
            "changed": False,
            "product": await get_doc_or_raise(db, competitor_id, product_name),
        }

    pending_report = build_pending_report(fetch_result.raw_text, fetch_result.source_version)
    await collection.update_one(
        {"competitor_id": competitor_id, "product_name": product_name},
        {
            "$set": {
                "last_checked_at": now,
                "report_status": "pending_review",
                "pending_technical_report": pending_report,
                "pending_tds_file_hash": fetch_result.file_hash,
                "pending_tds_text_hash": fetch_result.text_hash,
                "pending_tds_source_version": fetch_result.source_version,
                "next_check_at": None,
                "last_error": None,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    return {
        "ok": True,
        "status": "pending_review",
        "changed": True,
        "product": await get_doc_or_raise(db, competitor_id, product_name),
    }


async def list_due_docs(db) -> List[Dict[str, Any]]:
    await ensure_seeded(db)
    return await db[COMPETITOR_TDS_COLLECTION].find(
        {"next_check_at": {"$lte": utcnow()}},
        {"_id": 0},
    ).to_list(1000)


async def list_changed_docs(db) -> List[Dict[str, Any]]:
    await ensure_seeded(db)
    return await db[COMPETITOR_TDS_COLLECTION].find(
        {"report_status": "pending_review"},
        {"_id": 0},
    ).to_list(1000)


async def approve_pending_report(db, competitor_id: str, product_name: str, user_id: str) -> Dict[str, Any]:
    doc = await get_doc_or_raise(db, competitor_id, product_name)
    pending_report = doc.get("pending_technical_report")
    if not pending_report:
        raise ValueError("No pending technical report to approve")

    pending_fields = pending_report.get("fields") or {}
    if not pending_fields:
        raise ValueError("Pending report has no extracted technical fields to approve")

    approved_report = (doc.get("technical_report") or {}).copy()
    approved_report.update(pending_fields)
    now = utcnow()
    await db[COMPETITOR_TDS_COLLECTION].update_one(
        {"competitor_id": competitor_id, "product_name": product_name},
        {
            "$set": {
                "technical_report": approved_report,
                "tds_file_hash": doc.get("pending_tds_file_hash", doc.get("tds_file_hash", "")),
                "tds_text_hash": doc.get("pending_tds_text_hash", doc.get("tds_text_hash", "")),
                "tds_source_version": doc.get("pending_tds_source_version") or pending_report.get("source_version") or doc.get("tds_source_version", "seed-v1"),
                "last_checked_at": now,
                "last_updated_at": now,
                "next_check_at": next_check_time(doc.get("update_frequency_days", DEFAULT_TDS_UPDATE_FREQUENCY_DAYS)),
                "report_status": "fresh",
                "pending_technical_report": None,
                "pending_tds_file_hash": "",
                "pending_tds_text_hash": "",
                "pending_tds_source_version": "",
                "last_error": None,
                "approved_by": user_id,
                "updated_at": now,
            }
        },
    )
    return await get_doc_or_raise(db, competitor_id, product_name)


async def reject_pending_report(db, competitor_id: str, product_name: str, user_id: str) -> Dict[str, Any]:
    doc = await get_doc_or_raise(db, competitor_id, product_name)
    if not doc.get("pending_technical_report"):
        raise ValueError("No pending technical report to reject")

    now = utcnow()
    await db[COMPETITOR_TDS_COLLECTION].update_one(
        {"competitor_id": competitor_id, "product_name": product_name},
        {
            "$set": {
                "pending_technical_report": None,
                "pending_tds_file_hash": "",
                "pending_tds_text_hash": "",
                "pending_tds_source_version": "",
                "report_status": "fresh" if doc.get("technical_report") else "due",
                "last_checked_at": now,
                "next_check_at": next_check_time(doc.get("update_frequency_days", DEFAULT_TDS_UPDATE_FREQUENCY_DAYS)),
                "rejected_by": user_id,
                "updated_at": now,
            }
        },
    )
    return await get_doc_or_raise(db, competitor_id, product_name)


async def run_due_syncs(db, logger) -> Dict[str, int]:
    docs = await list_due_docs(db)
    processed = 0
    changed = 0
    failed = 0
    for doc in docs:
        try:
            result = await sync_doc(db, doc["competitor_id"], doc["product_name"])
            processed += 1
            if result.get("status") == "pending_review":
                changed += 1
            if result.get("status") == "failed":
                failed += 1
        except Exception:
            failed += 1
            logger.exception("Unexpected TDS sync error for %s / %s", doc.get("competitor_id"), doc.get("product_name"))
    return {"processed": processed, "changed": changed, "failed": failed}


async def _scheduler_loop(db, logger) -> None:
    await asyncio.sleep(5)
    while True:
        try:
            summary = await run_due_syncs(db, logger)
            logger.info("TDS sync pass complete: %s", summary)
        except Exception:
            logger.exception("Daily TDS scheduler pass failed")
        await asyncio.sleep(24 * 60 * 60)


def start_scheduler(db, logger) -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop(db, logger))


async def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None

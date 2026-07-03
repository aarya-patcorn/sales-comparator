import asyncio
import unittest
from copy import deepcopy
from unittest.mock import patch

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from competitor_tds import (
    approve_pending_report,
    build_seed_doc,
    ensure_seeded,
    sync_doc,
)
from seed_data import COMPETITORS
from tds_sync import TdsFetchResult


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, _limit):
        return [deepcopy(doc) for doc in self._docs]


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return deepcopy(doc)
        return None

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                doc.update(deepcopy(update.get("$set", {})))
                return
        if upsert:
            new_doc = deepcopy(query)
            new_doc.update(deepcopy(update.get("$set", {})))
            self.docs.append(new_doc)

    def find(self, query, projection=None):
        results = []
        for doc in self.docs:
            match = True
            for key, value in query.items():
                if isinstance(value, dict) and "$lte" in value:
                    candidate = doc.get(key)
                    if candidate is None or candidate > value["$lte"]:
                        match = False
                        break
                elif doc.get(key) != value:
                    match = False
                    break
            if match:
                results.append(deepcopy(doc))
        return FakeCursor(results)


class FakeDb(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = FakeCollection()
        return dict.__getitem__(self, name)


class CompetitorTdsSyncTests(unittest.TestCase):
    def _seeded_product_doc(self):
        competitor = COMPETITORS[0]
        product = deepcopy(competitor["products"][0])
        product["tds_url"] = "https://example.com/tds.pdf"
        return competitor, product, build_seed_doc(competitor, product, 0)

    def test_sync_doc_creates_pending_review(self):
        db = FakeDb()
        competitor, product, doc = self._seeded_product_doc()
        doc["tds_text_hash"] = "old-hash"
        asyncio.run(db["competitor_tds"].insert_one(doc))

        def fake_fetch(_url):
            return TdsFetchResult(
                source_type="pdf",
                raw_text="Open Time: 42 minutes\nPackaging: 20 KG bag\nColor: Grey",
                text_hash="new-hash",
                file_hash="file-hash",
                content_type="application/pdf",
                source_version="pdf:new-hash",
            )

        with patch("competitor_tds.fetch_tds_source", fake_fetch):
            result = asyncio.run(sync_doc(db, competitor["id"], product["name"]))

        self.assertEqual(result["status"], "pending_review")
        updated = asyncio.run(db["competitor_tds"].find_one({"competitor_id": competitor["id"], "product_name": product["name"]}))
        self.assertEqual(updated["report_status"], "pending_review")
        self.assertEqual(updated["technical_report"], doc["technical_report"])
        self.assertEqual(updated["pending_technical_report"]["fields"]["Open Time"], "42 minutes")
        self.assertEqual(updated["pending_tds_text_hash"], "new-hash")

    def test_approve_promotes_pending_report(self):
        db = FakeDb()
        competitor, product, doc = self._seeded_product_doc()
        doc["pending_technical_report"] = {
            "fields": {"Open Time": "45 minutes", "Packaging": "25 KG bag"},
            "raw_text": "Open Time: 45 minutes",
            "source_version": "pdf:approved",
        }
        doc["pending_tds_file_hash"] = "next-file"
        doc["pending_tds_text_hash"] = "next-text"
        doc["pending_tds_source_version"] = "pdf:approved"
        asyncio.run(db["competitor_tds"].insert_one(doc))

        approved = asyncio.run(approve_pending_report(db, competitor["id"], product["name"], "admin_user"))

        self.assertEqual(approved["report_status"], "fresh")
        self.assertEqual(approved["technical_report"]["Open Time"], "45 minutes")
        self.assertEqual(approved["technical_report"]["Packaging"], "25 KG bag")
        self.assertEqual(approved["tds_text_hash"], "next-text")
        self.assertIsNone(approved["pending_technical_report"])

    def test_ensure_seeded_backfills_collection(self):
        db = FakeDb()
        asyncio.run(ensure_seeded(db))
        docs = asyncio.run(db["competitor_tds"].find({}, {"_id": 0}).to_list(1000))
        self.assertTrue(docs)
        self.assertTrue(all("report_status" in doc for doc in docs))
        self.assertTrue(all("technical_report" in doc for doc in docs))


if __name__ == "__main__":
    unittest.main()

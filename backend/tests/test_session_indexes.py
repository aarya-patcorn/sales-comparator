import asyncio
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


@dataclass
class FakeDeleteResult:
    deleted_count: int


class FakeCursor:
    def __init__(self, documents):
        self._documents = list(documents)

    async def to_list(self, length=None):
        if length is None:
            return list(self._documents)
        return list(self._documents)[:length]


class FakeUserSessionsCollection:
    def __init__(self, documents=None, indexes=None):
        self.name = "user_sessions"
        self.documents = list(documents or [])
        self.indexes = list(indexes or [{"name": "_id_", "key": {"_id": 1}}])
        self.dropped_indexes = []
        self.created_indexes = []
        self.inserted_documents = []

    async def insert_one(self, document):
        self.inserted_documents.append(dict(document))
        self.documents.append(dict(document))
        return SimpleNamespace(inserted_id=document.get("_id", "generated"))

    async def delete_many(self, filter_document):
        del filter_document
        retained = []
        deleted_count = 0
        for document in self.documents:
            token_hash = document.get("session_token_hash")
            if (
                "session_token_hash" not in document
                or token_hash is None
                or token_hash == ""
                or (isinstance(token_hash, str) and not token_hash.strip())
            ):
                deleted_count += 1
            else:
                retained.append(document)
        self.documents = retained
        return FakeDeleteResult(deleted_count=deleted_count)

    def aggregate(self, pipeline):
        del pipeline
        counts = {}
        for document in self.documents:
            token_hash = document.get("session_token_hash")
            if isinstance(token_hash, str) and token_hash > "":
                counts.setdefault(token_hash, []).append(document.get("_id"))
        duplicates = [
            {"_id": token_hash, "count": len(session_ids), "session_ids": session_ids}
            for token_hash, session_ids in counts.items()
            if len(session_ids) > 1
        ]
        return FakeCursor(duplicates)

    def list_indexes(self):
        return FakeCursor(self.indexes)

    async def drop_index(self, index_name):
        self.dropped_indexes.append(index_name)
        self.indexes = [index for index in self.indexes if index.get("name") != index_name]

    async def create_index(self, keys, **kwargs):
        key_document = {field: direction for field, direction in keys}
        index_document = {"name": kwargs.get("name"), "key": key_document}
        index_document.update({k: v for k, v in kwargs.items() if k != "background"})
        self.created_indexes.append(index_document)
        self.indexes = [index for index in self.indexes if index.get("name") != index_document["name"]]
        self.indexes.append(index_document)
        return index_document["name"]


class FakeDatabase:
    def __init__(self, user_sessions):
        self.user_sessions = user_sessions


def test_create_user_session_persists_non_empty_hash(monkeypatch):
    collection = FakeUserSessionsCollection()
    db = FakeDatabase(collection)
    monkeypatch.setattr(server.secrets, "token_urlsafe", lambda size: "deterministic-token")

    token = asyncio.run(server._create_user_session(db, "rm_demo", datetime.now(timezone.utc)))

    assert token == "rm_session_deterministic-token"
    assert len(collection.inserted_documents) == 1
    stored_hash = collection.inserted_documents[0]["session_token_hash"]
    assert stored_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert stored_hash.strip()


def test_ensure_user_session_indexes_cleans_invalid_docs_and_replaces_legacy_indexes_idempotently():
    collection = FakeUserSessionsCollection(
        documents=[
            {"_id": 1, "user_id": "a"},
            {"_id": 2, "user_id": "b", "session_token_hash": None},
            {"_id": 3, "user_id": "c", "session_token_hash": "   "},
            {"_id": 4, "user_id": "d", "session_token_hash": "valid_hash", "expires_at": datetime.now(timezone.utc)},
        ],
        indexes=[
            {"name": "_id_", "key": {"_id": 1}},
            {"name": "session_token_hash_1", "key": {"session_token_hash": 1}, "unique": True},
            {"name": "expires_at_1", "key": {"expires_at": 1}},
        ],
    )
    db = FakeDatabase(collection)

    asyncio.run(server.ensure_user_session_indexes(db))

    assert [document["_id"] for document in collection.documents] == [4]
    assert collection.dropped_indexes == ["session_token_hash_1", "expires_at_1"]
    assert len(collection.created_indexes) == 2

    token_indexes = [index for index in collection.indexes if index["key"] == {"session_token_hash": 1}]
    assert len(token_indexes) == 1
    assert token_indexes[0]["unique"] is True
    assert token_indexes[0]["partialFilterExpression"] == server._session_token_partial_filter()

    ttl_indexes = [index for index in collection.indexes if index["key"] == {"expires_at": 1}]
    assert len(ttl_indexes) == 1
    assert ttl_indexes[0]["expireAfterSeconds"] == 0

    created_before_second_run = len(collection.created_indexes)
    dropped_before_second_run = len(collection.dropped_indexes)
    asyncio.run(server.ensure_user_session_indexes(db))
    assert len(collection.created_indexes) == created_before_second_run
    assert len(collection.dropped_indexes) == dropped_before_second_run


def test_ensure_user_session_indexes_fails_on_duplicate_valid_hashes():
    duplicate_hash = "same_hash"
    collection = FakeUserSessionsCollection(
        documents=[
            {"_id": 1, "user_id": "a", "session_token_hash": duplicate_hash},
            {"_id": 2, "user_id": "b", "session_token_hash": duplicate_hash},
        ]
    )
    db = FakeDatabase(collection)

    with pytest.raises(RuntimeError, match="duplicate valid session_token_hash"):
        asyncio.run(server.ensure_user_session_indexes(db))

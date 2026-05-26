"""
Unit tests for VectorDBClient.
When QDRANT_URL / QDRANT_API_KEY are not set these tests run against
a local in-memory Qdrant instance (qdrant_client.QdrantClient(":memory:")).
"""
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from qdrant_client import QdrantClient as _QdrantClient
from qdrant_client.http import models as qdrant_models


def _make_in_memory_client(collection_name: str = "test-codebase", dim: int = 4):
    """Return a VectorDBClient backed by an in-memory Qdrant instance."""
    from services.vector_db import VectorDBClient

    real_client = _QdrantClient(":memory:")
    real_client.create_collection(
        collection_name=collection_name,
        vectors_config=qdrant_models.VectorParams(
            size=dim,
            distance=qdrant_models.Distance.COSINE,
        ),
    )

    vdb = VectorDBClient.__new__(VectorDBClient)
    vdb.client = real_client
    vdb.collection_name = collection_name
    vdb.dimension = dim
    vdb._available = True
    vdb._cloud_mode = False
    return vdb


SAMPLE_META = {
    "file_path": "src/auth.py",
    "start_line": 10,
    "end_line": 40,
    "language": "python",
    "function_name": "authenticate",
    "repo_name": "owner/repo",
    "code_snippet": "def authenticate(user, pwd): ...",
    "timestamp": "2026-01-01T00:00:00+00:00",
}

DIM = 4
VEC = [0.1, 0.2, 0.3, 0.4]


def test_upsert_single_chunk():
    vdb = _make_in_memory_client(dim=DIM)
    chunk_id = str(uuid.uuid4())
    result = vdb.upsert_chunk(chunk_id, VEC, SAMPLE_META)
    assert result is True


def test_upsert_batch_chunks():
    vdb = _make_in_memory_client(dim=DIM)
    batch = [(str(uuid.uuid4()), VEC, SAMPLE_META) for _ in range(50)]
    count = vdb.upsert_chunks_batch(batch)
    assert count == 50


def test_query_returns_results():
    vdb = _make_in_memory_client(dim=DIM)
    cid = str(uuid.uuid4())
    vdb.upsert_chunk(cid, VEC, SAMPLE_META)

    results = vdb.query(VEC, top_k=1)
    assert len(results) >= 1
    assert "id" in results[0]
    assert "score" in results[0]
    assert "metadata" in results[0]


def test_metadata_preserved_after_upsert():
    vdb = _make_in_memory_client(dim=DIM)
    cid = str(uuid.uuid4())
    vdb.upsert_chunk(cid, VEC, SAMPLE_META)

    results = vdb.query(VEC, top_k=1)
    assert len(results) == 1
    meta = results[0]["metadata"]
    assert meta["file_path"] == "src/auth.py"
    assert meta["language"] == "python"
    assert meta["start_line"] == 10


def test_collection_creation():
    from services.vector_db import VectorDBClient
    real_client = _QdrantClient(":memory:")

    vdb = VectorDBClient.__new__(VectorDBClient)
    vdb.client = real_client
    vdb.collection_name = "new-collection"
    vdb.dimension = DIM
    vdb._available = True
    vdb._cloud_mode = False

    result = vdb.create_collection_if_not_exists()
    assert result is True

    collections = [c.name for c in real_client.get_collections().collections]
    assert "new-collection" in collections


def test_collection_already_exists_no_error():
    vdb = _make_in_memory_client(dim=DIM)
    result = vdb.create_collection_if_not_exists()
    assert result is True


def test_unavailable_client_returns_safe_defaults():
    from services.vector_db import VectorDBClient
    vdb = VectorDBClient.__new__(VectorDBClient)
    vdb.client = None
    vdb.collection_name = "x"
    vdb.dimension = DIM
    vdb._available = False

    assert vdb.upsert_chunk("id", VEC, {}) is False
    assert vdb.upsert_chunks_batch([]) == 0
    assert vdb.query(VEC) == []
    assert vdb.get_collection_stats() == {"status": "unavailable"}


def test_get_collection_stats():
    vdb = _make_in_memory_client(dim=DIM)
    stats = vdb.get_collection_stats()
    assert stats["status"] == "ok"
    assert stats["dimension"] == DIM

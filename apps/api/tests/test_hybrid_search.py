"""
Unit tests for hybrid search, keyword index, and RRF ranking.
All tests run locally — no API key or Qdrant Cloud required.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import time
import pytest

from services.keyword_index import KeywordIndex
from services.embedding_cache import EmbeddingCache
from services.embeddings import EmbeddingGenerator
from services.hybrid_search import HybridSearch


SAMPLE_CHUNKS = [
    {
        "id": "chunk-auth-1",
        "content": "def authenticate(username, password): verify credentials and return token",
        "metadata": {
            "file_path": "src/auth.py",
            "start_line": 10,
            "end_line": 30,
            "language": "python",
            "function_name": "authenticate",
            "repo_name": "owner/repo",
            "code_snippet": "def authenticate(username, password):",
        },
    },
    {
        "id": "chunk-db-1",
        "content": "def connect_database(host, port): establish database connection pool",
        "metadata": {
            "file_path": "src/db.py",
            "start_line": 5,
            "end_line": 25,
            "language": "python",
            "function_name": "connect_database",
            "repo_name": "owner/repo",
            "code_snippet": "def connect_database(host, port):",
        },
    },
    {
        "id": "chunk-http-1",
        "content": "function fetchUserData(userId) { return http.get('/users/' + userId) }",
        "metadata": {
            "file_path": "src/api.js",
            "start_line": 1,
            "end_line": 10,
            "language": "javascript",
            "function_name": "fetchUserData",
            "repo_name": "owner/repo",
            "code_snippet": "function fetchUserData(userId)",
        },
    },
    {
        "id": "chunk-error-1",
        "content": "raise HTTPException status_code 503 service unavailable error handler",
        "metadata": {
            "file_path": "src/errors.py",
            "start_line": 50,
            "end_line": 60,
            "language": "python",
            "function_name": "handle_error",
            "repo_name": "owner/repo",
            "code_snippet": "raise HTTPException(status_code=503)",
        },
    },
]


def _build_keyword_index() -> KeywordIndex:
    idx = KeywordIndex()
    idx.add_chunks_batch(SAMPLE_CHUNKS)
    return idx


def _build_hybrid_search() -> HybridSearch:
    from unittest.mock import MagicMock
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
    from services.vector_db import VectorDBClient

    real_client = QdrantClient(":memory:")
    real_client.create_collection(
        collection_name="test",
        vectors_config=qdrant_models.VectorParams(size=384, distance=qdrant_models.Distance.COSINE),
    )

    vdb = VectorDBClient.__new__(VectorDBClient)
    vdb.client = real_client
    vdb.collection_name = "test"
    vdb.dimension = 384
    vdb._available = True
    vdb._cloud_mode = False

    gen = EmbeddingGenerator(api_key=None)
    idx = _build_keyword_index()

    for chunk in SAMPLE_CHUNKS:
        vec = gen.generate_embedding(chunk["content"])
        vdb.upsert_chunk(chunk["id"], vec, chunk["metadata"])

    return HybridSearch(vector_db=vdb, embedding_generator=gen, keyword_index=idx)


def test_keyword_search_finds_relevant_chunk():
    idx = _build_keyword_index()
    results = idx.search("authentication credentials")
    ids = [r["id"] for r in results]
    assert "chunk-auth-1" in ids


def test_keyword_search_finds_exact_term():
    idx = _build_keyword_index()
    results = idx.search("Error 503 service unavailable")
    assert len(results) > 0
    assert results[0]["id"] == "chunk-error-1"


def test_keyword_search_respects_language_filter():
    idx = _build_keyword_index()
    results = idx.search("connection", filters={"language": "python"})
    for r in results:
        assert r["metadata"]["language"] == "python"


def test_keyword_search_returns_empty_for_unknown_terms():
    idx = _build_keyword_index()
    results = idx.search("xyzzy_nonexistent_term_12345")
    assert results == []


def test_keyword_index_size():
    idx = _build_keyword_index()
    assert idx.size == len(SAMPLE_CHUNKS)


def test_keyword_index_clears():
    idx = _build_keyword_index()
    idx.clear()
    assert idx.size == 0
    assert idx.search("authenticate") == []


def test_rrf_ranking_correct():
    hs = _build_hybrid_search()

    semantic = [
        {"id": "a", "score": 0.9, "metadata": {}},
        {"id": "b", "score": 0.8, "metadata": {}},
        {"id": "c", "score": 0.7, "metadata": {}},
    ]
    keyword = [
        {"id": "b", "score": 0.9, "metadata": {}},
        {"id": "c", "score": 0.8, "metadata": {}},
        {"id": "d", "score": 0.7, "metadata": {}},
    ]
    merged = hs.reciprocal_rank_fusion(semantic, keyword, k=60)

    ids = [r["id"] for r in merged]
    assert "b" in ids
    assert "c" in ids
    b_idx = ids.index("b")
    a_idx = ids.index("a")
    assert b_idx < a_idx, "b should rank above a (appears in both lists)"


def test_rrf_duplicate_removal():
    hs = _build_hybrid_search()
    same = [{"id": "x", "score": 0.9, "metadata": {}}]
    merged = hs.reciprocal_rank_fusion(same, same, k=60)
    ids = [r["id"] for r in merged]
    assert ids.count("x") == 1


def test_semantic_search_returns_results():
    hs = _build_hybrid_search()
    results, embed_ms = hs.semantic_search("authenticate user login", top_k=3)
    assert len(results) <= 3
    assert embed_ms >= 0


def test_hybrid_search_returns_results():
    hs = _build_hybrid_search()
    merged, embed_ms, search_ms = hs.hybrid_search("authentication credentials", top_k=5)
    assert len(merged) > 0
    assert all("hybrid_score" in r for r in merged)
    assert all("semantic_score" in r for r in merged)
    assert all("keyword_score" in r for r in merged)


def test_hybrid_search_scores_are_floats():
    hs = _build_hybrid_search()
    results, _, _ = hs.hybrid_search("database connection", top_k=3)
    for r in results:
        assert isinstance(r["hybrid_score"], float)
        assert isinstance(r["semantic_score"], float)
        assert isinstance(r["keyword_score"], float)


def test_hybrid_combines_both_sources():
    hs = _build_hybrid_search()
    results, _, _ = hs.hybrid_search("authenticate database", top_k=10)
    ids = [r["id"] for r in results]
    assert "chunk-auth-1" in ids or "chunk-db-1" in ids


def test_search_latency_under_1_second():
    hs = _build_hybrid_search()
    t0 = time.monotonic()
    hs.hybrid_search("how does authentication work", top_k=10)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, f"Search took {elapsed:.2f}s, expected <1s"

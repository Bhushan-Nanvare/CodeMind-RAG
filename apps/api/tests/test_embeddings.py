"""
Unit tests for EmbeddingGenerator, EmbeddingCache, and hashing utilities.
All tests run locally — no API key required (mock mode used throughout).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest

from services.embeddings import EmbeddingGenerator, _mock_embed
from services.embedding_cache import EmbeddingCache
from utils.hashing import hash_text

DIM = 384


def _gen(api_key=None) -> EmbeddingGenerator:
    return EmbeddingGenerator(api_key=api_key)


def test_embedding_dimension_is_384():
    gen = _gen()
    vec = gen.generate_embedding("def hello(): pass")
    assert len(vec) == DIM


def test_embedding_is_unit_normalised():
    gen = _gen()
    vec = gen.generate_embedding("class Foo: pass")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-5


def test_different_texts_different_vectors():
    gen = _gen()
    v1 = gen.generate_embedding("def add(a, b): return a + b")
    v2 = gen.generate_embedding("class Database: pass")
    assert v1 != v2


def test_same_text_same_vector_deterministic():
    text = "def authenticate(user, pwd): ..."
    gen = _gen()
    v1 = gen.generate_embedding(text)
    v2 = gen.generate_embedding(text)
    assert v1 == v2


def test_batch_embeddings_same_as_individual():
    gen = _gen()
    texts = [
        "import os",
        "def foo(): return 42",
        "class Bar: pass",
    ]
    batch_vecs = gen.generate_embeddings_batch(texts)
    assert len(batch_vecs) == 3
    for text, bvec in zip(texts, batch_vecs):
        ind_vec = gen.generate_embedding(text)
        assert bvec == ind_vec


def test_batch_dimension_is_384():
    gen = _gen()
    texts = [f"chunk number {i}" for i in range(20)]
    vecs = gen.generate_embeddings_batch(texts)
    assert len(vecs) == 20
    assert all(len(v) == DIM for v in vecs)


def test_cache_hit_rate_improves():
    gen = _gen()
    text = "x = 1 + 2"
    gen.generate_embedding(text)
    gen.generate_embedding(text)
    stats = gen.cache_stats()
    assert stats["hits"] >= 1
    assert stats["hit_rate"] > 0.0


def test_cache_stores_and_retrieves():
    cache = EmbeddingCache()
    vector = [0.1, 0.2, 0.3]
    th = hash_text("test text")
    cache.set(th, vector)
    result = cache.get(th)
    assert result == vector


def test_cache_miss_returns_none():
    cache = EmbeddingCache()
    result = cache.get("nonexistent_hash")
    assert result is None


def test_cache_stats_tracks_hits_and_misses():
    cache = EmbeddingCache()
    th = hash_text("hello world")
    cache.get(th)
    cache.set(th, [1.0])
    cache.get(th)
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5
    assert stats["size"] == 1


def test_cache_evicts_when_full():
    cache = EmbeddingCache(max_size=3)
    for i in range(4):
        cache.set(f"hash_{i}", [float(i)])
    assert len(cache._cache) == 3


def test_hash_text_consistent():
    t = "import numpy as np"
    assert hash_text(t) == hash_text(t)
    assert len(hash_text(t)) == 64


def test_hash_text_different_texts():
    assert hash_text("foo") != hash_text("bar")


def test_mock_embed_is_unit_normalised():
    vec = _mock_embed("print('hello')")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-5


def test_embedding_mode_is_local_mock_without_key():
    gen = _gen(api_key=None)
    assert gen.mode == "local_mock"


def test_embedding_mode_is_api_with_key():
    gen = _gen(api_key="hf_fake_key_for_testing")
    assert gen.mode == "huggingface_api"

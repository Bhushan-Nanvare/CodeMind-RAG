"""
Edge-case tests for HuggingFace endpoint fallbacks and error handling.

No network calls are made; httpx.post is monkeypatched.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class _Resp:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        import httpx

        if self.status_code >= 400:
            req = httpx.Request("POST", "https://example.com")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("bad", request=req, response=resp)

    def json(self):
        return self._payload


def test_hf_single_uses_router_endpoint_first_then_fallback(monkeypatch):
    from services.embeddings import EmbeddingGenerator

    calls = []

    def fake_post(url, *args, **kwargs):
        calls.append(url)
        # router endpoint returns 404, legacy returns ok with a single vector
        if "router.huggingface.co" in url:
            return _Resp(404, {"error": "not found"})
        return _Resp(200, [0.0] * 384)

    monkeypatch.setattr("services.embeddings.httpx.post", fake_post)

    gen = EmbeddingGenerator(api_key="hf_test_key")
    vec = gen.generate_embedding("hello")
    assert len(vec) == 384
    assert any("router.huggingface.co" in u for u in calls)
    assert any("api-inference.huggingface.co" in u for u in calls)


def test_hf_single_returns_mock_on_all_404(monkeypatch):
    from services.embeddings import EmbeddingGenerator

    def fake_post(url, *args, **kwargs):
        return _Resp(404, {"error": "not found"})

    monkeypatch.setattr("services.embeddings.httpx.post", fake_post)
    gen = EmbeddingGenerator(api_key="hf_test_key")
    vec = gen.generate_embedding("hello")
    assert len(vec) == 384


def test_hf_single_raises_on_401(monkeypatch):
    from services.embeddings import EmbeddingGenerator

    def fake_post(url, *args, **kwargs):
        return _Resp(401, {"error": "unauthorized"})

    monkeypatch.setattr("services.embeddings.httpx.post", fake_post)
    gen = EmbeddingGenerator(api_key="hf_test_key")
    with pytest.raises(RuntimeError, match="Invalid HuggingFace API key"):
        gen.generate_embedding("hello")


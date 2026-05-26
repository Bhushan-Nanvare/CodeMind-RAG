"""Embedding generation via HuggingFace Inference API, with a local mock fallback.

Without a key, falls back to a deterministic SHA-256-derived 384-dim vector so the
pipeline runs end-to-end with no credentials. The mock isn't semantically meaningful.
"""

import hashlib
import math
import time

import httpx

from services.embedding_cache import EmbeddingCache
from utils.hashing import hash_text
from utils.logger import get_logger

logger = get_logger(__name__)

_MOCK_DIM = 384
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0


def _mock_embed(text: str) -> list[float]:
    # Integer arithmetic on the hash bytes avoids NaN/Inf from float parsing.
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    floats = []
    for i in range(_MOCK_DIM):
        h = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        floats.append(int.from_bytes(h[:4], "big") / (2**32 - 1) * 2.0 - 1.0)

    norm = math.sqrt(sum(x * x for x in floats)) or 1.0
    return [x / norm for x in floats]


class EmbeddingGenerator:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache: EmbeddingCache | None = None,
    ):
        self._api_key = api_key
        self._model_name = model_name
        self._use_api = bool(api_key)
        self._cache = cache or EmbeddingCache()
        self._total_api_calls = 0
        # HF moved serverless inference behind router.huggingface.co; keep the
        # old endpoint as a fallback for accounts not yet migrated.
        self._hf_api_urls = [
            "https://router.huggingface.co/hf-inference/models/"
            f"{self._model_name}/pipeline/feature-extraction",
            "https://api-inference.huggingface.co/pipeline/feature-extraction/"
            f"{self._model_name}",
        ]
        logger.info("embedding_mode", mode=self.mode, model=model_name)

    @property
    def mode(self) -> str:
        return "huggingface_api" if self._use_api else "local_mock"

    def cache_stats(self) -> dict:
        stats = self._cache.stats()
        stats["total_api_calls"] = self._total_api_calls
        stats["mode"] = self.mode
        return stats

    def cache_get(self, text_hash: str) -> list[float] | None:
        return self._cache.get(text_hash)

    def cache_set(self, text_hash: str, vector: list[float]) -> None:
        self._cache.set(text_hash, vector)

    def generate_embedding(self, text: str) -> list[float]:
        th = hash_text(text)
        cached = self._cache.get(th)
        if cached is not None:
            return cached

        vector = self._hf_single(text) if self._use_api else _mock_embed(text)
        self._cache.set(th, vector)
        return vector

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        hashes = [hash_text(t) for t in texts]
        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []

        for i, th in enumerate(hashes):
            hit = self._cache.get(th)
            if hit is not None:
                results[i] = hit
            else:
                uncached_indices.append(i)

        if uncached_indices:
            batch_texts = [texts[i] for i in uncached_indices]
            if self._use_api:
                batch_vectors = self._hf_batch(batch_texts)
            else:
                batch_vectors = [_mock_embed(t) for t in batch_texts]

            for idx, vec in zip(uncached_indices, batch_vectors):
                self._cache.set(hashes[idx], vec)
                results[idx] = vec

        logger.info(
            "batch_embeddings_generated",
            total=len(texts),
            cache_hits=len(texts) - len(uncached_indices),
            api_calls=len(uncached_indices) if self._use_api else 0,
        )
        return results  # type: ignore[return-value]

    def _hf_single(self, text: str) -> list[float]:
        self._total_api_calls += 1
        headers = {"Authorization": f"Bearer {self._api_key}"}
        delay = _RETRY_BASE_DELAY

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                last_status: int | None = None
                for url in self._hf_api_urls:
                    resp = httpx.post(
                        url,
                        json={"inputs": text},
                        headers=headers,
                        timeout=30.0,
                    )
                    last_status = resp.status_code
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return self._parse_hf_response(data)
                logger.error("hf_api_error", status=last_status or 404)
                return _mock_embed(text)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == _MAX_RETRIES:
                    logger.warning("hf_api_retries_exhausted", error=str(exc))
                    return _mock_embed(text)
                logger.warning(
                    "hf_api_retry",
                    attempt=attempt,
                    delay=delay,
                    error=str(exc),
                )
                time.sleep(delay)
                delay *= 2
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise RuntimeError("Invalid HuggingFace API key") from exc
                logger.error("hf_api_error", status=exc.response.status_code)
                return _mock_embed(text)

        return _mock_embed(text)

    def _hf_batch(self, texts: list[str]) -> list[list[float]]:
        self._total_api_calls += 1
        headers = {"Authorization": f"Bearer {self._api_key}"}
        batch_size = 16
        all_vectors: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            delay = _RETRY_BASE_DELAY
            success = False

            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    resp = None
                    last_status: int | None = None
                    for url in self._hf_api_urls:
                        resp = httpx.post(
                            url,
                            json={"inputs": batch},
                            headers=headers,
                            timeout=60.0,
                        )
                        last_status = resp.status_code
                        if resp.status_code == 404:
                            continue
                        resp.raise_for_status()
                        break
                    if resp is None or (last_status == 404):
                        logger.error("hf_api_error", status=last_status or 404)
                        break

                    data = resp.json()
                    if isinstance(data, list) and isinstance(data[0], list):
                        all_vectors.extend(data)
                    else:
                        all_vectors.append(self._parse_hf_response(data))
                    success = True
                    break
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == _MAX_RETRIES:
                        break
                    time.sleep(delay)
                    delay *= 2
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 401:
                        raise RuntimeError("Invalid HuggingFace API key") from exc
                    break

            if not success:
                all_vectors.extend([_mock_embed(t) for t in batch])

        return all_vectors

    @staticmethod
    def _parse_hf_response(data) -> list[float]:
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                return data[0]
            return data
        raise ValueError(f"Unexpected HF API response format: {type(data)}")

"""Hybrid retrieval + Groq chat completion, with mock answer if no API key."""
from __future__ import annotations

import time
from typing import Any

import httpx

from config import Settings
from services.hybrid_search import HybridSearch
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a code assistant. Answer using ONLY the provided code context.
Cite concrete paths and line ranges like `path/to/file.ext` (lines START-END).
If the context does not contain the answer, say you cannot find it in the indexed code."""

_MAX_CONTEXT_CHARS = 12000


def _build_context(
    merged: list[dict[str, Any]], max_chars: int = _MAX_CONTEXT_CHARS
) -> tuple[str, list[dict[str, Any]]]:
    parts: list[str] = []
    sources: list[dict[str, Any]] = []
    used = 0
    for item in merged:
        meta = item.get("metadata") or {}
        fp = meta.get("file_path", "unknown")
        sl = int(meta.get("start_line", 0))
        el = int(meta.get("end_line", 0))
        content = meta.get("content") or ""
        block = f"--- File: {fp} (lines {sl}-{el}) ---\n{content}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
        snippet = content[:500] + ("..." if len(content) > 500 else "")
        sources.append(
            {
                "file_path": fp,
                "start_line": sl,
                "end_line": el,
                "language": meta.get("language", "unknown"),
                "function_name": meta.get("function_name"),
                "snippet": snippet,
                "rrf_score": float(item.get("hybrid_score", 0.0)),
            }
        )
    return "\n\n".join(parts), sources


def _mock_answer(question: str, sources: list[dict[str, Any]]) -> str:
    if not sources:
        return (
            "No relevant code was retrieved for this repository. "
            "Ensure ingestion completed successfully."
        )
    top = sources[0]
    return (
        f"Retrieval-only mode (no GROQ_API_KEY): the strongest match is "
        f"`{top['file_path']}` (lines {top['start_line']}-{top['end_line']}). "
        f"Add a Groq API key in `apps/api/.env` for full natural-language answers."
    )


async def _groq_complete(question: str, context: str, settings: Settings) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.GROQ_MODEL,
                "temperature": 0.3,
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Context:\n{context}\n\nQuestion: {question}",
                    },
                ],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


async def answer_question(
    question: str,
    repo_name: str,
    hybrid_search: HybridSearch,
    settings: Settings,
    top_k: int = 10,
) -> tuple[str, list[dict[str, Any]], float, int]:
    t0 = time.monotonic()
    merged, _embed_ms, _search_ms = hybrid_search.hybrid_search(
        question, top_k=top_k, filters={"repo_name": repo_name}
    )
    if not merged:
        return (
            "No indexed chunks found for this repository. Run ingestion first.",
            [],
            0.0,
            int((time.monotonic() - t0) * 1000),
        )

    context, sources = _build_context(merged)
    scores = [float(m.get("hybrid_score", 0.0)) for m in merged[: len(sources)]]
    confidence = sum(scores) / max(len(scores), 1)
    confidence_score = min(1.0, confidence * 2.5)

    answer_text: str
    groq_key = (settings.GROQ_API_KEY or "").strip()
    if groq_key and not groq_key.startswith("your-"):
        try:
            answer_text = await _groq_complete(question, context, settings)
        except Exception as exc:
            logger.warning("groq_answer_failed", error=str(exc))
            answer_text = _mock_answer(question, sources)
    else:
        answer_text = _mock_answer(question, sources)

    query_time_ms = int((time.monotonic() - t0) * 1000)
    return answer_text, sources, confidence_score, query_time_ms

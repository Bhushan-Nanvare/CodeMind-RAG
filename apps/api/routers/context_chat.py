from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config import settings
from services.packer import CodePacker, PackResult, get_cached_pack, set_cached_pack
from services.repo_cloner import RepoCloner
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v2", tags=["context-chat"])

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.1-70b-versatile"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0

_cloner = RepoCloner()
_packer = CodePacker()


class ContextChatRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repo URL")
    question: str = Field(..., description="Question about the codebase")
    branch: str = Field(default="main")
    repo_name: str | None = Field(default=None)
    format: str = Field(default="xml", description="xml | markdown | plain")
    force_repack: bool = Field(default=False)


class ContextChatResponse(BaseModel):
    question: str
    answer: str
    repo_name: str
    total_files_packed: int
    total_tokens_sent: int
    truncated: bool
    dropped_files: int
    cache_hit: bool
    query_time_ms: float


def _derive_repo_name(repo_url: str) -> str:
    parts = repo_url.rstrip("/").split("/")
    return f"{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else parts[-1]


def _build_prompt(pack: PackResult, question: str) -> str:
    truncation_note = (
        f"\nNote: {pack.dropped_files} file(s) were omitted due to token budget."
        if pack.truncated else ""
    )
    return f"""You are an expert software engineer performing a deep code review.
You have been given the complete source code of '{pack.repo_name}' ({pack.total_files} files).{truncation_note}

Answer with precise file paths, function names, and quoted code snippets from the repository.
Do NOT invent code or paths that do not exist in the provided source.

--- REPOSITORY SOURCE CODE ---
{pack.content}
--- END ---

Question: {question}"""


def _call_groq(prompt: str) -> str:
    if not settings.GROQ_API_KEY:
        return "_Groq API key not configured._"

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    delay = _RETRY_BASE_DELAY
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = httpx.post(_GROQ_API_URL, json=payload, headers=headers, timeout=120.0)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt == _MAX_RETRIES:
                raise RuntimeError(f"Groq unreachable after {_MAX_RETRIES} retries: {exc}") from exc
            logger.warning("context_chat_groq_retry", attempt=attempt, delay=delay)
            time.sleep(delay)
            delay *= 2
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 413:
                raise RuntimeError(
                    "Packed repo exceeds Groq request size limit. Try a smaller repo or use RAG mode."
                ) from exc
            raise RuntimeError(f"Groq API error {exc.response.status_code}: {exc.response.text[:300]}") from exc

    raise RuntimeError("Groq call exhausted all retries.")


def _clone_and_pack(repo_url: str, branch: str, repo_name: str, fmt: str) -> tuple[PackResult, str]:
    temp_dir = str(Path(settings.TEMP_DIR) / f"pack-{uuid.uuid4()}")
    try:
        cloned_path = _cloner.clone_repo(repo_url, branch, temp_dir)
        pack = _packer.pack(cloned_path, repo_name, fmt=fmt)
        return pack, temp_dir
    except Exception:
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@router.post("/context-chat", response_model=ContextChatResponse)
async def context_chat(body: ContextChatRequest) -> ContextChatResponse:
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="question cannot be empty")
    if not body.repo_url.strip():
        raise HTTPException(status_code=422, detail="repo_url cannot be empty")
    if body.format not in ("xml", "markdown", "plain"):
        raise HTTPException(status_code=422, detail="format must be xml, markdown, or plain")

    t0 = time.time()
    repo_name = body.repo_name or _derive_repo_name(body.repo_url)
    cache_hit = False
    temp_dir: str | None = None
    pack: PackResult | None = None

    if not body.force_repack:
        pack = get_cached_pack(repo_name)
        if pack:
            cache_hit = True

    if pack is None:
        logger.info("context_chat_cloning", repo=repo_name, url=body.repo_url)
        try:
            pack, temp_dir = _clone_and_pack(body.repo_url, body.branch, repo_name, body.format)
            set_cached_pack(repo_name, pack)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (PermissionError, ConnectionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("context_chat_pack_failed", error=str(exc))
            raise HTTPException(status_code=500, detail=f"Pack failed: {exc}") from exc
        finally:
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    prompt = _build_prompt(pack, body.question)
    logger.info("context_chat_groq_call", repo=repo_name, tokens=pack.total_tokens, cache_hit=cache_hit)

    try:
        answer = _call_groq(prompt)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    query_time_ms = round((time.time() - t0) * 1000, 2)
    logger.info("context_chat_complete", repo=repo_name, time_ms=query_time_ms)

    return ContextChatResponse(
        question=body.question,
        answer=answer,
        repo_name=repo_name,
        total_files_packed=pack.total_files,
        total_tokens_sent=pack.total_tokens,
        truncated=pack.truncated,
        dropped_files=pack.dropped_files,
        cache_hit=cache_hit,
        query_time_ms=query_time_ms,
    )

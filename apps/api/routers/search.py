from fastapi import APIRouter, HTTPException

from models.search_schemas import (
    HybridSearchResponse,
    SearchQuery,
    SearchResult,
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

_hybrid_search_ref = None


def set_hybrid_search(hs):
    global _hybrid_search_ref
    _hybrid_search_ref = hs


@router.post("/search", response_model=HybridSearchResponse)
async def search(request: SearchQuery) -> HybridSearchResponse:
    logger.info(
        "search_request",
        query=request.query[:80],
        top_k=request.top_k,
        filters=request.filters,
        repo_name=request.repo_name,
    )

    hs = _hybrid_search_ref
    if hs is None:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    filters = {}
    if request.repo_name:
        filters["repo_name"] = request.repo_name
    if request.filters:
        filters.update(request.filters)
    if not filters:
        filters = None

    try:
        merged, embed_ms, search_ms = hs.hybrid_search(
            query=request.query,
            top_k=request.top_k,
            filters=filters,
        )
    except Exception as exc:
        logger.error("search_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    results = []
    for rank, item in enumerate(merged, 1):
        meta = item.get("metadata") or {}
        results.append(
            SearchResult(
                id=item["id"],
                file_path=meta.get("file_path", "unknown"),
                start_line=meta.get("start_line", 0),
                end_line=meta.get("end_line", 0),
                language=meta.get("language", "unknown"),
                function_name=meta.get("function_name"),
                code_snippet=meta.get("code_snippet", meta.get("content", "")[:200]),
                content=meta.get("content", ""),
                repo_name=meta.get("repo_name"),
                semantic_score=round(item.get("semantic_score", 0.0), 6),
                keyword_score=round(item.get("keyword_score", 0.0), 6),
                hybrid_score=round(item.get("hybrid_score", 0.0), 6),
                rank=rank,
            )
        )

    logger.info(
        "search_response",
        returned=len(results),
        embed_ms=embed_ms,
        search_ms=search_ms,
    )

    return HybridSearchResponse(
        query=request.query,
        results=results,
        total_results=len(results),
        query_embedding_time_ms=embed_ms,
        search_time_ms=search_ms,
    )


@router.get("/search/repos")
async def list_indexed_repos():
    from services.ingestion import INDEXED_REPOS
    return {
        "repos": [
            {
                "repo_name": ctx.repo_name,
                "repo_url": ctx.repo_url,
                "languages": ctx.languages,
                "file_count": ctx.file_count,
                "chunk_count": ctx.chunk_count,
                "indexed_at": ctx.indexed_at,
            }
            for ctx in INDEXED_REPOS.values()
        ]
    }

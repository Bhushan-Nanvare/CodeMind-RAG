from fastapi import APIRouter, HTTPException

from config import settings
from models.rag_schemas import QueryRequestBody, QueryResponseBody, SourceChunk
from services.rag_answer import answer_question
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["query"])

_hybrid_search_ref = None


def set_hybrid_search(hs):
    global _hybrid_search_ref
    _hybrid_search_ref = hs


@router.post("/query", response_model=QueryResponseBody)
async def query_codebase(body: QueryRequestBody) -> QueryResponseBody:
    hs = _hybrid_search_ref
    if hs is None:
        raise HTTPException(status_code=503, detail="Search service not initialized")

    top_k = body.top_k if body.top_k > 0 else 10
    try:
        answer, sources_raw, confidence, query_time_ms = await answer_question(
            body.question,
            body.repo_name,
            hs,
            settings,
            top_k=top_k,
        )
    except Exception as exc:
        logger.error("query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    sources = [
        SourceChunk(
            file_path=s["file_path"],
            start_line=s["start_line"],
            end_line=s["end_line"],
            language=s["language"],
            snippet=s["snippet"],
            rrf_score=s["rrf_score"],
            function_name=s.get("function_name"),
        )
        for s in sources_raw
    ]

    return QueryResponseBody(
        question=body.question,
        answer=answer,
        sources=sources,
        confidence_score=confidence,
        query_time_ms=query_time_ms,
    )

import time
from datetime import datetime, timezone

from fastapi import APIRouter

from config import settings
from models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])

_start_time = time.monotonic()

_vector_db_ref = None
_embedding_generator_ref = None


def set_vector_db(vdb):
    global _vector_db_ref
    _vector_db_ref = vdb


def set_embedding_generator(eg):
    global _embedding_generator_ref
    _embedding_generator_ref = eg


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    if _vector_db_ref is None:
        qdrant_status = "not_configured"
    elif not _vector_db_ref.available:
        qdrant_status = "disconnected"
    elif _vector_db_ref.storage_mode == "cloud":
        qdrant_status = "connected"
    else:
        qdrant_status = "in-memory"

    if _embedding_generator_ref is None:
        hf_status = "not_configured"
    elif _embedding_generator_ref.mode == "huggingface_api":
        hf_status = "connected"
    else:
        hf_status = "local-mock"

    groq_key = (settings.GROQ_API_KEY or "").strip()
    if groq_key and not groq_key.lower().startswith("your-"):
        groq_status = "configured"
    else:
        groq_status = "not_configured"

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={
            "qdrant": qdrant_status,
            "groq": groq_status,
            "huggingface": hf_status,
        },
        uptime_seconds=round(time.monotonic() - _start_time, 2),
    )

from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.schemas import IngestRequest, IngestResponse, IngestionStatus
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["ingest"])

_ingestion_service_ref = None


def set_ingestion_service(svc):
    global _ingestion_service_ref
    _ingestion_service_ref = svc


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_repo(
    request: IngestRequest, background_tasks: BackgroundTasks
) -> IngestResponse:
    logger.info(
        "ingest_request_received",
        repo_url=request.repo_url,
        branch=request.branch,
    )

    svc = _ingestion_service_ref
    if svc is None:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    job_id = svc.ingest_repo(request.repo_url, request.branch)

    return IngestResponse(
        status="processing",
        job_id=job_id,
        message=(
            f"Ingestion started for {request.repo_url}. "
            f"Poll /api/ingest/status/{job_id} for progress."
        ),
    )


@router.get("/ingest/status/{job_id}", response_model=IngestionStatus)
async def get_ingestion_status(job_id: str) -> IngestionStatus:
    svc = _ingestion_service_ref
    if svc is None:
        raise HTTPException(status_code=503, detail="Ingestion service not initialized")

    status = svc.get_status(job_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id!r} not found.",
        )
    return status

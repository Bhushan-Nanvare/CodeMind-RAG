import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from utils.logger import setup_logging, get_logger
from routers import health as health_router
from routers import ingest as ingest_router
from routers import query
from routers import search as search_router
from routers import context_chat as context_chat_router

setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="CodeMind RAG API",
    version="0.4.0",
    description="Intelligent Codebase Search — Phase 6: Hybrid Search",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(ingest_router.router)
app.include_router(search_router.router)
app.include_router(query.router)
app.include_router(context_chat_router.router)


@app.on_event("startup")
async def startup() -> None:
    logger.info("codemind_rag_api_starting", version="0.4.0")

    from services.vector_db import VectorDBClient
    vector_db = VectorDBClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        dimension=settings.VECTOR_DIMENSION,
    )
    if vector_db.available:
        vector_db.create_collection_if_not_exists()
        vector_db.ensure_payload_indexes()

    from services.embedding_cache import EmbeddingCache
    from services.embeddings import EmbeddingGenerator
    cache = EmbeddingCache(max_size=settings.EMBEDDING_CACHE_SIZE)
    embedding_generator = EmbeddingGenerator(
        api_key=settings.HUGGINGFACE_API_KEY,
        model_name=settings.EMBEDDING_MODEL,
        cache=cache,
    )

    from services.keyword_index import KeywordIndex
    keyword_index = KeywordIndex()

    from services.ingestion import IngestionService
    svc = IngestionService(
        vector_db=vector_db,
        embedding_generator=embedding_generator,
        keyword_index=keyword_index,
    )

    from services.hybrid_search import HybridSearch
    hybrid_search = HybridSearch(
        vector_db=vector_db,
        embedding_generator=embedding_generator,
        keyword_index=keyword_index,
    )

    health_router.set_vector_db(vector_db)
    health_router.set_embedding_generator(embedding_generator)
    ingest_router.set_ingestion_service(svc)
    search_router.set_hybrid_search(hybrid_search)
    query.set_hybrid_search(hybrid_search)

    logger.info(
        "startup_complete",
        qdrant=vector_db.storage_mode,
        embeddings=embedding_generator.mode,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("codemind_rag_api_shutting_down")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

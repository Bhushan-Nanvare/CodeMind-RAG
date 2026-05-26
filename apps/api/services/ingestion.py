import uuid
import shutil
import os
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from config import settings
from models.schemas import IngestionStatus, CodeChunk
from models.search_schemas import RepoContext
from services.repo_cloner import RepoCloner
from services.file_filter import FileFilter
from services.chunking import chunking_service
from services.language_parser import language_parser
from utils.logger import get_logger
from utils.hashing import hash_text

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

job_store: dict[str, IngestionStatus] = {}
INDEXED_REPOS: dict[str, RepoContext] = {}


class IngestionService:
    def __init__(self, vector_db=None, embedding_generator=None, keyword_index=None):
        self.cloner = RepoCloner()
        self.filter = FileFilter()
        self.vector_db = vector_db
        self.embedding_generator = embedding_generator
        self.keyword_index = keyword_index

    def ingest_repo(self, repo_url: str, branch: str) -> str:
        job_id = str(uuid.uuid4())
        job_store[job_id] = IngestionStatus(
            job_id=job_id,
            status="queued",
            files_indexed=0,
            chunks_created=0,
            total_chunks=0,
            chunks_indexed_in_db=0,
            vector_db_status="pending",
            embeddings_generated=0,
            embedding_cache_hits=0,
            total_embedding_api_calls=0,
            embedding_mode=self.embedding_generator.mode if self.embedding_generator else "none",
            progress_percent=0,
        )
        _executor.submit(self._run_ingestion, job_id, repo_url, branch)
        logger.info("ingestion_job_queued", job_id=job_id, repo_url=repo_url, branch=branch)
        return job_id

    def _run_ingestion(self, job_id: str, repo_url: str, branch: str) -> None:
        temp_path = os.path.join(settings.TEMP_DIR, job_id)
        repo_name = repo_url.rstrip("/").split("github.com/")[-1]

        try:
            self._update_job(job_id, status="processing", progress_percent=5)

            logger.info("cloning_repo", job_id=job_id, repo_url=repo_url)
            clone_path = self.cloner.clone_repo(repo_url, branch, temp_path)
            self._update_job(job_id, progress_percent=30)

            logger.info("filtering_files", job_id=job_id)
            code_files = self.filter.get_code_files(clone_path)
            clone_root = os.path.abspath(clone_path)

            if len(code_files) > settings.MAX_FILES:
                raise ValueError(
                    f"Repository has {len(code_files)} files, exceeding limit of {settings.MAX_FILES}."
                )

            total_files = len(code_files)
            logger.info("files_found", job_id=job_id, count=total_files)
            self._update_job(job_id, progress_percent=40, files_indexed=total_files)

            all_chunks: list[CodeChunk] = []
            languages_seen = set()

            for idx, fpath in enumerate(code_files):
                try:
                    content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                    language = self.filter.detect_language(fpath)
                    languages_seen.add(language)
                    abs_fp = os.path.abspath(fpath)
                    try:
                        rel = os.path.relpath(abs_fp, clone_root)
                    except ValueError:
                        rel = os.path.basename(fpath)
                    repo_relative_path = rel.replace(os.sep, "/")
                    chunks = chunking_service.chunk_code(
                        content, language, repo_relative_path
                    )
                    deps = language_parser.extract_dependencies(
                        content, language, fpath
                    )
                    for chunk in chunks:
                        chunk.dependencies = deps
                    all_chunks.extend(chunks)
                except Exception as exc:
                    logger.warning("file_processing_error", job_id=job_id, file=fpath, error=str(exc))

                progress = 40 + int((idx + 1) / max(total_files, 1) * 30)
                self._update_job(
                    job_id,
                    progress_percent=progress,
                    chunks_created=len(all_chunks),
                    total_chunks=len(all_chunks),
                )

            self._update_job(
                job_id,
                progress_percent=70,
                files_indexed=total_files,
                chunks_created=len(all_chunks),
                total_chunks=len(all_chunks),
                chunks=all_chunks,
            )

            indexed_count, embed_stats = self._embed_and_upsert(
                job_id=job_id,
                chunks=all_chunks,
                repo_name=repo_name,
            )

            self._update_job(
                job_id,
                status="completed",
                progress_percent=100,
                chunks_indexed_in_db=indexed_count,
                vector_db_status="completed" if indexed_count > 0 else "skipped",
                embeddings_generated=embed_stats.get("generated", 0),
                embedding_cache_hits=embed_stats.get("cache_hits", 0),
                total_embedding_api_calls=embed_stats.get("api_calls", 0),
            )

            INDEXED_REPOS[repo_name] = RepoContext(
                repo_name=repo_name,
                repo_url=repo_url,
                languages=sorted(languages_seen),
                file_count=total_files,
                chunk_count=len(all_chunks),
                indexed_at=datetime.now(timezone.utc).isoformat(),
            )

            logger.info(
                "ingestion_complete",
                job_id=job_id,
                files=total_files,
                chunks=len(all_chunks),
                indexed=indexed_count,
                **embed_stats,
            )

        except Exception as exc:
            logger.error("ingestion_failed", job_id=job_id, error=str(exc))
            self._update_job(
                job_id,
                status="failed",
                error=str(exc),
                progress_percent=0,
                vector_db_status="failed",
            )
        finally:
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)

    def _embed_and_upsert(
        self, job_id: str, chunks: list[CodeChunk], repo_name: str
    ) -> tuple[int, dict]:
        embed_stats: dict = {"generated": 0, "cache_hits": 0, "api_calls": 0}

        has_embedder = self.embedding_generator is not None
        has_vector_db = self.vector_db is not None and self.vector_db.available

        timestamp = datetime.now(timezone.utc).isoformat()

        if not has_vector_db and not self.keyword_index:
            logger.info("all_indexes_skipped", job_id=job_id)
            return 0, embed_stats

        self._update_job(job_id, vector_db_status="indexing", progress_percent=75)

        if has_vector_db:
            self.vector_db.create_collection_if_not_exists()

        batch_size = settings.EMBEDDING_BATCH_SIZE
        all_vector_batches: list[tuple] = []
        keyword_docs: list[dict] = []

        cache_hits_before = (
            self.embedding_generator._cache.hits if has_embedder else 0
        )

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_texts = [c.content for c in batch_chunks]

            if has_embedder:
                vectors = self.embedding_generator.generate_embeddings_batch(batch_texts)
            else:
                vectors = [[0.0] * settings.VECTOR_DIMENSION] * len(batch_chunks)

            for chunk, vector in zip(batch_chunks, vectors):
                chunk_id = str(uuid.uuid4())
                metadata = {
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": chunk.language,
                    "function_name": chunk.function_name,
                    "dependencies": chunk.dependencies,
                    "repo_name": repo_name,
                    "code_snippet": chunk.content[:200],
                    "content": chunk.content,
                    "char_count": chunk.char_count,
                    "token_count": chunk.token_count,
                    "timestamp": timestamp,
                }
                all_vector_batches.append((chunk_id, vector, metadata))
                keyword_docs.append({"id": chunk_id, "content": chunk.content, "metadata": metadata})

            progress = 75 + int((i + len(batch_chunks)) / max(len(chunks), 1) * 20)
            self._update_job(
                job_id,
                progress_percent=min(progress, 95),
                embeddings_generated=i + len(batch_chunks),
            )

        indexed = 0
        if has_vector_db and all_vector_batches:
            indexed = self.vector_db.upsert_chunks_batch(all_vector_batches)

        if self.keyword_index and keyword_docs:
            self.keyword_index.add_chunks_batch(keyword_docs)
            logger.info(
                "keyword_index_updated",
                job_id=job_id,
                chunks=len(keyword_docs),
                total_indexed=self.keyword_index.size,
            )

        if not has_vector_db:
            indexed = len(keyword_docs)

        if has_embedder:
            cache_hits_after = self.embedding_generator._cache.hits
            embed_stats["generated"] = len(chunks)
            embed_stats["cache_hits"] = cache_hits_after - cache_hits_before
            embed_stats["api_calls"] = self.embedding_generator._total_api_calls

        logger.info(
            "embed_and_upsert_complete",
            job_id=job_id,
            indexed=indexed,
            keyword_indexed=len(keyword_docs),
            **embed_stats,
        )
        return indexed, embed_stats

    def _update_job(self, job_id: str, **kwargs) -> None:
        if job_id not in job_store:
            return
        current = job_store[job_id]
        updated = current.model_copy(update=kwargs)
        job_store[job_id] = updated

    def get_status(self, job_id: str) -> IngestionStatus | None:
        return job_store.get(job_id)

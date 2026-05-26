"""Qdrant wrapper. Uses Cloud when QDRANT_URL + QDRANT_API_KEY are set, else falls
back to an in-memory instance (functional but non-persistent) for local dev."""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from utils.logger import get_logger

logger = get_logger(__name__)

BATCH_SIZE = 100


class VectorDBClient:
    def _normalise_point_id(self, chunk_id: str) -> str:
        # Cloud Qdrant only accepts UUIDs or unsigned ints as point IDs. Ingestion
        # passes UUIDs, but coerce anything else to a stable UUID just in case.
        if not self._cloud_mode:
            return chunk_id
        try:
            uuid.UUID(str(chunk_id))
            return chunk_id
        except Exception:
            return str(uuid.uuid5(uuid.NAMESPACE_URL, str(chunk_id)))

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str = "codemind-codebase",
        dimension: int = 384,
    ):
        self.collection_name = collection_name
        self.dimension = dimension
        self._cloud_mode = bool(url and api_key)

        if self._cloud_mode:
            try:
                self.client = QdrantClient(url=url, api_key=api_key, timeout=30)
                self.client.get_collections()
                self._available = True
                logger.info("qdrant_cloud_connected", url=url)
            except Exception as exc:
                logger.warning(
                    "qdrant_cloud_unavailable",
                    error=str(exc),
                    fallback="in-memory",
                )
                self.client = QdrantClient(":memory:")
                self._cloud_mode = False
                self._available = True
        else:
            self.client = QdrantClient(":memory:")
            self._available = True
            logger.info(
                "qdrant_in_memory",
                note="Set QDRANT_URL + QDRANT_API_KEY to enable Cloud persistence",
            )

    @property
    def available(self) -> bool:
        return self._available

    @property
    def storage_mode(self) -> str:
        return "cloud" if self._cloud_mode else "in-memory"

    def create_collection_if_not_exists(self) -> bool:
        if not self._available:
            return False
        try:
            existing = [c.name for c in self.client.get_collections().collections]
            if self.collection_name in existing:
                return True
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=self.dimension,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )
            logger.info(
                "qdrant_collection_created",
                name=self.collection_name,
                dimension=self.dimension,
                mode=self.storage_mode,
            )
            return True
        except Exception as exc:
            logger.error("qdrant_create_collection_failed", error=str(exc))
            return False

    def ensure_payload_indexes(self) -> None:
        # Cloud Qdrant needs a payload index to filter on repo_name. Re-creating an
        # existing index is harmless, so swallow the error.
        if not self._available:
            return
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="repo_name",
                field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
            )
            logger.info("qdrant_payload_index_ready", field="repo_name")
        except Exception as exc:
            logger.debug("qdrant_payload_index_skip", field="repo_name", error=str(exc))

    def upsert_chunk(self, chunk_id: str, vector: list[float], metadata: dict) -> bool:
        if not self._available:
            return False
        try:
            point_id = self._normalise_point_id(chunk_id)
            self.client.upsert(
                collection_name=self.collection_name,
                points=[qdrant_models.PointStruct(id=point_id, vector=vector, payload=metadata)],
            )
            return True
        except Exception as exc:
            logger.error("qdrant_upsert_failed", chunk_id=chunk_id, error=str(exc))
            return False

    def upsert_chunks_batch(self, chunks: list[tuple[str, list[float], dict]]) -> int:
        if not self._available or not chunks:
            return 0

        total_upserted = 0
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            points = [
                qdrant_models.PointStruct(
                    id=self._normalise_point_id(cid), vector=vec, payload=meta
                )
                for cid, vec, meta in batch
            ]
            try:
                self.client.upsert(collection_name=self.collection_name, points=points)
                total_upserted += len(batch)
            except Exception as exc:
                logger.error("qdrant_batch_upsert_failed", batch_start=i, error=str(exc))

        logger.info(
            "qdrant_upsert_complete",
            total=total_upserted,
            mode=self.storage_mode,
        )
        return total_upserted

    def query(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[dict]:
        if not self._available:
            return []

        qdrant_filter = None
        if filters:
            conditions = [
                qdrant_models.FieldCondition(
                    key=k, match=qdrant_models.MatchValue(value=v)
                )
                for k, v in filters.items()
            ]
            qdrant_filter = qdrant_models.Filter(must=conditions)

        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
            )
            return [
                {"id": str(r.id), "score": r.score, "metadata": r.payload}
                for r in results
            ]
        except Exception as exc:
            logger.error("qdrant_query_failed", error=str(exc))
            return []

    def delete_collection(self) -> bool:
        if not self._available:
            return False
        try:
            self.client.delete_collection(self.collection_name)
            logger.info("qdrant_collection_deleted", name=self.collection_name)
            return True
        except Exception as exc:
            logger.error("qdrant_delete_failed", error=str(exc))
            return False

    def get_collection_stats(self) -> dict:
        if not self._available:
            return {"status": "unavailable"}
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "status": "ok",
                "mode": self.storage_mode,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "dimension": self.dimension,
                "collection": self.collection_name,
            }
        except Exception as exc:
            logger.error("qdrant_stats_failed", error=str(exc))
            return {"status": "error", "error": str(exc)}

"""
End-to-end retrieval smoketest against Qdrant Cloud.

Creates a temporary collection, inserts a few known chunks, runs:
  - semantic search (Vector DB)
  - keyword search (in-process TF-IDF)
  - RRF merge (hybrid ranking)

Then prints ranked outputs (IDs + metadata + scores) so we can debug
ranking, filtering, and payload index behavior.

By default the collection is deleted at the end.
Set KEEP_SMOKETEST_COLLECTION=1 to keep it for inspection.
"""

from __future__ import annotations

import os
import sys
import uuid


def _print_block(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _fmt_meta(meta: dict) -> str:
    return (
        f"{meta.get('file_path')}:{meta.get('start_line')}-{meta.get('end_line')} "
        f"lang={meta.get('language')} fn={meta.get('function_name')} repo={meta.get('repo_name')}"
    )


def main() -> int:
    # Ensure imports work when running as a script.
    here = os.path.dirname(os.path.abspath(__file__))
    api_root = os.path.dirname(here)
    sys.path.insert(0, api_root)

    from config import settings
    from services.embeddings import EmbeddingGenerator
    from services.hybrid_search import HybridSearch
    from services.keyword_index import KeywordIndex
    from services.vector_db import VectorDBClient

    collection = f"codemind-smoketest-{uuid.uuid4().hex[:10]}"
    repo_name = "smoketest/repo"

    _print_block("Config")
    print(f"QDRANT_URL set: {bool(settings.QDRANT_URL)}")
    print(f"QDRANT_API_KEY set: {bool(settings.QDRANT_API_KEY)}")
    print(f"Collection: {collection}")

    vdb = VectorDBClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        collection_name=collection,
        dimension=settings.VECTOR_DIMENSION,
    )
    if not vdb.available:
        raise SystemExit("Vector DB not available")

    _print_block("Create collection + payload index")
    ok = vdb.create_collection_if_not_exists()
    print(f"create_collection_if_not_exists: {ok}")
    vdb.ensure_payload_indexes()
    print("ensure_payload_indexes: done")

    # Use configured HF key if it exists; otherwise fall back to deterministic mock.
    gen = EmbeddingGenerator(
        api_key=settings.HUGGINGFACE_API_KEY,
        model_name=settings.EMBEDDING_MODEL,
    )
    idx = KeywordIndex()
    hs = HybridSearch(vector_db=vdb, embedding_generator=gen, keyword_index=idx)

    chunks = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "a-auth-login")),
            "content": "Login page uses Clerk SignIn and routes unauthenticated users to /",
            "metadata": {
                "file_path": "client/src/pages/Login.jsx",
                "start_line": 1,
                "end_line": 120,
                "language": "javascript",
                "function_name": "Login",
                "repo_name": repo_name,
                "code_snippet": "const Login = () => { /* ... */ }",
            },
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "b-auth-middleware")),
            "content": "protect middleware checks JWT token and rejects unauthenticated requests",
            "metadata": {
                "file_path": "server/middlewares/auth.js",
                "start_line": 1,
                "end_line": 90,
                "language": "javascript",
                "function_name": "protect",
                "repo_name": repo_name,
                "code_snippet": "export const protect = async (req,res,next) => { /* ... */ }",
            },
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "c-db-qdrant")),
            "content": "Vector database stores embeddings and supports filtered similarity search by repo_name",
            "metadata": {
                "file_path": "apps/api/services/vector_db.py",
                "start_line": 1,
                "end_line": 240,
                "language": "python",
                "function_name": "VectorDBClient.query",
                "repo_name": repo_name,
                "code_snippet": "def query(self, vector, top_k=10, filters=None):",
            },
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "d-ui-misc")),
            "content": "Inbox page lists recent messages and shows suggestions sidebar",
            "metadata": {
                "file_path": "client/src/pages/Inbox.jsx",
                "start_line": 1,
                "end_line": 120,
                "language": "javascript",
                "function_name": "Inbox",
                "repo_name": repo_name,
                "code_snippet": "const Inbox = () => { /* ... */ }",
            },
        },
    ]

    _print_block("Insert chunks")
    idx.add_chunks_batch(chunks)
    inserted = 0
    for ch in chunks:
        vec = gen.generate_embedding(ch["content"])
        if vdb.upsert_chunk(ch["id"], vec, ch["metadata"]):
            inserted += 1
        else:
            print(f"FAILED upsert id={ch['id']}")
    print(f"Inserted: {inserted}/{len(chunks)}")
    print(f"Keyword index size: {idx.size}")
    print(f"Embedding mode: {gen.mode}")

    query = "Where is login implemented and how does authentication work?"
    filters = {"repo_name": repo_name}

    _print_block("Semantic search (vector DB) with repo_name filter")
    sem, embed_ms = hs.semantic_search(query, top_k=5, filters=filters)
    print(f"embed_ms={round(embed_ms,1)} results={len(sem)}")
    for i, r in enumerate(sem, 1):
        meta = r.get("metadata") or {}
        print(f"{i}. id={r['id']} semantic_score={r.get('score',0):.4f}  {_fmt_meta(meta)}")

    _print_block("Keyword search (TF-IDF) with repo_name filter")
    kw = hs.keyword_search(query, top_k=5, filters=filters)
    print(f"results={len(kw)}")
    for i, r in enumerate(kw, 1):
        meta = r.get("metadata") or {}
        print(f"{i}. id={r['id']} keyword_score={r.get('score',0):.4f}  {_fmt_meta(meta)}")

    _print_block("Hybrid search (RRF merge)")
    merged, embed_ms2, search_ms = hs.hybrid_search(query, top_k=10, filters=filters)
    print(f"embed_ms={embed_ms2} search_ms={search_ms} results={len(merged)}")
    for i, r in enumerate(merged, 1):
        meta = r.get("metadata") or {}
        print(
            f"{i}. id={r['id']} hybrid={r.get('hybrid_score',0):.6f} "
            f"semantic={r.get('semantic_score',0):.4f} keyword={r.get('keyword_score',0):.4f}  "
            f"{_fmt_meta(meta)}"
        )

    _print_block("Filter negative test (wrong repo_name should return 0)")
    wrong = {"repo_name": "smoketest/other"}
    res, _, _ = hs.hybrid_search(query, top_k=5, filters=wrong)
    print(f"results={len(res)} (expected 0)")

    keep = os.getenv("KEEP_SMOKETEST_COLLECTION", "").strip() in {"1", "true", "True", "yes", "YES"}
    if keep:
        _print_block("Cleanup skipped")
        print("KEEP_SMOKETEST_COLLECTION is set; leaving collection in Qdrant.")
    else:
        _print_block("Cleanup")
        deleted = vdb.delete_collection()
        print(f"delete_collection: {deleted}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


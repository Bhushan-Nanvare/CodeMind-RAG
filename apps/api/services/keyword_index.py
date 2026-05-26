"""In-memory TF-IDF keyword index. Populated during ingestion, queried in hybrid search."""
import re
import math
from utils.logger import get_logger

logger = get_logger(__name__)

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "not", "are", "was",
    "has", "have", "had", "but", "from", "they", "you", "all", "can",
    "will", "use", "its", "out", "one", "get", "set", "new", "also",
    "into", "been", "more", "when", "then", "than", "any", "may",
    "each", "how", "what", "which", "who", "where", "else", "none",
    "true", "false", "return", "import", "class", "def", "pass",
    "self", "init", "none", "bool", "int", "str", "list", "dict",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


class KeywordIndex:
    def __init__(self):
        self._chunks: list[dict] = []
        self._idf_cache: dict[str, float] = {}
        self._dirty = True

    @property
    def size(self) -> int:
        return len(self._chunks)

    def add_chunk(self, chunk_id: str, content: str, metadata: dict) -> None:
        token_freq: dict[str, int] = {}
        for t in _tokenize(content):
            token_freq[t] = token_freq.get(t, 0) + 1

        self._chunks.append({
            "id": chunk_id,
            "tokens": token_freq,
            "content": content,
            "metadata": metadata,
        })
        self._dirty = True

    def add_chunks_batch(self, chunks: list[dict]) -> None:
        for chunk in chunks:
            self.add_chunk(chunk["id"], chunk["content"], chunk["metadata"])
        logger.info("keyword_index_batch_added", count=len(chunks), total=self.size)

    def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[dict]:
        if not self._chunks:
            return []

        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        if self._dirty:
            self._rebuild_idf()

        results = []
        for chunk in self._chunks:
            if filters:
                meta = chunk["metadata"]
                if not all(meta.get(k) == v for k, v in filters.items()):
                    continue

            tf_idf_score = 0.0
            matched_terms = []
            for token in query_tokens:
                if token in chunk["tokens"]:
                    tf = chunk["tokens"][token] / max(sum(chunk["tokens"].values()), 1)
                    idf = self._idf_cache.get(token, 0.0)
                    tf_idf_score += tf * idf
                    matched_terms.append(token)

            if tf_idf_score > 0:
                results.append({
                    "id": chunk["id"],
                    "score": tf_idf_score,
                    "keyword_matches": matched_terms,
                    "metadata": chunk["metadata"],
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _rebuild_idf(self) -> None:
        n = len(self._chunks)
        if n == 0:
            return

        df: dict[str, int] = {}
        for chunk in self._chunks:
            for token in chunk["tokens"]:
                df[token] = df.get(token, 0) + 1

        self._idf_cache = {
            token: math.log((1 + n) / (1 + count)) + 1.0
            for token, count in df.items()
        }
        self._dirty = False
        logger.debug("keyword_idf_rebuilt", vocab_size=len(self._idf_cache))

    def clear(self) -> None:
        self._chunks.clear()
        self._idf_cache.clear()
        self._dirty = True
        logger.info("keyword_index_cleared")

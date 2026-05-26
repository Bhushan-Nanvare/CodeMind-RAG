class EmbeddingCache:
    def __init__(self, max_size: int = 10000):
        self._cache: dict[str, list[float]] = {}
        self._max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, text_hash: str) -> list[float] | None:
        if text_hash in self._cache:
            self.hits += 1
            return self._cache[text_hash]
        self.misses += 1
        return None

    def set(self, text_hash: str, vector: list[float]) -> None:
        if len(self._cache) >= self._max_size:
            del self._cache[next(iter(self._cache))]
        self._cache[text_hash] = vector

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total > 0 else 0.0,
            "size": len(self._cache),
        }

    def clear(self) -> None:
        self._cache.clear()
        self.hits = 0
        self.misses = 0

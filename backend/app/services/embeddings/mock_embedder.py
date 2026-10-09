import hashlib
import math

from app.core.config import settings


class MockEmbedder:
    """Dependency-free, API-key-free embedder for offline dev/CI.

    Not semantically meaningful in the way a real model is, but not pure
    noise either: it's a character/bigram hashing-trick bag-of-words vector
    (works for Chinese text, which has no whitespace word boundaries), so
    documents that share vocabulary with the query score higher than ones
    that don't. That is enough to exercise the full retrieval + RBAC-filter
    pipeline end to end without any external API key.
    """

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = self._tokenize(text)
        for token in tokens:
            idx = int(hashlib.blake2b(token.encode("utf-8"), digest_size=8).hexdigest(), 16) % self.dim
            vec[idx] += 1.0

        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        cleaned = text.strip()
        if not cleaned:
            return []
        tokens = list(cleaned)  # unigrams, handles CJK without a tokenizer
        tokens += [cleaned[i : i + 2] for i in range(len(cleaned) - 1)]  # bigrams
        return tokens

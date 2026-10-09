from typing import Protocol


class Embedder(Protocol):
    """Swappable embedding backend. All implementations must return vectors
    of settings.embedding_dim so a backend switch never requires rebuilding
    the vector collection.
    """

    dim: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

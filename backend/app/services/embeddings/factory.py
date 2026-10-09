from functools import lru_cache

from app.core.config import settings
from app.services.embeddings.base import Embedder


@lru_cache
def get_embedder() -> Embedder:
    if settings.embedding_backend == "local":
        from app.services.embeddings.cache import CachedEmbedder
        from app.services.embeddings.local_embedder import LocalEmbedder

        return CachedEmbedder(LocalEmbedder(), settings.local_embedding_model, settings.embedding_cache_path)

    if settings.embedding_backend == "hunyuan":
        from app.services.embeddings.hunyuan_embedder import HunyuanEmbedder

        return HunyuanEmbedder()

    from app.services.embeddings.mock_embedder import MockEmbedder

    return MockEmbedder()

from functools import lru_cache

from app.core.config import settings
from app.services.vectorstore.base import VectorStore


@lru_cache
def get_vector_store() -> VectorStore:
    if settings.vector_backend == "tencent_vectordb":
        from app.services.vectorstore.tencent_store import TencentVectorDBStore

        return TencentVectorDBStore()

    from app.services.vectorstore.qdrant_store import QdrantVectorStore

    return QdrantVectorStore()

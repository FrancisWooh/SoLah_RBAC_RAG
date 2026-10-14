"""Local sentence-transformers embedding backend (Qwen3-Embedding-0.6B by
default; any sentence-transformers model works). No API key needed.

Qwen3-Embedding is asymmetric: queries get an instruction prefix, documents
do not. embed_texts() is the document path (ingestion); embed_query() is the
query path. Callers that only know embed_texts() still work, just with
slightly lower retrieval quality for queries.
"""

from app.core.config import settings

QUERY_INSTRUCTION = "Given a user question, retrieve the internal company document passages that answer it"


class LocalEmbedder:
    def __init__(self, dim: int | None = None, model_name: str | None = None):
        import torch
        from sentence_transformers import SentenceTransformer

        self.dim = dim or settings.embedding_dim
        self.model_name = model_name or settings.local_embedding_model
        # Qwen3-Embedding weights are BFloat16; sentence-transformers' encode()
        # feeds float32 input by default, causing a dtype mismatch RuntimeError
        # in the linear layers. Loading with torch_dtype=float32 upcasts the
        # weights once at load time so all subsequent encode() calls are
        # consistent. (The model is only 0.6B params, so the extra memory is
        # negligible.)
        try:
            self._model = SentenceTransformer(
                self.model_name, truncate_dim=self.dim,
                model_kwargs={"torch_dtype": torch.float32},
                local_files_only=True,
            )
        except Exception:
            self._model = SentenceTransformer(
                self.model_name, truncate_dim=self.dim,
                model_kwargs={"torch_dtype": torch.float32},
            )
        self._model.max_seq_length = 1024  # table chunks reach ~950 tokens

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, batch_size=16, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        prompt = f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text}"
        vec = self._model.encode([prompt], normalize_embeddings=True)[0]
        return vec.tolist()

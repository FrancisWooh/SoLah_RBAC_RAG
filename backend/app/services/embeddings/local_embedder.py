"""Local sentence-transformers embedding backend.

Default: Qwen3-Embedding-0.6B (asymmetric — queries get an instruction prefix).
Also supports symmetric models like BAAI/bge-base-zh-v1.5 (no instruction
prefix needed for queries). Detection is based on model name.
"""

from app.core.config import settings

QUERY_INSTRUCTION = "Given a user question, retrieve the internal company document passages that answer it"

# Models that use instruction prefix for queries (asymmetric)
ASYMMETRIC_MODELS = {"Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-4B", "Qwen/Qwen3-Embedding-8B"}


class LocalEmbedder:
    def __init__(self, dim: int | None = None, model_name: str | None = None):
        import torch
        from sentence_transformers import SentenceTransformer

        self.dim = dim or settings.embedding_dim
        self.model_name = model_name or settings.local_embedding_model
        self._is_asymmetric = self.model_name in ASYMMETRIC_MODELS
        # Qwen3-Embedding weights are BFloat16; sentence-transformers' encode()
        # feeds float32 input by default, causing a dtype mismatch RuntimeError
        # in the linear layers. Loading with torch_dtype=float32 upcasts the
        # weights once at load time so all subsequent encode() calls are
        # consistent. For bge models this is harmless (they're already float32).
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
        self._model.max_seq_length = settings.embedding_max_seq_length  # table chunks reach ~950 tokens

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, batch_size=settings.embedding_batch_size, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        if self._is_asymmetric:
            prompt = f"Instruct: {QUERY_INSTRUCTION}\nQuery: {text}"
        else:
            prompt = text
        vec = self._model.encode([prompt], normalize_embeddings=True)[0]
        return vec.tolist()

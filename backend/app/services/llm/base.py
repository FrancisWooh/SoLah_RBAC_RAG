from typing import Protocol

from app.services.vectorstore.base import ScoredChunk


class LLM(Protocol):
    def generate_answer(self, question: str, context_chunks: list[ScoredChunk]) -> str: ...

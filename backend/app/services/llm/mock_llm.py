from app.services.vectorstore.base import ScoredChunk


class MockLLM:
    """Extractive, no-API-key stand-in: not a real generation model, just
    enough to demo the end-to-end pipeline (retrieval -> RBAC filter ->
    "answer" with citations) without any external dependency. Swap
    settings.llm_backend to "hunyuan" for an actually-generated answer.
    """

    def generate_answer(self, question: str, context_chunks: list[ScoredChunk]) -> str:
        if not context_chunks:
            return "未在知识库中检索到相关内容。"

        lines = ["根据内部知识库检索到的相关资料，摘录如下："]
        for chunk in context_chunks:
            lines.append(f"- 【{chunk.doc_id}】{chunk.text}")
        return "\n".join(lines)

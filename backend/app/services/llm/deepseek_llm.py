"""Local-degraded LLM backend: any OpenAI-chat-compatible server (e.g. a
self-hosted DeepSeek-R1-Distill-Qwen-14B behind vLLM/Ollama), per readme.txt's
"DeepSeek-R1-Distill-Qwen-14B（本地）" option. NOT exercised here — no such
server was running in this environment. The OpenAI chat-completions wire
format is stable/well-known, but still smoke-test against your actual
deployment before relying on it.
"""

import httpx

from app.core.config import settings
from app.services.llm.hunyuan_llm import SYSTEM_PROMPT
from app.services.vectorstore.base import ScoredChunk


class DeepSeekLLM:
    def generate_answer(self, question: str, context_chunks: list[ScoredChunk]) -> str:
        context_text = "\n".join(f"【{c.doc_id}】{c.text}" for c in context_chunks) or "（无检索到的资料）"

        response = httpx.post(
            f"{settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": settings.deepseek_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"资料：\n{context_text}\n\n问题：{question}"},
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

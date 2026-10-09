"""Claude (Anthropic API) LLM backend, via the official SDK.

Same prompt contract as openai_compat_llm: retrieved text goes to the model
inside <document> tags and is declared untrusted data (prompt-injection
defence in depth; authorization never depends on the model, the RBAC filter
already ran on the chunks).
"""

from collections.abc import Iterator

import anthropic

from app.core.config import settings
from app.services.llm.openai_compat_llm import SYSTEM_PROMPT, build_messages
from app.services.vectorstore.base import ScoredChunk

REFUSAL_TEXT = "模型出于安全策略拒绝回答该问题。"


class AnthropicLLM:
    supports_history = True

    def __init__(self):
        # SDK retries 408/409/429/5xx with backoff (max_retries default 2).
        headers = {"anthropic-workspace-id": settings.anthropic_workspace_id} if settings.anthropic_workspace_id else None
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key, timeout=120.0, default_headers=headers
        )

    def _request(self, question: str, context_chunks: list[ScoredChunk], history: list[dict] | None = None) -> dict:
        # build_messages() returns [system, user] in OpenAI shape; Anthropic
        # takes the system prompt as a top-level parameter.
        return dict(
            model=settings.anthropic_model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=build_messages(question, context_chunks, history)[1:],
            # Routine grounded Q&A: low effort keeps latency/cost down.
            output_config={"effort": settings.anthropic_effort},
            # Server-side refusal fallback (routes by refusal category).
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

    def stream_answer(
        self, question: str, context_chunks: list[ScoredChunk], history: list[dict] | None = None
    ) -> Iterator[str]:
        with self._client.beta.messages.stream(**self._request(question, context_chunks, history)) as stream:
            emitted = False
            for text in stream.text_stream:
                if text:
                    emitted = True
                    yield text
            final = stream.get_final_message()
        if final.stop_reason == "refusal" and not emitted:
            yield REFUSAL_TEXT

    def generate_answer(
        self, question: str, context_chunks: list[ScoredChunk], history: list[dict] | None = None
    ) -> str:
        response = self._client.beta.messages.create(**self._request(question, context_chunks, history))
        if response.stop_reason == "refusal":
            return REFUSAL_TEXT
        return "".join(block.text for block in response.content if block.type == "text").strip()

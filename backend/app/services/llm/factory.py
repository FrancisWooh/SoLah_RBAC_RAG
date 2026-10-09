from functools import lru_cache

from app.core.config import settings
from app.services.llm.base import LLM


@lru_cache
def get_llm() -> LLM:
    if settings.llm_backend == "hunyuan":
        from app.services.llm.hunyuan_llm import HunyuanLLM

        return HunyuanLLM()

    if settings.llm_backend == "anthropic":
        from app.services.llm.anthropic_llm import AnthropicLLM

        return AnthropicLLM()

    if settings.llm_backend == "openai_compat":
        from app.services.llm.openai_compat_llm import OpenAICompatLLM

        return OpenAICompatLLM()

    if settings.llm_backend == "deepseek":
        from app.services.llm.deepseek_llm import DeepSeekLLM

        return DeepSeekLLM()

    from app.services.llm.mock_llm import MockLLM

    return MockLLM()

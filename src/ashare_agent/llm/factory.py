from __future__ import annotations

from ashare_agent.llm.base import LLMClient
from ashare_agent.llm.deepseek import DeepSeekClient
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.llm.openai_client import OpenAIClient


def create_llm_client(
    provider: str = "mock",
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
    deepseek_api_key: str | None = None,
    deepseek_model: str = "deepseek-v4-pro",
) -> LLMClient:
    provider = provider.lower()
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai":
        return OpenAIClient(api_key=openai_api_key, model=openai_model)
    if provider == "deepseek":
        return DeepSeekClient(api_key=deepseek_api_key, model=deepseek_model)
    raise RuntimeError(f"未知 LLM provider: {provider}")

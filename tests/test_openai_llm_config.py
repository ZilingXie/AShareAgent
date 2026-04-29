from __future__ import annotations

from ashare_agent.llm.factory import create_llm_client
from ashare_agent.llm.openai_client import OpenAIClient


def test_llm_factory_uses_openai_when_configured() -> None:
    client = create_llm_client(
        provider="openai",
        openai_api_key="test-key",
        openai_model="gpt-4.1-mini",
    )

    assert isinstance(client, OpenAIClient)
    assert client.model == "gpt-4.1-mini"

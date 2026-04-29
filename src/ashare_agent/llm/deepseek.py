from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from openai import OpenAI

from ashare_agent.domain import LLMAnalysis


class DeepSeekClient:
    def __init__(self, api_key: str | None = None, model: str = "deepseek-v4-pro") -> None:
        self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self._model = model
        if not self._api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未设置，不能调用真实 DeepSeek API")
        self._client = OpenAI(api_key=self._api_key, base_url="https://api.deepseek.com")

    def analyze_pre_market(self, trade_date: date, context: dict[str, Any]) -> LLMAnalysis:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 A 股研究助理，只输出结构化研究摘要。"
                        "不得给出荐股、收益承诺或真实交易建议。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"trade_date": trade_date.isoformat(), "context": context},
                        ensure_ascii=False,
                    ),
                },
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        content = response.choices[0].message.content or ""
        return LLMAnalysis(
            trade_date=trade_date,
            model=self._model,
            summary=content,
            key_points=[],
            risk_notes=["LLM 仅做分析辅助，交易信号由规则和风控决定。"],
            raw_response=response.model_dump(),
        )


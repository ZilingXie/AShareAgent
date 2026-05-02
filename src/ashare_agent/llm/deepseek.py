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

    def generate_strategy_insight(
        self,
        trade_date: date,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 AShareAgent 的策略复盘助理。"
                        "只能输出 JSON object，不得输出 Markdown。"
                        "只提出策略优化假设，不得给出荐股、收益承诺、真实交易建议，"
                        "不得要求绕过风控或修改真实交易相关配置。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "trade_date": trade_date.isoformat(),
                            "context": context,
                            "schema": {
                                "summary": "string",
                                "attribution": ["string"],
                                "hypotheses": [
                                    {
                                        "area": "string",
                                        "direction": "string",
                                        "reason": "string",
                                        "risk": "string",
                                    }
                                ],
                                "recommended_experiments": [
                                    {
                                        "name": "string",
                                        "param": "string",
                                        "candidate_value": "number|string|int",
                                    }
                                ],
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        return {
            "model": self._model,
            "content": response.choices[0].message.content or "",
            "raw_response": response.model_dump(),
        }

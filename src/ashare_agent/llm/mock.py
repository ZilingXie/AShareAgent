from __future__ import annotations

from datetime import date
from typing import Any

from ashare_agent.domain import LLMAnalysis


class MockLLMClient:
    def analyze_pre_market(self, trade_date: date, context: dict[str, Any]) -> LLMAnalysis:
        top_symbols = context.get("top_symbols", [])
        summary = f"Mock 盘前分析：市场状态 {context.get('market_regime', 'unknown')}。"
        return LLMAnalysis(
            trade_date=trade_date,
            model="mock-llm",
            summary=summary,
            key_points=[f"重点观察: {', '.join(top_symbols) if top_symbols else '无'}"],
            risk_notes=["仅用于模拟研究，不构成投资建议。"],
            raw_response={"context": context},
        )


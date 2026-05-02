from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from ashare_agent.domain import LLMAnalysis


class LLMClient(Protocol):
    def analyze_pre_market(self, trade_date: date, context: dict[str, Any]) -> LLMAnalysis: ...

    def generate_strategy_insight(
        self,
        trade_date: date,
        context: dict[str, Any],
    ) -> dict[str, Any]: ...

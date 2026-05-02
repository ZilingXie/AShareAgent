from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import Any, cast

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

    def generate_strategy_insight(
        self,
        trade_date: date,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        day_summary = context.get("day_summary", {})
        signal_count = 0
        risk_rejected_count = 0
        if isinstance(day_summary, Mapping):
            day_summary_payload = cast(Mapping[str, object], day_summary)
            raw_signals = day_summary_payload.get("signals", [])
            raw_risk = day_summary_payload.get("risk_decisions", [])
            signal_count = (
                len(cast(list[object], raw_signals)) if isinstance(raw_signals, list) else 0
            )
            if isinstance(raw_risk, list):
                risk_decisions = cast(list[object], raw_risk)
                risk_rejected_count = sum(
                    1 for item in risk_decisions if _is_rejected_risk_decision(item)
                )
        payload = {
            "summary": (
                f"Mock 策略复盘：{trade_date.isoformat()} "
                f"信号 {signal_count} 个，风控拒绝 {risk_rejected_count} 个。"
            ),
            "attribution": [
                "信号数量偏少，先验证最低评分阈值是否过严。",
                "LLM 仅生成假设，参数变更由代码回测验证。",
            ],
            "hypotheses": [
                {
                    "area": "signal.min_score",
                    "direction": "lower",
                    "reason": "近期信号偏少",
                    "risk": "可能增加低质量交易",
                }
            ],
            "recommended_experiments": [
                {
                    "name": "降低最低评分阈值",
                    "param": "signal.min_score",
                    "candidate_value": 0.50,
                }
            ],
        }
        return {
            "model": "mock-llm",
            "content": json.dumps(payload, ensure_ascii=False),
            "raw_response": {"context": context},
        }


def _is_rejected_risk_decision(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    payload = cast(Mapping[str, object], value)
    return payload.get("approved") is False

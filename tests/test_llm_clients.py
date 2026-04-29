from __future__ import annotations

from datetime import date

from ashare_agent.llm.mock import MockLLMClient


def test_mock_llm_returns_structured_pre_market_analysis() -> None:
    analysis = MockLLMClient().analyze_pre_market(
        trade_date=date(2026, 4, 29),
        context={"market_regime": "risk_on", "top_symbols": ["510300"]},
    )

    assert analysis.model == "mock-llm"
    assert analysis.summary
    assert analysis.risk_notes
    assert analysis.trade_date == date(2026, 4, 29)


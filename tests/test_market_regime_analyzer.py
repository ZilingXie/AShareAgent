from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from ashare_agent.agents.market_regime_analyzer import MarketRegimeAnalyzer
from ashare_agent.domain import MarketBar


def test_market_regime_analyzer_marks_risk_on_when_trend_and_volume_improve() -> None:
    trade_date = date(2026, 4, 29)
    bars: list[MarketBar] = []
    for idx in range(30):
        day = trade_date - timedelta(days=29 - idx)
        close = Decimal("3.00") + Decimal(idx) * Decimal("0.02")
        bars.append(
            MarketBar(
                symbol="510300",
                trade_date=day,
                open=close - Decimal("0.01"),
                high=close + Decimal("0.02"),
                low=close - Decimal("0.02"),
                close=close,
                volume=1_000_000 + idx * 10_000,
                amount=Decimal("100000000") + Decimal(idx * 1_000_000),
                source="mock",
                collected_at=datetime(2026, 4, 29, 16),
            )
        )

    regime = MarketRegimeAnalyzer().analyze(trade_date=trade_date, bars=bars)

    assert regime.status == "risk_on"
    assert regime.trend_score > 0
    assert regime.volume_score > 0
    assert regime.reasons


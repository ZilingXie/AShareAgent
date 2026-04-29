from __future__ import annotations

from datetime import date

from ashare_agent.agents.signal_engine import SignalEngine
from ashare_agent.domain import (
    AnnouncementEvent,
    MarketRegime,
    TechnicalIndicator,
)


def test_signal_engine_keeps_one_top_buy_signal_per_day() -> None:
    trade_date = date(2026, 4, 29)
    indicators = [
        TechnicalIndicator(
            symbol="510300",
            trade_date=trade_date,
            close_above_ma5=True,
            close_above_ma20=True,
            return_5d=0.04,
            return_20d=0.08,
            volume_ratio=1.4,
        ),
        TechnicalIndicator(
            symbol="159915",
            trade_date=trade_date,
            close_above_ma5=True,
            close_above_ma20=False,
            return_5d=0.01,
            return_20d=0.02,
            volume_ratio=1.1,
        ),
    ]
    events = [
        AnnouncementEvent(
            symbol="510300",
            trade_date=trade_date,
            category="distribution",
            sentiment="positive",
            is_material=True,
            exclude=False,
            reasons=["规模增长"],
        )
    ]
    regime = MarketRegime(
        trade_date=trade_date,
        status="risk_on",
        trend_score=0.8,
        volume_score=0.7,
        industry_score=0.5,
        risk_appetite_score=0.8,
        reasons=["趋势向上"],
    )

    result = SignalEngine().generate(
        trade_date=trade_date,
        indicators=indicators,
        events=events,
        regime=regime,
    )

    assert len(result.watchlist) == 2
    assert len(result.signals) == 1
    assert result.signals[0].symbol == "510300"
    assert result.signals[0].action == "paper_buy"
    assert result.signals[0].score_breakdown["technical"] > 0


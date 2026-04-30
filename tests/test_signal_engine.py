from __future__ import annotations

from datetime import date

from ashare_agent.agents.signal_engine import SignalEngine
from ashare_agent.agents.strategy_params_agent import SignalParams, SignalWeights
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


def test_signal_engine_uses_configured_weights_threshold_and_daily_signal_limit() -> None:
    trade_date = date(2026, 4, 29)
    params = SignalParams(
        min_score=0.40,
        max_daily_signals=2,
        weights=SignalWeights(
            technical=0.70,
            market=0.10,
            event=0.10,
            risk_penalty=0.10,
        ),
    )
    indicators = [
        TechnicalIndicator(
            symbol="510300",
            trade_date=trade_date,
            close_above_ma5=True,
            close_above_ma20=True,
            return_5d=0.05,
            return_20d=0.10,
            volume_ratio=1.5,
        ),
        TechnicalIndicator(
            symbol="159915",
            trade_date=trade_date,
            close_above_ma5=True,
            close_above_ma20=False,
            return_5d=0.02,
            return_20d=0.03,
            volume_ratio=1.2,
        ),
        TechnicalIndicator(
            symbol="600000",
            trade_date=trade_date,
            close_above_ma5=False,
            close_above_ma20=False,
            return_5d=-0.03,
            return_20d=-0.04,
            volume_ratio=0.6,
        ),
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

    result = SignalEngine(
        params=params,
        strategy_params_version="experiment-v1",
        strategy_params_snapshot={"version": "experiment-v1", "signal": params.snapshot()},
    ).generate(
        trade_date=trade_date,
        indicators=indicators,
        events=[],
        regime=regime,
    )

    assert [signal.symbol for signal in result.signals] == ["510300", "159915"]
    assert len(result.signals) == 2
    assert result.watchlist[0].score_breakdown["technical"] == 0.7
    assert result.signals[0].strategy_params_version == "experiment-v1"
    assert result.signals[0].strategy_params_snapshot["signal"]["max_daily_signals"] == 2
    assert result.watchlist[0].strategy_params_version == "experiment-v1"

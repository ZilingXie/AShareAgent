from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.agents.data_reliability_agent import DataReliabilityAgent
from ashare_agent.domain import (
    Asset,
    MarketBar,
    PipelineRunContext,
    SourceSnapshot,
    TradingCalendarDay,
)
from ashare_agent.repository import InMemoryRepository


def test_data_reliability_agent_reports_source_health_and_recent_market_gaps() -> None:
    repository = InMemoryRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="run-1")
    repository.save_trading_calendar_days(
        context,
        [
            TradingCalendarDay(date(2026, 4, 27), True, "trade_calendar"),
            TradingCalendarDay(date(2026, 4, 28), True, "trade_calendar"),
            TradingCalendarDay(date(2026, 4, 29), True, "trade_calendar"),
        ],
    )
    repository.save_universe_assets(
        context,
        [Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
    )
    repository.save_market_bars(
        context,
        [
            MarketBar(
                symbol="510300",
                trade_date=date(2026, 4, 27),
                open=Decimal("4.00"),
                high=Decimal("4.10"),
                low=Decimal("3.90"),
                close=Decimal("4.00"),
                volume=1000,
                amount=Decimal("4000"),
                source="test",
            ),
            MarketBar(
                symbol="510300",
                trade_date=date(2026, 4, 29),
                open=Decimal("4.10"),
                high=Decimal("4.20"),
                low=Decimal("4.00"),
                close=Decimal("4.10"),
                volume=1000,
                amount=Decimal("4100"),
                source="test",
            ),
        ],
    )
    repository.save_raw_source_snapshots(
        context,
        [
            SourceSnapshot("market_bars", context.trade_date, "success", row_count=2),
            SourceSnapshot("news", context.trade_date, "success", row_count=0),
            SourceSnapshot(
                "policy",
                context.trade_date,
                "failed",
                failure_reason="policy endpoint failed",
            ),
        ],
    )

    report = DataReliabilityAgent(
        repository,
        required_data_sources={"market_bars"},
    ).analyze(context.trade_date)

    assert report.status == "failed"
    assert report.is_trade_date is True
    assert report.lookback_trade_days == 30
    assert report.total_sources == 3
    assert report.failed_source_count == 1
    assert report.empty_source_count == 1
    assert round(report.source_failure_rate, 4) == 0.3333
    assert report.missing_market_bar_count == 1
    assert report.source_health[0].source == "market_bars"
    assert report.market_bar_gaps[0].symbol == "510300"
    assert report.market_bar_gaps[0].missing_dates == ["2026-04-28"]
    assert {issue.check_name for issue in report.issues} >= {
        "source_failed",
        "empty_source",
        "market_bar_gap",
    }


def test_data_reliability_agent_skips_market_gap_check_on_non_trade_date() -> None:
    repository = InMemoryRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="run-1")
    repository.save_trading_calendar_days(
        context,
        [
            TradingCalendarDay(date(2026, 4, 29), True, "trade_calendar"),
            TradingCalendarDay(date(2026, 4, 30), False, "trade_calendar"),
        ],
    )

    report = DataReliabilityAgent(repository).analyze(context.trade_date)

    assert report.status == "skipped"
    assert report.is_trade_date is False
    assert report.missing_market_bar_count == 0
    assert [issue.check_name for issue in report.issues] == ["non_trade_date"]

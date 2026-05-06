from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ashare_agent.agents.data_collector import DataCollector
from ashare_agent.agents.data_quality_agent import DataQualityAgent
from ashare_agent.domain import (
    Asset,
    MarketBar,
    MarketDataset,
    SourceSnapshot,
    TradingCalendarDay,
)
from ashare_agent.providers.mock import MockProvider


def _bar(symbol: str, trade_date: date, close: Decimal = Decimal("4.00")) -> MarketBar:
    return MarketBar(
        symbol=symbol,
        trade_date=trade_date,
        open=close,
        high=close + Decimal("0.10"),
        low=close - Decimal("0.10"),
        close=close,
        volume=1000,
        amount=close * Decimal("1000"),
        source="test",
    )


def _daily_quality_dataset(
    *,
    trade_date: date,
    bar_dates: list[date],
    calendar_dates: list[date],
) -> MarketDataset:
    return MarketDataset(
        trade_date=trade_date,
        assets=[Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        bars=[_bar("510300", bar_date) for bar_date in bar_dates],
        announcements=[],
        news=[],
        policy_items=[],
        industry_snapshots=[],
        source_snapshots=[
            SourceSnapshot(
                source="market_bars",
                trade_date=trade_date,
                status="success",
                row_count=len(bar_dates),
            )
        ],
        trade_calendar=None,
        trade_calendar_dates=calendar_dates,
        trade_calendar_days=[
            TradingCalendarDay(calendar_date=calendar_date, is_trade_date=True, source="test")
            for calendar_date in calendar_dates
        ],
    )


def test_data_quality_agent_passes_mock_dataset() -> None:
    trade_date = date(2026, 4, 29)
    dataset = DataCollector(MockProvider()).collect(trade_date)

    report = DataQualityAgent(required_data_sources={"universe", "market_bars"}).analyze(
        stage="pre_market",
        dataset=dataset,
    )

    assert report.status == "passed"
    assert report.source_failure_rate == 0
    assert report.failed_source_count == 0
    assert report.empty_source_count == 0
    assert report.missing_market_bar_count == 0
    assert report.abnormal_price_count == 0
    assert report.issues == []


def test_data_quality_agent_fails_required_empty_source_and_missing_trade_date_bars() -> None:
    trade_date = date(2026, 4, 29)
    dataset = MarketDataset(
        trade_date=trade_date,
        assets=[Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=trade_date - timedelta(days=1),
                open=Decimal("4.00"),
                high=Decimal("4.10"),
                low=Decimal("3.90"),
                close=Decimal("4.05"),
                volume=1000,
                amount=Decimal("4050"),
                source="test",
            )
        ],
        announcements=[],
        news=[],
        policy_items=[],
        industry_snapshots=[],
        source_snapshots=[
            SourceSnapshot(
                source="market_bars",
                trade_date=trade_date,
                status="success",
                row_count=0,
            )
        ],
        trade_calendar=None,
        trade_calendar_dates=[],
    )

    report = DataQualityAgent(required_data_sources={"market_bars"}).analyze(
        stage="pre_market",
        dataset=dataset,
    )

    assert report.status == "failed"
    assert report.empty_source_count == 1
    assert report.missing_market_bar_count == 1
    assert {issue.check_name for issue in report.issues} >= {
        "empty_source",
        "missing_market_bar",
    }


def test_data_quality_agent_fails_recent_trade_day_market_bar_gap() -> None:
    trade_date = date(2026, 4, 29)
    dataset = MarketDataset(
        trade_date=trade_date,
        assets=[Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=date(2026, 4, 27),
                open=Decimal("4.00"),
                high=Decimal("4.10"),
                low=Decimal("3.90"),
                close=Decimal("4.05"),
                volume=1000,
                amount=Decimal("4050"),
                source="test",
            ),
            MarketBar(
                symbol="510300",
                trade_date=trade_date,
                open=Decimal("4.10"),
                high=Decimal("4.20"),
                low=Decimal("4.00"),
                close=Decimal("4.15"),
                volume=1000,
                amount=Decimal("4150"),
                source="test",
            ),
        ],
        announcements=[],
        news=[],
        policy_items=[],
        industry_snapshots=[],
        source_snapshots=[
            SourceSnapshot(
                source="market_bars",
                trade_date=trade_date,
                status="success",
                row_count=2,
            )
        ],
        trade_calendar=None,
        trade_calendar_dates=[date(2026, 4, 27), date(2026, 4, 28), trade_date],
    )

    report = DataQualityAgent(required_data_sources={"market_bars"}).analyze(
        stage="pre_market",
        dataset=dataset,
    )

    assert report.status == "failed"
    assert report.missing_market_bar_count == 1
    assert report.issues[-1].check_name == "missing_market_bar"
    assert report.issues[-1].metadata["missing_dates"] == ["2026-04-28"]


def test_data_quality_agent_fails_abnormal_prices_and_large_close_jump() -> None:
    trade_date = date(2026, 4, 29)
    dataset = MarketDataset(
        trade_date=trade_date,
        assets=[Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=trade_date - timedelta(days=1),
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
                trade_date=trade_date,
                open=Decimal("4.10"),
                high=Decimal("4.00"),
                low=Decimal("4.20"),
                close=Decimal("6.00"),
                volume=-1,
                amount=Decimal("-1"),
                source="test",
            ),
        ],
        announcements=[],
        news=[],
        policy_items=[],
        industry_snapshots=[],
        source_snapshots=[
            SourceSnapshot(
                source="market_bars",
                trade_date=trade_date,
                status="success",
                row_count=2,
            )
        ],
        trade_calendar=None,
        trade_calendar_dates=[],
    )

    report = DataQualityAgent(required_data_sources={"market_bars"}).analyze(
        stage="pre_market",
        dataset=dataset,
    )

    assert report.status == "failed"
    assert report.abnormal_price_count >= 3
    assert {issue.check_name for issue in report.issues} >= {
        "invalid_ohlc_range",
        "negative_turnover",
        "abnormal_close_jump",
    }


def test_data_quality_agent_warns_on_non_trade_date_without_missing_bar_failure() -> None:
    trade_date = date(2026, 4, 30)
    dataset = DataCollector(MockProvider()).collect(trade_date)
    dataset = MarketDataset(
        trade_date=dataset.trade_date,
        assets=dataset.assets,
        bars=[
            bar
            for bar in dataset.bars
            if not (bar.symbol == "510300" and bar.trade_date == trade_date)
        ],
        announcements=dataset.announcements,
        news=dataset.news,
        policy_items=dataset.policy_items,
        industry_snapshots=dataset.industry_snapshots,
        source_snapshots=dataset.source_snapshots,
        trade_calendar=dataset.trade_calendar
        and type(dataset.trade_calendar)(
            trade_date=dataset.trade_calendar.trade_date,
            is_trade_date=False,
            row_count=dataset.trade_calendar.row_count,
            source=dataset.trade_calendar.source,
            calendar_start=dataset.trade_calendar.calendar_start,
            calendar_end=dataset.trade_calendar.calendar_end,
        ),
        trade_calendar_dates=[
            day for day in dataset.trade_calendar_dates if day != trade_date
        ],
    )

    report = DataQualityAgent(required_data_sources={"market_bars"}).analyze(
        stage="pre_market",
        dataset=dataset,
    )

    assert report.status == "warning"
    assert report.is_trade_date is False
    assert report.missing_market_bar_count == 0
    assert [issue.check_name for issue in report.issues] == ["non_trade_date"]


def test_pre_market_and_intraday_only_require_daily_bars_through_previous_trade_date() -> None:
    trade_date = date(2026, 5, 6)
    previous_trade_date = date(2026, 5, 5)
    dataset = _daily_quality_dataset(
        trade_date=trade_date,
        bar_dates=[previous_trade_date],
        calendar_dates=[previous_trade_date, trade_date],
    )
    agent = DataQualityAgent(required_data_sources={"market_bars"})

    pre_market_report = agent.analyze(stage="pre_market", dataset=dataset)
    intraday_report = agent.analyze(stage="intraday_watch", dataset=dataset)
    post_market_report = agent.analyze(stage="post_market_review", dataset=dataset)

    assert pre_market_report.status == "passed"
    assert pre_market_report.missing_market_bar_count == 0
    assert intraday_report.status == "passed"
    assert intraday_report.missing_market_bar_count == 0
    assert post_market_report.status == "failed"
    assert post_market_report.missing_market_bar_count == 1
    assert post_market_report.issues[-1].metadata["missing_dates"] == ["2026-05-06"]


def test_pre_market_and_intraday_still_fail_when_previous_trade_date_bar_is_missing() -> None:
    trade_date = date(2026, 5, 6)
    previous_trade_date = date(2026, 5, 5)
    dataset = _daily_quality_dataset(
        trade_date=trade_date,
        bar_dates=[],
        calendar_dates=[previous_trade_date, trade_date],
    )
    agent = DataQualityAgent(required_data_sources={"market_bars"})

    pre_market_report = agent.analyze(stage="pre_market", dataset=dataset)
    intraday_report = agent.analyze(stage="intraday_watch", dataset=dataset)

    assert pre_market_report.status == "failed"
    assert pre_market_report.missing_market_bar_count == 1
    assert pre_market_report.issues[-1].metadata["missing_dates"] == ["2026-05-05"]
    assert intraday_report.status == "failed"
    assert intraday_report.missing_market_bar_count == 1
    assert intraday_report.issues[-1].metadata["missing_dates"] == ["2026-05-05"]


def test_pre_market_and_intraday_ignore_incomplete_current_day_daily_bar_quality() -> None:
    trade_date = date(2026, 5, 6)
    previous_trade_date = date(2026, 5, 5)
    dataset = _daily_quality_dataset(
        trade_date=trade_date,
        bar_dates=[previous_trade_date],
        calendar_dates=[previous_trade_date, trade_date],
    )
    dataset = MarketDataset(
        trade_date=dataset.trade_date,
        assets=dataset.assets,
        bars=[
            *dataset.bars,
            MarketBar(
                symbol="510300",
                trade_date=trade_date,
                open=Decimal("0"),
                high=Decimal("0"),
                low=Decimal("0"),
                close=Decimal("0"),
                volume=-1,
                amount=Decimal("-1"),
                source="test",
            ),
        ],
        announcements=dataset.announcements,
        news=dataset.news,
        policy_items=dataset.policy_items,
        industry_snapshots=dataset.industry_snapshots,
        source_snapshots=dataset.source_snapshots,
        trade_calendar=dataset.trade_calendar,
        trade_calendar_dates=dataset.trade_calendar_dates,
        trade_calendar_days=dataset.trade_calendar_days,
    )
    agent = DataQualityAgent(required_data_sources={"market_bars"})

    pre_market_report = agent.analyze(stage="pre_market", dataset=dataset)
    intraday_report = agent.analyze(stage="intraday_watch", dataset=dataset)
    post_market_report = agent.analyze(stage="post_market_review", dataset=dataset)

    assert pre_market_report.status == "passed"
    assert pre_market_report.abnormal_price_count == 0
    assert intraday_report.status == "passed"
    assert intraday_report.abnormal_price_count == 0
    assert post_market_report.status == "failed"
    assert post_market_report.abnormal_price_count >= 1


def test_pre_market_and_intraday_do_not_guess_previous_day_without_prior_calendar() -> None:
    trade_date = date(2026, 5, 6)
    dataset = _daily_quality_dataset(
        trade_date=trade_date,
        bar_dates=[trade_date],
        calendar_dates=[trade_date],
    )
    dataset = MarketDataset(
        trade_date=dataset.trade_date,
        assets=dataset.assets,
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=trade_date,
                open=Decimal("0"),
                high=Decimal("0"),
                low=Decimal("0"),
                close=Decimal("0"),
                volume=-1,
                amount=Decimal("-1"),
                source="test",
            )
        ],
        announcements=dataset.announcements,
        news=dataset.news,
        policy_items=dataset.policy_items,
        industry_snapshots=dataset.industry_snapshots,
        source_snapshots=dataset.source_snapshots,
        trade_calendar=dataset.trade_calendar,
        trade_calendar_dates=dataset.trade_calendar_dates,
        trade_calendar_days=dataset.trade_calendar_days,
    )
    agent = DataQualityAgent(required_data_sources={"market_bars"})

    pre_market_report = agent.analyze(stage="pre_market", dataset=dataset)
    intraday_report = agent.analyze(stage="intraday_watch", dataset=dataset)
    post_market_report = agent.analyze(stage="post_market_review", dataset=dataset)

    assert pre_market_report.status == "passed"
    assert pre_market_report.missing_market_bar_count == 0
    assert pre_market_report.abnormal_price_count == 0
    assert intraday_report.status == "passed"
    assert intraday_report.missing_market_bar_count == 0
    assert intraday_report.abnormal_price_count == 0
    assert post_market_report.status == "failed"
    assert post_market_report.missing_market_bar_count == 0
    assert post_market_report.abnormal_price_count >= 1

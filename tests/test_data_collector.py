from __future__ import annotations

from datetime import date

from ashare_agent.agents.data_collector import DataCollector
from ashare_agent.providers.base import DataProviderError
from ashare_agent.providers.mock import MockProvider


def test_data_collector_records_trade_calendar_snapshot() -> None:
    trade_date = date(2026, 4, 29)
    dataset = DataCollector(MockProvider()).collect(trade_date)

    calendar_snapshot = next(
        snapshot for snapshot in dataset.source_snapshots if snapshot.source == "trade_calendar"
    )

    assert calendar_snapshot.status == "success"
    assert calendar_snapshot.row_count > 0
    assert calendar_snapshot.metadata["includes_trade_date"] is True
    assert dataset.trade_calendar is not None
    assert dataset.trade_calendar.is_trade_date is True


def test_data_collector_keeps_required_source_failure_snapshot() -> None:
    class BrokenMarketProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30):  # type: ignore[no-untyped-def]
            raise DataProviderError("行情接口失败")

    trade_date = date(2026, 4, 29)
    dataset = DataCollector(BrokenMarketProvider()).collect(trade_date)

    market_snapshot = next(
        snapshot for snapshot in dataset.source_snapshots if snapshot.source == "market_bars"
    )

    assert market_snapshot.status == "failed"
    assert market_snapshot.failure_reason == "行情接口失败"

from __future__ import annotations

from datetime import date

from ashare_agent.agents.data_collector import DataCollector
from ashare_agent.domain import Asset, IntradayBar
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


def test_data_collector_expands_structured_trade_calendar_days() -> None:
    class SparseCalendarProvider(MockProvider):
        def __init__(self) -> None:
            super().__init__([Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")])

        def get_trade_calendar(self) -> list[date]:
            return [date(2026, 4, 27), date(2026, 4, 29)]

    dataset = DataCollector(SparseCalendarProvider()).collect(date(2026, 4, 28))

    assert [(row.calendar_date, row.is_trade_date) for row in dataset.trade_calendar_days] == [
        (date(2026, 4, 27), True),
        (date(2026, 4, 28), False),
        (date(2026, 4, 29), True),
    ]
    assert dataset.trade_calendar is not None
    assert dataset.trade_calendar.is_trade_date is False


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


def test_data_collector_records_intraday_source_metadata_for_missing_symbols() -> None:
    class PartialIntradayProvider(MockProvider):
        intraday_source = "akshare_em"
        intraday_timeout_seconds = 2.0
        intraday_retry_attempts = 3

        def get_intraday_bars(
            self,
            trade_date: date,
            symbols: list[str],
            period: str = "1",
        ) -> list[IntradayBar]:
            return [
                bar
                for bar in super().get_intraday_bars(trade_date, symbols, period)
                if bar.symbol == "510300"
            ]

    collection = DataCollector(PartialIntradayProvider()).collect_intraday_bars(
        date(2026, 4, 29),
        ["510300", "600000"],
    )

    assert collection.source_snapshot.status == "success"
    assert collection.source_snapshot.metadata["intraday_source"] == "akshare_em"
    assert collection.source_snapshot.metadata["requested_symbols"] == ["510300", "600000"]
    assert collection.source_snapshot.metadata["returned_symbols"] == ["510300"]
    assert collection.source_snapshot.metadata["missing_symbols"] == ["600000"]
    assert collection.source_snapshot.metadata["timeout_seconds"] == 2.0
    assert collection.source_snapshot.metadata["retry_attempts"] == 3


def test_data_collector_records_intraday_source_failure_metadata() -> None:
    class BrokenIntradayProvider(MockProvider):
        intraday_source = "akshare_em"
        intraday_timeout_seconds = 2.0
        intraday_retry_attempts = 3

        def get_intraday_bars(
            self,
            trade_date: date,
            symbols: list[str],
            period: str = "1",
        ) -> list[IntradayBar]:
            raise DataProviderError(
                "akshare_em 分钟线源不可用: symbol=510300 attempts=3 timeout=2.0",
                metadata={
                    "intraday_source": "akshare_em",
                    "failed_symbol": "510300",
                    "retry_attempts": 3,
                    "timeout_seconds": 2.0,
                },
            )

    collection = DataCollector(BrokenIntradayProvider()).collect_intraday_bars(
        date(2026, 4, 29),
        ["510300", "600000"],
    )

    assert collection.source_snapshot.status == "failed"
    assert collection.source_snapshot.metadata["intraday_source"] == "akshare_em"
    assert collection.source_snapshot.metadata["requested_symbols"] == ["510300", "600000"]
    assert collection.source_snapshot.metadata["failed_symbol"] == "510300"
    assert collection.source_snapshot.metadata["timeout_seconds"] == 2.0
    assert collection.source_snapshot.metadata["retry_attempts"] == 3

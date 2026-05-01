from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, TypeVar

from ashare_agent.domain import (
    IntradayBar,
    MarketDataset,
    SourceSnapshot,
    TradingCalendarDay,
    TradingCalendarSnapshot,
)
from ashare_agent.providers.base import DataProvider, DataProviderError

T = TypeVar("T")


@dataclass(frozen=True)
class TradeCalendarCollection:
    snapshot: TradingCalendarSnapshot | None
    dates: list[date]
    days: list[TradingCalendarDay]
    source_snapshot: SourceSnapshot


@dataclass(frozen=True)
class IntradayBarsCollection:
    bars: list[IntradayBar]
    source_snapshot: SourceSnapshot


class DataCollector:
    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def _collect(
        self,
        source_name: str,
        trade_date: date,
        loader: Callable[[], list[T]],
        snapshots: list[SourceSnapshot],
        metadata_builder: Callable[[list[T]], dict[str, Any]] | None = None,
    ) -> list[T]:
        try:
            rows = loader()
        except DataProviderError as exc:
            snapshots.append(
                SourceSnapshot(
                    source=source_name,
                    trade_date=trade_date,
                    status="failed",
                    failure_reason=str(exc),
                )
            )
            return []
        snapshots.append(
            SourceSnapshot(
                source=source_name,
                trade_date=trade_date,
                status="success",
                row_count=len(rows),
                metadata=metadata_builder(rows) if metadata_builder is not None else {},
            )
        )
        return rows

    def _trade_calendar_metadata(
        self,
        trade_date: date,
        calendar_dates: list[date],
    ) -> dict[str, Any]:
        if not calendar_dates:
            return {"includes_trade_date": False}
        ordered = sorted(calendar_dates)
        return {
            "calendar_start": ordered[0].isoformat(),
            "calendar_end": ordered[-1].isoformat(),
            "includes_trade_date": trade_date in set(ordered),
        }

    def _trade_calendar_snapshot(
        self,
        trade_date: date,
        calendar_dates: list[date],
    ) -> TradingCalendarSnapshot | None:
        if not calendar_dates:
            return None
        ordered = sorted(calendar_dates)
        return TradingCalendarSnapshot(
            trade_date=trade_date,
            is_trade_date=trade_date in set(ordered),
            row_count=len(ordered),
            source="trade_calendar",
            calendar_start=ordered[0],
            calendar_end=ordered[-1],
        )

    def _structured_trade_calendar_days(
        self,
        calendar_dates: list[date],
    ) -> list[TradingCalendarDay]:
        if not calendar_dates:
            return []
        trade_dates = set(calendar_dates)
        ordered = sorted(trade_dates)
        current = ordered[0]
        end = ordered[-1]
        days: list[TradingCalendarDay] = []
        while current <= end:
            days.append(
                TradingCalendarDay(
                    calendar_date=current,
                    is_trade_date=current in trade_dates,
                    source="trade_calendar",
                )
            )
            current += timedelta(days=1)
        return days

    def collect_trade_calendar(self, trade_date: date) -> TradeCalendarCollection:
        snapshots: list[SourceSnapshot] = []
        calendar_dates = self._collect(
            "trade_calendar",
            trade_date,
            self._provider.get_trade_calendar,
            snapshots,
            lambda rows: self._trade_calendar_metadata(trade_date, rows),
        )
        return TradeCalendarCollection(
            snapshot=self._trade_calendar_snapshot(trade_date, calendar_dates),
            dates=calendar_dates,
            days=self._structured_trade_calendar_days(calendar_dates),
            source_snapshot=snapshots[0],
        )

    def collect_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> IntradayBarsCollection:
        snapshots: list[SourceSnapshot] = []
        bars = self._collect(
            "intraday_bars",
            trade_date,
            lambda: self._provider.get_intraday_bars(trade_date, symbols, period),
            snapshots,
            lambda rows: {
                "requested_symbols": symbols,
                "returned_symbols": sorted({bar.symbol for bar in rows}),
                "period": period,
            },
        )
        return IntradayBarsCollection(bars=bars, source_snapshot=snapshots[0])

    def collect(self, trade_date: date, lookback_days: int = 30) -> MarketDataset:
        snapshots: list[SourceSnapshot] = []
        assets = self._collect("universe", trade_date, self._provider.get_universe, snapshots)
        bars = self._collect(
            "market_bars",
            trade_date,
            lambda: self._provider.get_market_bars(trade_date, lookback_days),
            snapshots,
        )
        announcements = self._collect(
            "announcements",
            trade_date,
            lambda: self._provider.get_announcements(trade_date),
            snapshots,
        )
        news = self._collect(
            "news",
            trade_date,
            lambda: self._provider.get_news(trade_date),
            snapshots,
        )
        policy_items = self._collect(
            "policy",
            trade_date,
            lambda: self._provider.get_policy_items(trade_date),
            snapshots,
        )
        industry = self._collect(
            "industry",
            trade_date,
            lambda: self._provider.get_industry_snapshots(trade_date),
            snapshots,
        )
        calendar_dates = self._collect(
            "trade_calendar",
            trade_date,
            self._provider.get_trade_calendar,
            snapshots,
            lambda rows: self._trade_calendar_metadata(trade_date, rows),
        )
        calendar_days = self._structured_trade_calendar_days(calendar_dates)
        return MarketDataset(
            trade_date=trade_date,
            assets=assets,
            bars=bars,
            announcements=announcements,
            news=news,
            policy_items=policy_items,
            industry_snapshots=industry,
            source_snapshots=snapshots,
            trade_calendar=self._trade_calendar_snapshot(trade_date, calendar_dates),
            trade_calendar_dates=calendar_dates,
            trade_calendar_days=calendar_days,
        )

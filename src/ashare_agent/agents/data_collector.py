from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import TypeVar

from ashare_agent.domain import MarketDataset, SourceSnapshot
from ashare_agent.providers.base import DataProvider, DataProviderError

T = TypeVar("T")


class DataCollector:
    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def _collect(
        self,
        source_name: str,
        trade_date: date,
        loader: Callable[[], list[T]],
        snapshots: list[SourceSnapshot],
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
            )
        )
        return rows

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
        return MarketDataset(
            trade_date=trade_date,
            assets=assets,
            bars=bars,
            announcements=announcements,
            news=news,
            policy_items=policy_items,
            industry_snapshots=industry,
            source_snapshots=snapshots,
        )

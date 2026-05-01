from __future__ import annotations

from datetime import date
from typing import Protocol

from ashare_agent.domain import (
    AnnouncementItem,
    Asset,
    IndustrySnapshot,
    IntradayBar,
    MarketBar,
    NewsItem,
    PolicyItem,
)


class DataProviderError(RuntimeError):
    """Raised when a provider cannot return trustworthy data."""


class DataProvider(Protocol):
    def get_universe(self) -> list[Asset]: ...

    def get_market_bars(self, trade_date: date, lookback_days: int) -> list[MarketBar]: ...

    def get_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> list[IntradayBar]: ...

    def get_announcements(self, trade_date: date) -> list[AnnouncementItem]: ...

    def get_news(self, trade_date: date) -> list[NewsItem]: ...

    def get_policy_items(self, trade_date: date) -> list[PolicyItem]: ...

    def get_industry_snapshots(self, trade_date: date) -> list[IndustrySnapshot]: ...

    def get_trade_calendar(self) -> list[date]: ...

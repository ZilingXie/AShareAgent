from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from ashare_agent.domain import (
    AnnouncementItem,
    Asset,
    IndustrySnapshot,
    MarketBar,
    NewsItem,
    PolicyItem,
)


class MockProvider:
    """Deterministic provider for tests and local pipeline replay."""

    def __init__(self, assets: list[Asset] | None = None) -> None:
        self._assets = assets or [
            Asset(symbol="510300", name="沪深300ETF", asset_type="ETF"),
            Asset(symbol="159915", name="创业板ETF", asset_type="ETF"),
            Asset(symbol="600000", name="浦发银行", asset_type="STOCK"),
        ]

    def get_universe(self) -> list[Asset]:
        return list(self._assets)

    def get_market_bars(self, trade_date: date, lookback_days: int = 30) -> list[MarketBar]:
        bars: list[MarketBar] = []
        for asset_index, asset in enumerate(self._assets):
            base = Decimal("3.00") + Decimal(asset_index) * Decimal("0.40")
            for idx in range(lookback_days):
                day = trade_date - timedelta(days=lookback_days - 1 - idx)
                drift = Decimal(idx) * (Decimal("0.018") - Decimal(asset_index) * Decimal("0.003"))
                close = base + drift
                bars.append(
                    MarketBar(
                        symbol=asset.symbol,
                        trade_date=day,
                        open=close - Decimal("0.01"),
                        high=close + Decimal("0.03"),
                        low=close - Decimal("0.03"),
                        close=close,
                        volume=1_000_000 + idx * 20_000 - asset_index * 30_000,
                        amount=(close * Decimal("1000000")).quantize(Decimal("0.01")),
                        source="mock",
                    )
                )
        return bars

    def get_announcements(self, trade_date: date) -> list[AnnouncementItem]:
        published_at = datetime.combine(trade_date, datetime.min.time()).replace(hour=8, minute=30)
        return [
            AnnouncementItem(
                symbol="510300",
                name="沪深300ETF",
                title="基金规模增长并提高分红比例的公告",
                category="重大事项",
                published_at=published_at,
                url="https://mock.local/notice/510300",
                source="mock",
                trade_date=trade_date,
            ),
            AnnouncementItem(
                symbol="600000",
                name="浦发银行",
                title="关于重大诉讼及风险提示的公告",
                category="风险提示",
                published_at=published_at,
                url="https://mock.local/notice/600000",
                source="mock",
                trade_date=trade_date,
            ),
        ]

    def get_news(self, trade_date: date) -> list[NewsItem]:
        published_at = datetime.combine(trade_date, datetime.min.time()).replace(hour=8)
        return [
            NewsItem(
                symbol="510300",
                title="宽基 ETF 成交额继续放大",
                content="市场资金继续流入核心宽基 ETF。",
                published_at=published_at,
                source="mock",
                url="https://mock.local/news/510300",
                trade_date=trade_date,
            )
        ]

    def get_policy_items(self, trade_date: date) -> list[PolicyItem]:
        published_at = datetime.combine(trade_date, datetime.min.time()).replace(hour=7, minute=30)
        return [
            PolicyItem(
                title="政策强调资本市场稳定发展",
                content="政策文本强调长期资金入市和市场稳定。",
                published_at=published_at,
                source="mock",
                trade_date=trade_date,
            )
        ]

    def get_industry_snapshots(self, trade_date: date) -> list[IndustrySnapshot]:
        return [
            IndustrySnapshot(
                industry="宽基指数",
                strength_score=0.72,
                source="mock",
                trade_date=trade_date,
                reasons=["成交额放大", "趋势改善"],
            ),
            IndustrySnapshot(
                industry="金融",
                strength_score=0.44,
                source="mock",
                trade_date=trade_date,
                reasons=["风险提示增加"],
            ),
        ]


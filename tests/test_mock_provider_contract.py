from __future__ import annotations

from datetime import date

from ashare_agent.providers.mock import MockProvider


def test_mock_provider_returns_standard_audit_models() -> None:
    provider = MockProvider()
    trade_date = date(2026, 4, 29)

    assets = provider.get_universe()
    bars = provider.get_market_bars(trade_date=trade_date, lookback_days=30)
    intraday_bars = provider.get_intraday_bars(trade_date=trade_date, symbols=["510300"])
    announcements = provider.get_announcements(trade_date=trade_date)
    news = provider.get_news(trade_date=trade_date)
    policy_items = provider.get_policy_items(trade_date=trade_date)
    industry_items = provider.get_industry_snapshots(trade_date=trade_date)
    trade_calendar = provider.get_trade_calendar()

    assert assets
    assert all(asset.asset_type in {"ETF", "STOCK"} for asset in assets)
    assert all(bar.source == "mock" and bar.collected_at is not None for bar in bars)
    assert intraday_bars
    assert intraday_bars[0].symbol == "510300"
    assert intraday_bars[0].timestamp.date() == trade_date
    assert intraday_bars[0].source == "mock_intraday"
    assert all(item.source == "mock" for item in announcements)
    assert all(item.source == "mock" for item in news)
    assert all(item.source == "mock" for item in policy_items)
    assert all(item.source == "mock" for item in industry_items)
    assert trade_date in trade_calendar
    assert {bar.symbol for bar in bars}.issubset({asset.symbol for asset in assets})

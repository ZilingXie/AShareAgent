from __future__ import annotations

import sys
from datetime import date
from types import ModuleType
from typing import Any

import pytest

from ashare_agent.domain import Asset
from ashare_agent.providers.akshare_provider import AKShareProvider
from ashare_agent.providers.base import DataProviderError


class FakeDataFrame:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def tail(self, count: int) -> FakeDataFrame:
        return FakeDataFrame(self._records[-count:])

    def to_dict(self, orient: str) -> list[dict[str, Any]]:
        assert orient == "records"
        return list(self._records)


def test_akshare_provider_returns_standard_audit_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fund_etf_hist_em(**kwargs: object) -> FakeDataFrame:
        assert kwargs["symbol"] == "510300"
        return FakeDataFrame(
            [
                {
                    "日期": "2026-04-28",
                    "开盘": "4.00",
                    "最高": "4.10",
                    "最低": "3.99",
                    "收盘": "4.05",
                    "成交量": 1000,
                    "成交额": "4050",
                },
                {
                    "日期": "2026-04-29",
                    "开盘": "4.05",
                    "最高": "4.20",
                    "最低": "4.01",
                    "收盘": "4.18",
                    "成交量": 1200,
                    "成交额": "5016",
                },
            ]
        )

    def stock_zh_a_hist(**kwargs: object) -> FakeDataFrame:
        assert kwargs["symbol"] == "600000"
        return FakeDataFrame(
            [
                {
                    "日期": "2026-04-29",
                    "开盘": "9.00",
                    "最高": "9.20",
                    "最低": "8.90",
                    "收盘": "9.10",
                    "成交量": 2000,
                    "成交额": "18200",
                }
            ]
        )

    def stock_notice_report(**kwargs: object) -> FakeDataFrame:
        return FakeDataFrame(
            [
                {
                    "代码": "510300",
                    "名称": "沪深300ETF",
                    "公告标题": "基金公告",
                    "公告类型": kwargs["symbol"],
                    "公告日期": "2026-04-29",
                    "网址": "https://example.test/notice",
                },
                {
                    "代码": "000001",
                    "名称": "平安银行",
                    "公告标题": "非池内公告",
                    "公告类型": kwargs["symbol"],
                    "公告日期": "2026-04-29",
                    "网址": "https://example.test/skip",
                },
            ]
        )

    def stock_news_em(**kwargs: object) -> FakeDataFrame:
        return FakeDataFrame(
            [
                {
                    "新闻标题": f"{kwargs['symbol']} 新闻",
                    "新闻内容": "公开新闻内容",
                    "发布时间": "2026-04-29 09:00:00",
                    "文章来源": "东方财富",
                    "新闻链接": "https://example.test/news",
                }
            ]
        )

    def news_cctv(**kwargs: object) -> FakeDataFrame:
        assert kwargs["date"] == "20260429"
        return FakeDataFrame(
            [{"date": "2026-04-29", "title": "政策标题", "content": "政策内容"}]
        )

    def tool_trade_date_hist_sina() -> FakeDataFrame:
        return FakeDataFrame([{"trade_date": "2026-04-28"}, {"trade_date": "2026-04-29"}])

    fake_akshare = ModuleType("akshare")
    fake_akshare.__dict__.update(
        {
            "fund_etf_hist_em": fund_etf_hist_em,
            "stock_zh_a_hist": stock_zh_a_hist,
            "stock_notice_report": stock_notice_report,
            "stock_news_em": stock_news_em,
            "news_cctv": news_cctv,
            "tool_trade_date_hist_sina": tool_trade_date_hist_sina,
        }
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    provider = AKShareProvider(
        [
            Asset(symbol="510300", name="沪深300ETF", asset_type="ETF"),
            Asset(symbol="600000", name="浦发银行", asset_type="STOCK"),
        ]
    )

    bars = provider.get_market_bars(date(2026, 4, 29), lookback_days=2)
    announcements = provider.get_announcements(date(2026, 4, 29))
    news = provider.get_news(date(2026, 4, 29))
    policy = provider.get_policy_items(date(2026, 4, 29))
    calendar = provider.get_trade_calendar()

    assert {bar.symbol for bar in bars} == {"510300", "600000"}
    assert all(bar.source == "akshare" for bar in bars)
    assert {item.symbol for item in announcements} == {"510300"}
    assert {item.symbol for item in news} == {"510300", "600000"}
    assert policy[0].source == "akshare_cctv"
    assert calendar == [date(2026, 4, 28), date(2026, 4, 29)]


def test_akshare_provider_wraps_market_bar_parse_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_fund_etf_hist_em(**kwargs: object) -> FakeDataFrame:
        assert kwargs["symbol"] == "510300"
        return FakeDataFrame([{"收盘": "4.18"}])

    fake_akshare = ModuleType("akshare")
    fake_akshare.__dict__.update(
        {
            "fund_etf_hist_em": broken_fund_etf_hist_em,
        }
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    provider = AKShareProvider([Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")])

    try:
        provider.get_market_bars(date(2026, 4, 29), lookback_days=1)
    except DataProviderError as exc:
        assert "行情解析失败" in str(exc)
    else:
        raise AssertionError("行情字段缺失必须包装成 DataProviderError")

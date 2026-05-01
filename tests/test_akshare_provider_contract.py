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
    def fund_etf_hist_sina(**kwargs: object) -> FakeDataFrame:
        assert kwargs["symbol"] == "sh510300"
        return FakeDataFrame(
            [
                {
                    "date": "2026-04-28",
                    "open": "4.00",
                    "high": "4.10",
                    "low": "3.99",
                    "close": "4.05",
                    "volume": 1000,
                    "amount": "4050",
                },
                {
                    "date": "2026-04-29",
                    "open": "4.05",
                    "high": "4.20",
                    "low": "4.01",
                    "close": "4.18",
                    "volume": 1200,
                    "amount": "5016",
                },
            ]
        )

    def stock_zh_a_daily(**kwargs: object) -> FakeDataFrame:
        assert kwargs["symbol"] == "sh600000"
        assert kwargs["start_date"] == "20250429"
        assert kwargs["end_date"] == "20260429"
        return FakeDataFrame(
            [
                {
                    "date": "2026-04-29",
                    "open": "9.00",
                    "high": "9.20",
                    "low": "8.90",
                    "close": "9.10",
                    "volume": 2000,
                    "amount": "18200",
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
            "fund_etf_hist_sina": fund_etf_hist_sina,
            "stock_zh_a_daily": stock_zh_a_daily,
            "stock_notice_report": stock_notice_report,
            "stock_news_em": stock_news_em,
            "news_cctv": news_cctv,
            "tool_trade_date_hist_sina": tool_trade_date_hist_sina,
        }
    )
    monkeypatch.setitem(sys.modules, "akshare", fake_akshare)
    _patch_eastmoney_intraday(
        monkeypatch,
        {
            "1.510300": [
                "2026-04-29 09:31,4.18,4.19,4.20,4.18,100,419,4.19",
            ],
            "1.600000": [
                "2026-04-29 09:31,9.10,9.11,9.12,9.09,200,1822,9.11",
            ],
        },
    )
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
    intraday_bars = provider.get_intraday_bars(
        date(2026, 4, 29),
        symbols=["510300", "600000"],
    )

    assert {bar.symbol for bar in bars} == {"510300", "600000"}
    assert all(bar.source == "akshare" for bar in bars)
    assert {bar.symbol for bar in intraday_bars} == {"510300", "600000"}
    assert all(bar.source == "akshare_em" for bar in intraday_bars)
    assert intraday_bars[0].timestamp.isoformat() == "2026-04-29T09:31:00"
    assert {item.symbol for item in announcements} == {"510300"}
    assert {item.symbol for item in news} == {"510300", "600000"}
    assert policy[0].source == "akshare_cctv"
    assert calendar == [date(2026, 4, 28), date(2026, 4, 29)]


def test_akshare_provider_wraps_market_bar_parse_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken_fund_etf_hist_sina(**kwargs: object) -> FakeDataFrame:
        assert kwargs["symbol"] == "sh510300"
        return FakeDataFrame([{"收盘": "4.18"}])

    fake_akshare = ModuleType("akshare")
    fake_akshare.__dict__.update(
        {
            "fund_etf_hist_sina": broken_fund_etf_hist_sina,
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


def test_akshare_provider_uses_direct_eastmoney_intraday_with_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, float, dict[str, str]]] = []

    def fake_get(url: str, *, timeout: float, params: dict[str, str]) -> object:
        calls.append((url, timeout, params))
        return FakeResponse(
            {
                "data": {
                    "trends": [
                        "2026-04-28 09:31,4.00,4.01,4.02,3.99,90,360,4.00",
                        "2026-04-29 09:31,4.18,4.19,4.20,4.18,100,419,4.19",
                    ]
                }
            }
        )

    monkeypatch.setattr("ashare_agent.providers.akshare_provider.requests.get", fake_get)
    provider = AKShareProvider(
        [Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        intraday_source="akshare_em",
        intraday_timeout_seconds=3.0,
        intraday_retry_attempts=2,
        intraday_retry_backoff_seconds=0,
    )

    bars = provider.get_intraday_bars(date(2026, 4, 29), ["510300"])

    assert len(bars) == 1
    assert bars[0].source == "akshare_em"
    assert bars[0].timestamp.isoformat() == "2026-04-29T09:31:00"
    assert calls[0][1] == 3.0
    assert calls[0][2]["secid"] == "1.510300"


def test_akshare_provider_retries_intraday_source_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def broken_get(url: str, *, timeout: float, params: dict[str, str]) -> object:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("RemoteDisconnected")

    def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("ashare_agent.providers.akshare_provider.requests.get", broken_get)
    monkeypatch.setattr("ashare_agent.providers.akshare_provider.sleep", no_sleep)
    provider = AKShareProvider(
        [Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        intraday_source="akshare_em",
        intraday_timeout_seconds=2.0,
        intraday_retry_attempts=3,
        intraday_retry_backoff_seconds=0.1,
    )

    with pytest.raises(DataProviderError) as caught:
        provider.get_intraday_bars(date(2026, 4, 29), ["510300"])

    message = str(caught.value)
    assert attempts == 3
    assert "akshare_em" in message
    assert "510300" in message
    assert "attempts=3" in message
    assert "timeout=2.0" in message
    assert "RemoteDisconnected" in message
    assert caught.value.metadata["failed_symbol"] == "510300"


def test_akshare_provider_returns_empty_intraday_when_symbol_has_no_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_eastmoney_intraday(monkeypatch, {"1.510300": []})
    provider = AKShareProvider(
        [Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
        intraday_source="akshare_em",
        intraday_retry_attempts=1,
    )

    assert provider.get_intraday_bars(date(2026, 4, 29), ["510300"]) == []


def test_akshare_provider_rejects_unknown_intraday_source() -> None:
    with pytest.raises(ValueError) as caught:
        AKShareProvider(
            [Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")],
            intraday_source="unknown",
        )

    assert "未知 ASHARE_INTRADAY_SOURCE" in str(caught.value)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _patch_eastmoney_intraday(
    monkeypatch: pytest.MonkeyPatch,
    trends_by_secid: dict[str, list[str]],
) -> None:
    def fake_get(url: str, *, timeout: float, params: dict[str, str]) -> FakeResponse:
        assert url == "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
        assert timeout > 0
        secid = params["secid"]
        return FakeResponse({"data": {"trends": trends_by_secid[secid]}})

    monkeypatch.setattr("ashare_agent.providers.akshare_provider.requests.get", fake_get)

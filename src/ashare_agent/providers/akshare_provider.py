from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from time import sleep
from typing import Any, cast

import requests  # type: ignore[import-untyped]

from ashare_agent.domain import (
    AnnouncementItem,
    Asset,
    IndustrySnapshot,
    IntradayBar,
    MarketBar,
    NewsItem,
    PolicyItem,
)
from ashare_agent.providers.base import DataProviderError

EASTMONEY_INTRADAY_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
SUPPORTED_INTRADAY_SOURCES = {"akshare_em"}


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DataProviderError(f"无法解析数值: {value}") from exc


def _parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).replace("-", "")
    return datetime.strptime(text[:8], "%Y%m%d").date()


def _parse_datetime(value: object, fallback_date: date) -> datetime:
    text = str(value)
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.combine(fallback_date, datetime.min.time())


def _symbol_text(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit() and len(text) < 6:
        return text.zfill(6)
    return text


def _exchange_symbol(symbol: str) -> str:
    if symbol.startswith(("5", "6", "9")):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _eastmoney_market_id(symbol: str) -> str:
    if symbol.startswith(("5", "6", "9")):
        return "1"
    return "0"


def _row_value(row: dict[str, object], *keys: str) -> object:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    raise KeyError(keys[0])


class AKShareProvider:
    """AKShare adapter. All failures are explicit provider errors."""

    def __init__(
        self,
        universe: list[Asset],
        *,
        intraday_source: str = "akshare_em",
        intraday_timeout_seconds: float = 15.0,
        intraday_retry_attempts: int = 3,
        intraday_retry_backoff_seconds: float = 0.5,
    ) -> None:
        if intraday_source not in SUPPORTED_INTRADAY_SOURCES:
            raise ValueError(f"未知 ASHARE_INTRADAY_SOURCE: {intraday_source}")
        if intraday_timeout_seconds <= 0:
            raise ValueError("ASHARE_INTRADAY_TIMEOUT_SECONDS 必须大于 0")
        if intraday_retry_attempts < 1:
            raise ValueError("ASHARE_INTRADAY_RETRY_ATTEMPTS 必须大于等于 1")
        if intraday_retry_backoff_seconds < 0:
            raise ValueError("ASHARE_INTRADAY_RETRY_BACKOFF_SECONDS 不能小于 0")
        self._universe = universe
        self.intraday_source = intraday_source
        self.intraday_timeout_seconds = intraday_timeout_seconds
        self.intraday_retry_attempts = intraday_retry_attempts
        self.intraday_retry_backoff_seconds = intraday_retry_backoff_seconds

    def _ak(self) -> Any:
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataProviderError("AKShare 未安装，无法获取真实公开数据") from exc
        return ak

    def get_universe(self) -> list[Asset]:
        return list(self._universe)

    def get_market_bars(self, trade_date: date, lookback_days: int = 30) -> list[MarketBar]:
        ak = self._ak()
        start_date = trade_date.replace(year=trade_date.year - 1).strftime("%Y%m%d")
        end_date = trade_date.strftime("%Y%m%d")
        bars: list[MarketBar] = []
        for asset in self._universe:
            try:
                market_symbol = _exchange_symbol(asset.symbol)
                if asset.asset_type == "ETF":
                    df = ak.fund_etf_hist_sina(symbol=market_symbol)
                else:
                    df = ak.stock_zh_a_daily(
                        symbol=market_symbol,
                        start_date=start_date,
                        end_date=end_date,
                        adjust="",
                    )
            except Exception as exc:  # noqa: BLE001
                raise DataProviderError(f"{asset.symbol} 行情获取失败: {exc}") from exc
            try:
                records = [
                    row
                    for row in df.to_dict("records")
                    if _parse_date(_row_value(row, "date", "日期")) <= trade_date
                ][-lookback_days:]
                if not records:
                    raise DataProviderError(f"{asset.symbol} 行情为空")
                for row in records:
                    bars.append(
                        MarketBar(
                            symbol=asset.symbol,
                            trade_date=_parse_date(_row_value(row, "date", "日期")),
                            open=_to_decimal(_row_value(row, "open", "开盘")),
                            high=_to_decimal(_row_value(row, "high", "最高")),
                            low=_to_decimal(_row_value(row, "low", "最低")),
                            close=_to_decimal(_row_value(row, "close", "收盘")),
                            volume=int(_to_decimal(_row_value(row, "volume", "成交量"))),
                            amount=_to_decimal(_row_value(row, "amount", "成交额")),
                            source="akshare",
                        )
                    )
            except DataProviderError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise DataProviderError(f"{asset.symbol} 行情解析失败: {exc}") from exc
        return bars

    def get_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> list[IntradayBar]:
        if period != "1":
            raise DataProviderError(
                f"{self.intraday_source} 分钟线源仅支持 period=1",
                metadata={
                    "intraday_source": self.intraday_source,
                    "period": period,
                },
            )
        assets_by_symbol = {asset.symbol: asset for asset in self._universe}
        bars: list[IntradayBar] = []
        for symbol in symbols:
            asset = assets_by_symbol.get(symbol)
            if asset is None:
                raise DataProviderError(f"{symbol} 不在 universe 中，无法获取分钟线")
            bars.extend(self._get_intraday_bars_akshare_em(trade_date, asset))
        return bars

    def _get_intraday_bars_akshare_em(self, trade_date: date, asset: Asset) -> list[IntradayBar]:
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "ndays": "5",
            "iscr": "0",
            "secid": f"{_eastmoney_market_id(asset.symbol)}.{asset.symbol}",
        }
        last_error = "unknown failure"
        for attempt in range(1, self.intraday_retry_attempts + 1):
            try:
                response = requests.get(
                    EASTMONEY_INTRADAY_URL,
                    timeout=self.intraday_timeout_seconds,
                    params=params,
                )
                response.raise_for_status()
                return self._parse_eastmoney_intraday_payload(
                    asset.symbol,
                    trade_date,
                    response.json(),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc) or exc.__class__.__name__
                if attempt < self.intraday_retry_attempts and (
                    self.intraday_retry_backoff_seconds > 0
                ):
                    sleep(self.intraday_retry_backoff_seconds)
        metadata = {
            "intraday_source": self.intraday_source,
            "failed_symbol": asset.symbol,
            "retry_attempts": self.intraday_retry_attempts,
            "timeout_seconds": self.intraday_timeout_seconds,
            "last_error": last_error,
        }
        raise DataProviderError(
            f"{self.intraday_source} 分钟线源不可用: "
            f"symbol={asset.symbol} "
            f"attempts={self.intraday_retry_attempts} "
            f"timeout={self.intraday_timeout_seconds} "
            f"last_error={last_error}",
            metadata=metadata,
        )

    def _parse_eastmoney_intraday_payload(
        self,
        symbol: str,
        trade_date: date,
        payload: object,
    ) -> list[IntradayBar]:
        if not isinstance(payload, Mapping):
            raise DataProviderError("EastMoney 分钟线响应必须是 JSON object")
        payload_map = cast(Mapping[str, object], payload)
        data = payload_map.get("data")
        if not isinstance(data, Mapping):
            raise DataProviderError("EastMoney 分钟线响应缺少 data object")
        data_map = cast(Mapping[str, object], data)
        trends = data_map.get("trends")
        if trends is None:
            raise DataProviderError("EastMoney 分钟线响应缺少 data.trends")
        if not isinstance(trends, list):
            raise DataProviderError("EastMoney 分钟线 data.trends 必须是 list")
        bars: list[IntradayBar] = []
        for raw_item in cast(list[object], trends):
            if not isinstance(raw_item, str):
                raise DataProviderError("EastMoney 分钟线 item 必须是 string")
            fields = raw_item.split(",")
            if len(fields) < 7:
                raise DataProviderError(f"EastMoney 分钟线字段不足: {raw_item}")
            timestamp = _parse_datetime(fields[0], trade_date)
            if timestamp.date() != trade_date:
                continue
            bars.append(
                IntradayBar(
                    symbol=symbol,
                    trade_date=trade_date,
                    timestamp=timestamp,
                    open=_to_decimal(fields[1]),
                    close=_to_decimal(fields[2]),
                    high=_to_decimal(fields[3]),
                    low=_to_decimal(fields[4]),
                    volume=int(_to_decimal(fields[5])),
                    amount=_to_decimal(fields[6]),
                    source=self.intraday_source,
                )
            )
        return bars

    def get_announcements(self, trade_date: date) -> list[AnnouncementItem]:
        ak = self._ak()
        results: list[AnnouncementItem] = []
        universe_symbols = {asset.symbol for asset in self._universe}
        notice_types = (
            "重大事项",
            "财务报告",
            "融资公告",
            "风险提示",
            "资产重组",
            "信息变更",
            "持股变动",
        )
        for symbol in notice_types:
            try:
                df = ak.stock_notice_report(symbol=symbol, date=trade_date.strftime("%Y%m%d"))
            except Exception as exc:  # noqa: BLE001
                raise DataProviderError(f"公告获取失败: {exc}") from exc
            for row in df.to_dict("records"):
                row_symbol = _symbol_text(row.get("代码", ""))
                if row_symbol not in universe_symbols:
                    continue
                results.append(
                    AnnouncementItem(
                        symbol=row_symbol,
                        name=str(row.get("名称", "")),
                        title=str(row.get("公告标题", "")),
                        category=str(row.get("公告类型", symbol)),
                        published_at=_parse_datetime(row.get("公告日期", ""), trade_date),
                        url=str(row.get("网址", "")),
                        source="akshare",
                        trade_date=trade_date,
                    )
                )
        return results

    def get_news(self, trade_date: date) -> list[NewsItem]:
        ak = self._ak()
        news: list[NewsItem] = []
        for asset in self._universe:
            try:
                df = ak.stock_news_em(symbol=asset.symbol)
            except Exception as exc:  # noqa: BLE001
                raise DataProviderError(f"{asset.symbol} 新闻获取失败: {exc}") from exc
            for row in df.to_dict("records"):
                news.append(
                    NewsItem(
                        symbol=asset.symbol,
                        title=str(row.get("新闻标题", "")),
                        content=str(row.get("新闻内容", "")),
                        published_at=_parse_datetime(row.get("发布时间", ""), trade_date),
                        source=str(row.get("文章来源", "akshare")),
                        url=str(row.get("新闻链接", "")),
                        trade_date=trade_date,
                    )
                )
        return news

    def get_policy_items(self, trade_date: date) -> list[PolicyItem]:
        ak = self._ak()
        try:
            df = ak.news_cctv(date=trade_date.strftime("%Y%m%d"))
        except Exception as exc:  # noqa: BLE001
            raise DataProviderError(f"政策/新闻联播文本获取失败: {exc}") from exc
        return [
            PolicyItem(
                title=str(row.get("title", "")),
                content=str(row.get("content", "")),
                published_at=_parse_datetime(row.get("date", ""), trade_date),
                source="akshare_cctv",
                trade_date=trade_date,
            )
            for row in df.to_dict("records")
        ]

    def get_industry_snapshots(self, trade_date: date) -> list[IndustrySnapshot]:
        # 免费公开源的行业强弱接口稳定性不一，第一版保留显式空结果。
        return [
            IndustrySnapshot(
                industry="公开源行业数据",
                strength_score=0.5,
                source="akshare",
                trade_date=trade_date,
                reasons=["第一版未启用行业真实强弱接口"],
            )
        ]

    def get_trade_calendar(self) -> list[date]:
        ak = self._ak()
        try:
            df = ak.tool_trade_date_hist_sina()
        except Exception as exc:  # noqa: BLE001
            raise DataProviderError(f"交易日历获取失败: {exc}") from exc
        try:
            dates = [_parse_date(row["trade_date"]) for row in df.to_dict("records")]
            if not dates:
                raise DataProviderError("交易日历为空")
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DataProviderError(f"交易日历解析失败: {exc}") from exc
        return sorted(dates)

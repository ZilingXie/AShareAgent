from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ashare_agent.agents.intraday_price_estimator import IntradayPriceEstimator
from ashare_agent.domain import IntradayBar, MarketBar


def _daily_bar(symbol: str, trade_date: date, close: Decimal) -> MarketBar:
    return MarketBar(
        symbol=symbol,
        trade_date=trade_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
        amount=close * Decimal("1000000"),
        source="test",
    )


def _minute_bar(
    symbol: str,
    *,
    timestamp: datetime,
    close: Decimal,
    high: Decimal | None = None,
    low: Decimal | None = None,
    volume: int = 1000,
    amount: Decimal | None = None,
) -> IntradayBar:
    return IntradayBar(
        symbol=symbol,
        trade_date=timestamp.date(),
        timestamp=timestamp,
        open=close,
        high=high or close,
        low=low or close,
        close=close,
        volume=volume,
        amount=amount if amount is not None else close * Decimal(volume),
        source="mock_intraday",
    )


def test_estimator_uses_first_valid_minute_and_dynamic_slippage_for_buy() -> None:
    trade_date = date(2026, 4, 29)
    estimator = IntradayPriceEstimator(
        base_slippage_pct=Decimal("0.001"),
        price_limit_pct=Decimal("0.098"),
    )

    estimate = estimator.estimate(
        symbol="510300",
        side="buy",
        trade_date=trade_date,
        intraday_bars=[
            _minute_bar(
                "510300",
                timestamp=datetime(2026, 4, 29, 9, 31),
                close=Decimal("10.00"),
                high=Decimal("10.10"),
                low=Decimal("9.90"),
            ),
            _minute_bar(
                "510300",
                timestamp=datetime(2026, 4, 29, 9, 32),
                close=Decimal("10.50"),
            ),
        ],
        daily_bars=[
            _daily_bar("510300", date(2026, 4, 28), Decimal("9.90")),
            _daily_bar("510300", trade_date, Decimal("10.20")),
        ],
    )

    assert estimate.status == "filled"
    assert estimate.reference_price == Decimal("10.00")
    assert estimate.slippage == Decimal("0.003")
    assert estimate.estimated_price == Decimal("10.0300")
    assert estimate.execution_source == "mock_intraday"
    assert estimate.execution_timestamp == datetime(2026, 4, 29, 9, 31)
    assert estimate.execution_method == "first_valid_1m_bar"
    assert estimate.used_daily_fallback is False


def test_estimator_rejects_when_intraday_bars_are_missing() -> None:
    trade_date = date(2026, 4, 29)
    estimate = IntradayPriceEstimator().estimate(
        symbol="510300",
        side="buy",
        trade_date=trade_date,
        intraday_bars=[],
        daily_bars=[_daily_bar("510300", date(2026, 4, 28), Decimal("10"))],
    )

    assert estimate.status == "rejected"
    assert estimate.failure_reason == "无分钟线，无法成交"
    assert estimate.used_daily_fallback is False


def test_estimator_rejects_suspended_symbol_without_valid_volume() -> None:
    trade_date = date(2026, 4, 29)
    estimate = IntradayPriceEstimator().estimate(
        symbol="510300",
        side="buy",
        trade_date=trade_date,
        intraday_bars=[
            _minute_bar(
                "510300",
                timestamp=datetime(2026, 4, 29, 9, 31),
                close=Decimal("10"),
                volume=0,
                amount=Decimal("0"),
            )
        ],
        daily_bars=[_daily_bar("510300", date(2026, 4, 28), Decimal("10"))],
    )

    assert estimate.status == "rejected"
    assert estimate.failure_reason == "停牌或分钟线无有效成交"


def test_estimator_rejects_side_specific_price_limits() -> None:
    trade_date = date(2026, 4, 29)
    estimator = IntradayPriceEstimator(price_limit_pct=Decimal("0.098"))

    buy = estimator.estimate(
        symbol="510300",
        side="buy",
        trade_date=trade_date,
        intraday_bars=[
            _minute_bar("510300", timestamp=datetime(2026, 4, 29, 9, 31), close=Decimal("10.98"))
        ],
        daily_bars=[_daily_bar("510300", date(2026, 4, 28), Decimal("10"))],
    )
    sell = estimator.estimate(
        symbol="159915",
        side="sell",
        trade_date=trade_date,
        intraday_bars=[
            _minute_bar("159915", timestamp=datetime(2026, 4, 29, 9, 31), close=Decimal("9.02"))
        ],
        daily_bars=[_daily_bar("159915", date(2026, 4, 28), Decimal("10"))],
    )

    assert buy.status == "rejected"
    assert buy.failure_reason == "涨停不可买入"
    assert sell.status == "rejected"
    assert sell.failure_reason == "跌停不可卖出"

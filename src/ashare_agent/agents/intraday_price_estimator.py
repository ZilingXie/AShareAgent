from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.domain import ExecutionEvent, IntradayBar, MarketBar, OrderSide


class IntradayPriceEstimator:
    def __init__(
        self,
        base_slippage_pct: Decimal = Decimal("0.001"),
        price_limit_pct: Decimal = Decimal("0.098"),
    ) -> None:
        self.base_slippage_pct = base_slippage_pct
        self.price_limit_pct = price_limit_pct

    def estimate(
        self,
        *,
        symbol: str,
        side: OrderSide,
        trade_date: date,
        intraday_bars: list[IntradayBar],
        daily_bars: list[MarketBar],
    ) -> ExecutionEvent:
        method = "first_valid_1m_bar"
        symbol_minutes = sorted(
            [
                bar
                for bar in intraday_bars
                if bar.symbol == symbol and bar.trade_date == trade_date
            ],
            key=lambda item: item.timestamp,
        )
        if not symbol_minutes:
            return self._rejected(symbol, trade_date, side, method, "无分钟线，无法成交")

        minute = next((bar for bar in symbol_minutes if self._is_valid_minute(bar)), None)
        if minute is None:
            return self._rejected(symbol, trade_date, side, method, "停牌或分钟线无有效成交")

        previous_close = self._previous_close(symbol, trade_date, daily_bars)
        if previous_close is None:
            return self._rejected(symbol, trade_date, side, method, "缺少前收盘价，无法判断涨跌停")

        reference_price = minute.close
        limit_up = previous_close * (Decimal("1") + self.price_limit_pct)
        limit_down = previous_close * (Decimal("1") - self.price_limit_pct)
        if side == "buy" and reference_price >= limit_up:
            return self._rejected(symbol, trade_date, side, method, "涨停不可买入")
        if side == "sell" and reference_price <= limit_down:
            return self._rejected(symbol, trade_date, side, method, "跌停不可卖出")

        slippage = self._slippage(minute)
        multiplier = Decimal("1") + slippage if side == "buy" else Decimal("1") - slippage
        estimated_price = (reference_price * multiplier).quantize(Decimal("0.0001"))
        return ExecutionEvent(
            symbol=symbol,
            trade_date=trade_date,
            side=side,
            status="filled",
            execution_method=method,
            used_daily_fallback=False,
            execution_source=minute.source,
            execution_timestamp=minute.timestamp,
            reference_price=reference_price,
            estimated_price=estimated_price,
            slippage=slippage,
        )

    def _rejected(
        self,
        symbol: str,
        trade_date: date,
        side: OrderSide,
        method: str,
        reason: str,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            symbol=symbol,
            trade_date=trade_date,
            side=side,
            status="rejected",
            execution_method=method,
            used_daily_fallback=False,
            failure_reason=reason,
        )

    def _is_valid_minute(self, bar: IntradayBar) -> bool:
        return (
            bar.open > 0
            and bar.high > 0
            and bar.low > 0
            and bar.close > 0
            and bar.volume > 0
            and bar.amount > 0
        )

    def _previous_close(
        self,
        symbol: str,
        trade_date: date,
        daily_bars: list[MarketBar],
    ) -> Decimal | None:
        previous = [
            bar.close
            for bar in sorted(daily_bars, key=lambda item: item.trade_date)
            if bar.symbol == symbol and bar.trade_date < trade_date
        ]
        return previous[-1] if previous else None

    def _slippage(self, bar: IntradayBar) -> Decimal:
        if bar.close <= 0:
            return self.base_slippage_pct
        environment = ((bar.high - bar.low) / bar.close) * Decimal("0.1")
        return self.base_slippage_pct + min(environment, Decimal("0.003"))

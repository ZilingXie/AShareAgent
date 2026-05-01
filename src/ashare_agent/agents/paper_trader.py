from __future__ import annotations

from datetime import date
from decimal import ROUND_DOWN, Decimal

from ashare_agent.agents.intraday_price_estimator import IntradayPriceEstimator
from ashare_agent.domain import (
    ExecutionEvent,
    ExitDecision,
    IntradayBar,
    MarketBar,
    PaperOrder,
    PaperPosition,
    PaperTradeResult,
    RiskDecision,
)


class PaperTrader:
    def __init__(
        self,
        initial_cash: Decimal = Decimal("100000"),
        position_size_pct: Decimal = Decimal("0.10"),
        slippage_pct: Decimal = Decimal("0.001"),
        price_limit_pct: Decimal = Decimal("0.098"),
    ) -> None:
        self.cash = initial_cash
        self.position_size_pct = position_size_pct
        self.slippage_pct = slippage_pct
        self.estimator = IntradayPriceEstimator(
            base_slippage_pct=slippage_pct,
            price_limit_pct=price_limit_pct,
        )
        self.positions: list[PaperPosition] = []
        self.orders: list[PaperOrder] = []

    def open_positions(self) -> list[PaperPosition]:
        return [position for position in self.positions if position.status == "open"]

    def apply_pre_market_decisions(
        self,
        trade_date: date,
        decisions: list[RiskDecision],
        bars: list[MarketBar],
        intraday_bars: list[IntradayBar],
        existing_orders: list[PaperOrder] | None = None,
    ) -> PaperTradeResult:
        latest_bars = {bar.symbol: bar for bar in sorted(bars, key=lambda item: item.trade_date)}
        new_orders: list[PaperOrder] = []
        execution_events: list[ExecutionEvent] = []
        open_symbols = {position.symbol for position in self.open_positions()}
        existing_order_keys = {
            (order.trade_date, order.symbol, order.side) for order in (existing_orders or [])
        }
        for decision in decisions:
            if not decision.approved or decision.signal_action != "paper_buy":
                continue
            if decision.symbol in open_symbols:
                continue
            if (trade_date, decision.symbol, "buy") in existing_order_keys:
                continue
            bar = latest_bars.get(decision.symbol)
            if bar is None:
                continue
            estimate = self.estimator.estimate(
                symbol=decision.symbol,
                side="buy",
                trade_date=trade_date,
                intraday_bars=intraday_bars,
                daily_bars=bars,
            )
            execution_events.append(estimate)
            if estimate.status != "filled" or estimate.estimated_price is None:
                continue
            target_pct = decision.target_position_pct or self.position_size_pct
            budget = self.cash * target_pct
            price = estimate.estimated_price
            quantity = int((budget / price).quantize(Decimal("1"), rounding=ROUND_DOWN))
            quantity = (quantity // 100) * 100
            if quantity <= 0:
                continue
            amount = (price * Decimal(quantity)).quantize(Decimal("0.01"))
            if amount > self.cash:
                continue
            order = PaperOrder(
                order_id=f"paper-{trade_date.isoformat()}-{decision.symbol}-buy",
                symbol=decision.symbol,
                trade_date=trade_date,
                side="buy",
                quantity=quantity,
                price=price,
                amount=amount,
                slippage=estimate.slippage or self.slippage_pct,
                reason=";".join(decision.reasons),
                is_real_trade=False,
                execution_source=estimate.execution_source,
                execution_timestamp=estimate.execution_timestamp,
                execution_method=estimate.execution_method,
                reference_price=estimate.reference_price,
                used_daily_fallback=estimate.used_daily_fallback,
                execution_failure_reason=estimate.failure_reason,
            )
            self.cash -= amount
            self.orders.append(order)
            new_orders.append(order)
            self.positions.append(
                PaperPosition(
                    symbol=decision.symbol,
                    opened_at=trade_date,
                    quantity=quantity,
                    entry_price=price,
                    current_price=bar.close,
                    status="open",
                )
            )
            open_symbols.add(decision.symbol)
        return PaperTradeResult(
            cash=self.cash,
            orders=new_orders,
            positions=list(self.positions),
            execution_events=execution_events,
        )

    def apply_exit_decisions(
        self,
        trade_date: date,
        decisions: list[ExitDecision],
        bars: list[MarketBar],
        intraday_bars: list[IntradayBar],
        existing_orders: list[PaperOrder] | None = None,
    ) -> PaperTradeResult:
        latest_bars = {bar.symbol: bar for bar in sorted(bars, key=lambda item: item.trade_date)}
        existing_order_keys = {
            (order.trade_date, order.symbol, order.side) for order in (existing_orders or [])
        }
        positions_by_symbol = {position.symbol: position for position in self.open_positions()}
        new_orders: list[PaperOrder] = []
        execution_events: list[ExecutionEvent] = []
        for decision in decisions:
            if not decision.approved or decision.exit_reason is None:
                continue
            if (trade_date, decision.symbol, "sell") in existing_order_keys:
                continue
            position = positions_by_symbol.get(decision.symbol)
            if position is None:
                continue
            bar = latest_bars.get(decision.symbol)
            if bar is None:
                continue
            estimate = self.estimator.estimate(
                symbol=decision.symbol,
                side="sell",
                trade_date=trade_date,
                intraday_bars=intraday_bars,
                daily_bars=bars,
            )
            execution_events.append(estimate)
            if estimate.status != "filled" or estimate.estimated_price is None:
                continue
            price = estimate.estimated_price
            amount = (price * Decimal(position.quantity)).quantize(Decimal("0.01"))
            order = PaperOrder(
                order_id=f"paper-{trade_date.isoformat()}-{decision.symbol}-sell",
                symbol=decision.symbol,
                trade_date=trade_date,
                side="sell",
                quantity=position.quantity,
                price=price,
                amount=amount,
                slippage=estimate.slippage or self.slippage_pct,
                reason=";".join(decision.reasons),
                is_real_trade=False,
                execution_source=estimate.execution_source,
                execution_timestamp=estimate.execution_timestamp,
                execution_method=estimate.execution_method,
                reference_price=estimate.reference_price,
                used_daily_fallback=estimate.used_daily_fallback,
                execution_failure_reason=estimate.failure_reason,
            )
            self.cash += amount
            position.current_price = bar.close
            position.status = "closed"
            position.closed_at = trade_date
            position.exit_price = price
            self.orders.append(order)
            new_orders.append(order)
            existing_order_keys.add((trade_date, decision.symbol, "sell"))
        return PaperTradeResult(
            cash=self.cash,
            orders=new_orders,
            positions=list(self.positions),
            execution_events=execution_events,
        )

    def mark_to_market(self, bars: list[MarketBar]) -> None:
        latest_bars = {bar.symbol: bar for bar in sorted(bars, key=lambda item: item.trade_date)}
        for position in self.open_positions():
            bar = latest_bars.get(position.symbol)
            if bar is not None:
                position.current_price = bar.close

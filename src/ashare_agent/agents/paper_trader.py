from __future__ import annotations

from datetime import date
from decimal import ROUND_DOWN, Decimal

from ashare_agent.domain import (
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
    ) -> None:
        self.cash = initial_cash
        self.position_size_pct = position_size_pct
        self.slippage_pct = slippage_pct
        self.positions: list[PaperPosition] = []
        self.orders: list[PaperOrder] = []

    def open_positions(self) -> list[PaperPosition]:
        return [position for position in self.positions if position.status == "open"]

    def apply_pre_market_decisions(
        self,
        trade_date: date,
        decisions: list[RiskDecision],
        bars: list[MarketBar],
    ) -> PaperTradeResult:
        latest_bars = {bar.symbol: bar for bar in sorted(bars, key=lambda item: item.trade_date)}
        new_orders: list[PaperOrder] = []
        for decision in decisions:
            if not decision.approved or decision.signal_action != "paper_buy":
                continue
            bar = latest_bars.get(decision.symbol)
            if bar is None:
                continue
            target_pct = decision.target_position_pct or self.position_size_pct
            budget = self.cash * target_pct
            price = (bar.close * (Decimal("1") + self.slippage_pct)).quantize(Decimal("0.0001"))
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
                slippage=self.slippage_pct,
                reason=";".join(decision.reasons),
                is_real_trade=False,
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
        return PaperTradeResult(cash=self.cash, orders=new_orders, positions=self.open_positions())

    def mark_to_market(self, bars: list[MarketBar]) -> None:
        latest_bars = {bar.symbol: bar for bar in sorted(bars, key=lambda item: item.trade_date)}
        for position in self.open_positions():
            bar = latest_bars.get(position.symbol)
            if bar is not None:
                position.current_price = bar.close

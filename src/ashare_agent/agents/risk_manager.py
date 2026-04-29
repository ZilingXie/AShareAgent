from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.domain import PaperPosition, RiskDecision, Signal


class RiskManager:
    def __init__(
        self,
        max_positions: int = 5,
        target_position_pct: Decimal = Decimal("0.10"),
        blacklist: set[str] | None = None,
        min_cash: Decimal = Decimal("100"),
    ) -> None:
        self._max_positions = max_positions
        self._target_position_pct = target_position_pct
        self._blacklist = blacklist or set()
        self._min_cash = min_cash

    def evaluate(
        self,
        trade_date: date,
        signals: list[Signal],
        open_positions: list[PaperPosition],
        cash: Decimal,
    ) -> list[RiskDecision]:
        decisions: list[RiskDecision] = []
        open_symbols = {position.symbol for position in open_positions if position.status == "open"}
        for signal in signals:
            reasons: list[str] = []
            if signal.symbol in self._blacklist:
                reasons.append("黑名单过滤")
            if signal.symbol in open_symbols:
                reasons.append("已有持仓，避免重复买入")
            if len(open_positions) >= self._max_positions:
                reasons.append("持仓数量已达上限")
            if cash <= self._min_cash:
                reasons.append("可用现金不足")
            approved = not reasons
            decisions.append(
                RiskDecision(
                    symbol=signal.symbol,
                    trade_date=trade_date,
                    signal_action=signal.action,
                    approved=approved,
                    reasons=reasons or ["通过"],
                    target_position_pct=self._target_position_pct if approved else Decimal("0"),
                )
            )
        return decisions


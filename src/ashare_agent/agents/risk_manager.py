from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.domain import (
    ExitDecision,
    ExitReason,
    MarketBar,
    PaperPosition,
    RiskDecision,
    Signal,
    TechnicalIndicator,
)


def _latest_bars_by_symbol(bars: list[MarketBar]) -> dict[str, list[MarketBar]]:
    grouped: dict[str, list[MarketBar]] = {}
    for bar in bars:
        grouped.setdefault(bar.symbol, []).append(bar)
    return {
        symbol: sorted(rows, key=lambda item: item.trade_date)
        for symbol, rows in grouped.items()
    }


def _elapsed_trade_days(opened_at: date, trade_date: date, trade_calendar: list[date]) -> int:
    if trade_date <= opened_at:
        return 0
    calendar = sorted(set(trade_calendar))
    if not calendar:
        return (trade_date - opened_at).days
    return len([item for item in calendar if opened_at < item <= trade_date])


class RiskManager:
    def __init__(
        self,
        max_positions: int = 5,
        target_position_pct: Decimal = Decimal("0.10"),
        blacklist: set[str] | None = None,
        min_cash: Decimal = Decimal("100"),
        max_daily_loss_pct: Decimal = Decimal("0.02"),
        stop_loss_pct: Decimal = Decimal("0.05"),
        price_limit_pct: Decimal = Decimal("0.098"),
        min_holding_trade_days: int = 2,
        max_holding_trade_days: int = 10,
    ) -> None:
        self._max_positions = max_positions
        self._target_position_pct = target_position_pct
        self._blacklist = blacklist or set()
        self._min_cash = min_cash
        self._max_daily_loss_pct = max_daily_loss_pct
        self._stop_loss_pct = stop_loss_pct
        self._price_limit_pct = price_limit_pct
        self._min_holding_trade_days = min_holding_trade_days
        self._max_holding_trade_days = max_holding_trade_days

    def evaluate(
        self,
        trade_date: date,
        signals: list[Signal],
        open_positions: list[PaperPosition],
        cash: Decimal,
        bars: list[MarketBar] | None = None,
        previous_total_value: Decimal | None = None,
        current_total_value: Decimal | None = None,
    ) -> list[RiskDecision]:
        decisions: list[RiskDecision] = []
        open_symbols = {position.symbol for position in open_positions if position.status == "open"}
        bars_by_symbol = _latest_bars_by_symbol(bars or [])
        daily_loss_triggered = False
        if (
            previous_total_value is not None
            and current_total_value is not None
            and previous_total_value > 0
        ):
            loss_pct = (previous_total_value - current_total_value) / previous_total_value
            daily_loss_triggered = loss_pct >= self._max_daily_loss_pct
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
            if daily_loss_triggered:
                reasons.append("单日最大亏损超过 2%")
            if bars is not None:
                symbol_bars = bars_by_symbol.get(signal.symbol, [])
                if len(symbol_bars) < 2:
                    reasons.append("行情数据不足")
                else:
                    previous_close = symbol_bars[-2].close
                    latest_close = symbol_bars[-1].close
                    if previous_close <= 0:
                        reasons.append("行情数据不足")
                    else:
                        return_pct = (latest_close - previous_close) / previous_close
                        if return_pct >= self._price_limit_pct:
                            reasons.append("接近涨停，不买入")
                        elif return_pct <= -self._price_limit_pct:
                            reasons.append("接近跌停，不买入")
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

    def evaluate_exits(
        self,
        trade_date: date,
        open_positions: list[PaperPosition],
        indicators: list[TechnicalIndicator],
        trade_calendar: list[date],
    ) -> list[ExitDecision]:
        indicators_by_symbol = {indicator.symbol: indicator for indicator in indicators}
        decisions: list[ExitDecision] = []
        for position in open_positions:
            elapsed_days = _elapsed_trade_days(position.opened_at, trade_date, trade_calendar)
            if elapsed_days < 1:
                decisions.append(
                    ExitDecision(
                        symbol=position.symbol,
                        trade_date=trade_date,
                        approved=False,
                        reasons=["T+1 限制，不能当日卖出"],
                    )
                )
                continue

            stop_price = position.entry_price * (Decimal("1") - self._stop_loss_pct)
            if position.current_price <= stop_price:
                decisions.append(
                    ExitDecision(
                        symbol=position.symbol,
                        trade_date=trade_date,
                        approved=True,
                        exit_reason="stop_loss",
                        reasons=["触发止损"],
                    )
                )
                continue

            if elapsed_days < self._min_holding_trade_days:
                decisions.append(
                    ExitDecision(
                        symbol=position.symbol,
                        trade_date=trade_date,
                        approved=False,
                        reasons=[f"未满足最少持有 {self._min_holding_trade_days} 个交易日"],
                    )
                )
                continue

            exit_reason: ExitReason | None = None
            reasons: list[str] = []
            indicator = indicators_by_symbol.get(position.symbol)
            if indicator is not None and not indicator.close_above_ma5 and indicator.return_5d < 0:
                exit_reason = "trend_weakness"
                reasons.append("趋势走弱卖出")
            if elapsed_days >= self._max_holding_trade_days:
                exit_reason = "max_holding_days"
                reasons = [f"持有满 {self._max_holding_trade_days} 个交易日到期卖出"]

            decisions.append(
                ExitDecision(
                    symbol=position.symbol,
                    trade_date=trade_date,
                    approved=exit_reason is not None,
                    exit_reason=exit_reason,
                    reasons=reasons or ["继续持有"],
                )
            )
        return decisions

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.domain import PaperPosition, PortfolioSnapshot, ReviewReport


class ReviewAgent:
    def review(
        self,
        trade_date: date,
        cash: Decimal,
        positions: list[PaperPosition],
    ) -> tuple[PortfolioSnapshot, ReviewReport]:
        market_value = sum((position.market_value for position in positions), Decimal("0"))
        total_value = cash + market_value
        snapshot = PortfolioSnapshot(
            trade_date=trade_date,
            cash=cash,
            market_value=market_value,
            total_value=total_value,
            open_positions=len([position for position in positions if position.status == "open"]),
        )
        attribution = [
            f"{position.symbol}: 当前价 {position.current_price}, 成本 {position.entry_price}"
            for position in positions
        ]
        report = ReviewReport(
            trade_date=trade_date,
            summary=f"模拟账户总资产 {total_value:.2f}，开放持仓 {snapshot.open_positions} 个。",
            stats={
                "cash": float(cash),
                "market_value": float(market_value),
                "total_value": float(total_value),
                "open_positions": float(snapshot.open_positions),
            },
            attribution=attribution or ["当日无开放持仓"],
            parameter_suggestions=["继续观察固定参数表现，暂不自动调整策略。"],
        )
        return snapshot, report


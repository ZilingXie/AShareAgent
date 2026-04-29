from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.agents.risk_manager import RiskManager
from ashare_agent.domain import PaperPosition, Signal


def test_risk_manager_rejects_when_max_positions_reached() -> None:
    trade_date = date(2026, 4, 29)
    signal = Signal(
        symbol="510300",
        trade_date=trade_date,
        action="paper_buy",
        score=0.82,
        score_breakdown={"technical": 0.4},
        reasons=["测试信号"],
    )
    positions = [
        PaperPosition(
            symbol=f"51030{idx}",
            opened_at=trade_date,
            quantity=100,
            entry_price=Decimal("1.00"),
            current_price=Decimal("1.00"),
            status="open",
        )
        for idx in range(5)
    ]

    decisions = RiskManager(max_positions=5).evaluate(
        trade_date=trade_date,
        signals=[signal],
        open_positions=positions,
        cash=Decimal("100000"),
    )

    assert len(decisions) == 1
    assert decisions[0].approved is False
    assert "持仓数量已达上限" in decisions[0].reasons


from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.agents.paper_trader import PaperTrader
from ashare_agent.domain import MarketBar, RiskDecision


def test_paper_trader_executes_only_approved_paper_buy() -> None:
    trade_date = date(2026, 4, 29)
    trader = PaperTrader(initial_cash=Decimal("100000"), position_size_pct=Decimal("0.10"))
    decision = RiskDecision(
        symbol="510300",
        trade_date=trade_date,
        signal_action="paper_buy",
        approved=True,
        reasons=["通过"],
        target_position_pct=Decimal("0.10"),
    )
    bar = MarketBar(
        symbol="510300",
        trade_date=trade_date,
        open=Decimal("4.00"),
        high=Decimal("4.20"),
        low=Decimal("3.90"),
        close=Decimal("4.10"),
        volume=10_000_000,
        amount=Decimal("41000000"),
        source="mock",
    )

    result = trader.apply_pre_market_decisions(
        trade_date=trade_date,
        decisions=[decision],
        bars=[bar],
    )

    assert result.orders[0].side == "buy"
    assert result.orders[0].is_real_trade is False
    assert result.positions[0].symbol == "510300"
    assert result.cash < Decimal("100000")


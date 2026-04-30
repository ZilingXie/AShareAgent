from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.agents.paper_trader import PaperTrader
from ashare_agent.domain import ExitDecision, MarketBar, PaperOrder, PaperPosition, RiskDecision


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


def test_paper_trader_executes_sell_and_closes_position() -> None:
    trade_date = date(2026, 4, 30)
    trader = PaperTrader(initial_cash=Decimal("90000"), slippage_pct=Decimal("0.001"))
    trader.positions = [
        PaperPosition(
            symbol="510300",
            opened_at=date(2026, 4, 29),
            quantity=100,
            entry_price=Decimal("100"),
            current_price=Decimal("96"),
            status="open",
        )
    ]

    result = trader.apply_exit_decisions(
        trade_date=trade_date,
        decisions=[
            ExitDecision(
                symbol="510300",
                trade_date=trade_date,
                approved=True,
                exit_reason="stop_loss",
                reasons=["触发止损"],
            )
        ],
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=trade_date,
                open=Decimal("96"),
                high=Decimal("96"),
                low=Decimal("96"),
                close=Decimal("96"),
                volume=1_000_000,
                amount=Decimal("96000000"),
                source="test",
            )
        ],
    )

    order = result.orders[0]
    position = result.positions[0]
    assert order.side == "sell"
    assert order.is_real_trade is False
    assert trader.cash > Decimal("90000")
    assert position.status == "closed"
    assert position.closed_at == trade_date
    assert position.exit_price == order.price


def test_paper_trader_does_not_repeat_same_day_sell_order() -> None:
    trade_date = date(2026, 4, 30)
    trader = PaperTrader(initial_cash=Decimal("90000"))
    trader.positions = [
        PaperPosition(
            symbol="510300",
            opened_at=date(2026, 4, 29),
            quantity=100,
            entry_price=Decimal("100"),
            current_price=Decimal("96"),
            status="open",
        )
    ]
    existing_order = PaperOrder(
        order_id="paper-2026-04-30-510300-sell",
        symbol="510300",
        trade_date=trade_date,
        side="sell",
        quantity=100,
        price=Decimal("95"),
        amount=Decimal("9500"),
        slippage=Decimal("0.001"),
        reason="触发止损",
    )

    result = trader.apply_exit_decisions(
        trade_date=trade_date,
        decisions=[
            ExitDecision(
                symbol="510300",
                trade_date=trade_date,
                approved=True,
                exit_reason="stop_loss",
                reasons=["触发止损"],
            )
        ],
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=trade_date,
                open=Decimal("96"),
                high=Decimal("96"),
                low=Decimal("96"),
                close=Decimal("96"),
                volume=1_000_000,
                amount=Decimal("96000000"),
                source="test",
            )
        ],
        existing_orders=[existing_order],
    )

    assert result.orders == []
    assert trader.positions[0].status == "open"

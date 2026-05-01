from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ashare_agent.agents.paper_trader import PaperTrader
from ashare_agent.domain import (
    ExitDecision,
    IntradayBar,
    MarketBar,
    PaperOrder,
    PaperPosition,
    RiskDecision,
)


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
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=date(2026, 4, 28),
                open=Decimal("4.00"),
                high=Decimal("4.00"),
                low=Decimal("4.00"),
                close=Decimal("4.00"),
                volume=10_000_000,
                amount=Decimal("40000000"),
                source="mock",
            ),
            bar,
        ],
        intraday_bars=[
            IntradayBar(
                symbol="510300",
                trade_date=trade_date,
                timestamp=datetime(2026, 4, 29, 9, 31),
                open=Decimal("4.11"),
                high=Decimal("4.14"),
                low=Decimal("4.10"),
                close=Decimal("4.12"),
                volume=1000,
                amount=Decimal("4120"),
                source="mock_intraday",
            )
        ],
    )

    assert result.orders[0].side == "buy"
    assert result.orders[0].is_real_trade is False
    assert result.orders[0].execution_source == "mock_intraday"
    assert result.orders[0].execution_timestamp == datetime(2026, 4, 29, 9, 31)
    assert result.orders[0].execution_method == "first_valid_1m_bar"
    assert result.orders[0].used_daily_fallback is False
    assert result.execution_events[0].status == "filled"
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
                trade_date=date(2026, 4, 29),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=1_000_000,
                amount=Decimal("100000000"),
                source="test",
            ),
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
        intraday_bars=[
            IntradayBar(
                symbol="510300",
                trade_date=trade_date,
                timestamp=datetime(2026, 4, 30, 9, 31),
                open=Decimal("96"),
                high=Decimal("96"),
                low=Decimal("96"),
                close=Decimal("96"),
                volume=1_000,
                amount=Decimal("96000"),
                source="mock_intraday",
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
    assert result.execution_events[0].status == "filled"


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
                trade_date=date(2026, 4, 29),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=1_000_000,
                amount=Decimal("100000000"),
                source="test",
            ),
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
        intraday_bars=[
            IntradayBar(
                symbol="510300",
                trade_date=trade_date,
                timestamp=datetime(2026, 4, 30, 9, 31),
                open=Decimal("96"),
                high=Decimal("96"),
                low=Decimal("96"),
                close=Decimal("96"),
                volume=1_000,
                amount=Decimal("96000"),
                source="mock_intraday",
            )
        ],
        existing_orders=[existing_order],
    )

    assert result.orders == []
    assert trader.positions[0].status == "open"


def test_paper_trader_rejects_buy_without_intraday_bar_and_does_not_change_state() -> None:
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

    result = trader.apply_pre_market_decisions(
        trade_date=trade_date,
        decisions=[decision],
        bars=[
            MarketBar(
                symbol="510300",
                trade_date=date(2026, 4, 28),
                open=Decimal("4.00"),
                high=Decimal("4.00"),
                low=Decimal("4.00"),
                close=Decimal("4.00"),
                volume=1_000_000,
                amount=Decimal("4000000"),
                source="test",
            )
        ],
        intraday_bars=[],
    )

    assert result.orders == []
    assert result.positions == []
    assert result.cash == Decimal("100000")
    assert result.execution_events[0].status == "rejected"
    assert result.execution_events[0].failure_reason == "无分钟线，无法成交"

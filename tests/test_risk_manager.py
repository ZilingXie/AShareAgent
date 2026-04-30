from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ashare_agent.agents.risk_manager import RiskManager
from ashare_agent.domain import MarketBar, PaperPosition, Signal, TechnicalIndicator


def _signal(symbol: str = "510300", trade_date: date = date(2026, 4, 29)) -> Signal:
    return Signal(
        symbol=symbol,
        trade_date=trade_date,
        action="paper_buy",
        score=0.82,
        score_breakdown={"technical": 0.4},
        reasons=["测试信号"],
    )


def _position(
    *,
    opened_at: date,
    current_price: Decimal = Decimal("100"),
    entry_price: Decimal = Decimal("100"),
    symbol: str = "510300",
) -> PaperPosition:
    return PaperPosition(
        symbol=symbol,
        opened_at=opened_at,
        quantity=100,
        entry_price=entry_price,
        current_price=current_price,
        status="open",
    )


def _bar(symbol: str, trade_date: date, close: Decimal) -> MarketBar:
    return MarketBar(
        symbol=symbol,
        trade_date=trade_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
        amount=close * Decimal("1000000"),
        source="test",
    )


def _weak_indicator(symbol: str, trade_date: date) -> TechnicalIndicator:
    return TechnicalIndicator(
        symbol=symbol,
        trade_date=trade_date,
        close_above_ma5=False,
        close_above_ma20=False,
        return_5d=-0.03,
        return_20d=-0.02,
        volume_ratio=1.0,
    )


def test_risk_manager_rejects_when_max_positions_reached() -> None:
    trade_date = date(2026, 4, 29)
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
        signals=[_signal(trade_date=trade_date)],
        open_positions=positions,
        cash=Decimal("100000"),
    )

    assert len(decisions) == 1
    assert decisions[0].approved is False
    assert "持仓数量已达上限" in decisions[0].reasons


def test_risk_manager_rejects_buy_near_price_limit() -> None:
    trade_date = date(2026, 4, 29)

    decisions = RiskManager().evaluate(
        trade_date=trade_date,
        signals=[_signal(trade_date=trade_date)],
        open_positions=[],
        cash=Decimal("100000"),
        bars=[
            _bar("510300", trade_date - timedelta(days=1), Decimal("10")),
            _bar("510300", trade_date, Decimal("10.98")),
        ],
    )

    assert decisions[0].approved is False
    assert "接近涨停，不买入" in decisions[0].reasons


def test_risk_manager_rejects_buy_after_daily_account_loss() -> None:
    trade_date = date(2026, 4, 29)

    decisions = RiskManager(max_daily_loss_pct=Decimal("0.02")).evaluate(
        trade_date=trade_date,
        signals=[_signal(trade_date=trade_date)],
        open_positions=[],
        cash=Decimal("97000"),
        bars=[
            _bar("510300", trade_date - timedelta(days=1), Decimal("10")),
            _bar("510300", trade_date, Decimal("10.05")),
        ],
        previous_total_value=Decimal("100000"),
        current_total_value=Decimal("97000"),
    )

    assert decisions[0].approved is False
    assert "单日最大亏损超过 2%" in decisions[0].reasons


def test_risk_manager_rejects_exit_on_t_plus_one_hard_limit() -> None:
    trade_date = date(2026, 4, 29)
    decisions = RiskManager().evaluate_exits(
        trade_date=trade_date,
        open_positions=[
            _position(opened_at=trade_date, current_price=Decimal("94"), entry_price=Decimal("100"))
        ],
        indicators=[_weak_indicator("510300", trade_date)],
        trade_calendar=[trade_date],
    )

    assert decisions[0].approved is False
    assert "T+1 限制，不能当日卖出" in decisions[0].reasons


def test_risk_manager_rejects_trend_exit_before_min_holding_days() -> None:
    opened_at = date(2026, 4, 29)
    trade_date = date(2026, 4, 30)

    decisions = RiskManager(min_holding_trade_days=2).evaluate_exits(
        trade_date=trade_date,
        open_positions=[_position(opened_at=opened_at, current_price=Decimal("99"))],
        indicators=[_weak_indicator("510300", trade_date)],
        trade_calendar=[opened_at, trade_date],
    )

    assert decisions[0].approved is False
    assert "未满足最少持有 2 个交易日" in decisions[0].reasons


def test_risk_manager_allows_stop_loss_after_t_plus_one_before_min_holding_days() -> None:
    opened_at = date(2026, 4, 29)
    trade_date = date(2026, 4, 30)

    decisions = RiskManager(stop_loss_pct=Decimal("0.05"), min_holding_trade_days=2).evaluate_exits(
        trade_date=trade_date,
        open_positions=[
            _position(opened_at=opened_at, current_price=Decimal("94"), entry_price=Decimal("100"))
        ],
        indicators=[_weak_indicator("510300", trade_date)],
        trade_calendar=[opened_at, trade_date],
    )

    assert decisions[0].approved is True
    assert decisions[0].exit_reason == "stop_loss"
    assert "触发止损" in decisions[0].reasons


def test_risk_manager_allows_trend_weakness_after_min_holding_days() -> None:
    opened_at = date(2026, 4, 29)
    trade_date = date(2026, 5, 1)

    decisions = RiskManager(min_holding_trade_days=2).evaluate_exits(
        trade_date=trade_date,
        open_positions=[_position(opened_at=opened_at, current_price=Decimal("99"))],
        indicators=[_weak_indicator("510300", trade_date)],
        trade_calendar=[opened_at, date(2026, 4, 30), trade_date],
    )

    assert decisions[0].approved is True
    assert decisions[0].exit_reason == "trend_weakness"
    assert "趋势走弱卖出" in decisions[0].reasons


def test_risk_manager_allows_exit_after_max_holding_days() -> None:
    opened_at = date(2026, 4, 1)
    trade_date = date(2026, 4, 11)
    calendar = [opened_at + timedelta(days=idx) for idx in range(11)]

    decisions = RiskManager(max_holding_trade_days=10).evaluate_exits(
        trade_date=trade_date,
        open_positions=[_position(opened_at=opened_at, current_price=Decimal("101"))],
        indicators=[],
        trade_calendar=calendar,
    )

    assert decisions[0].approved is True
    assert decisions[0].exit_reason == "max_holding_days"
    assert "持有满 10 个交易日到期卖出" in decisions[0].reasons

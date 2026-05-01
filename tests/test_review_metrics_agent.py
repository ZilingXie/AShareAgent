from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ashare_agent.agents.review_metrics_agent import ReviewMetricsAgent
from ashare_agent.domain import PaperOrder, PaperPosition, PipelineRunContext, PortfolioSnapshot
from ashare_agent.repository import InMemoryRepository


class RawPayloadRepository(InMemoryRepository):
    def save_raw_payload(
        self,
        table_name: str,
        context: PipelineRunContext,
        symbol: str | None,
        payload: dict[str, Any],
    ) -> None:
        self._save_payload(table_name, context.run_id, context.trade_date, symbol, payload)


def test_review_metrics_calculates_closed_trade_metrics_as_of_date() -> None:
    repository = InMemoryRepository()
    first_context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="first-review")
    second_context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="second-review")
    future_context = PipelineRunContext(trade_date=date(2026, 5, 6), run_id="future-review")

    repository.save_pipeline_run(first_context, "intraday_watch", "success", {"order_count": 2})
    repository.save_pipeline_run(second_context, "intraday_watch", "success", {"order_count": 1})
    repository.save_paper_positions(
        first_context,
        [
            PaperPosition(
                symbol="510300",
                opened_at=date(2026, 4, 27),
                quantity=100,
                entry_price=Decimal("100"),
                current_price=Decimal("112"),
                status="closed",
                closed_at=date(2026, 4, 29),
                exit_price=Decimal("110"),
            ),
            PaperPosition(
                symbol="159915",
                opened_at=date(2026, 4, 28),
                quantity=50,
                entry_price=Decimal("100"),
                current_price=Decimal("90"),
                status="closed",
                closed_at=date(2026, 4, 30),
                exit_price=Decimal("90"),
            ),
        ],
    )
    repository.save_paper_positions(
        second_context,
        [
            PaperPosition(
                symbol="510300",
                opened_at=date(2026, 4, 27),
                quantity=100,
                entry_price=Decimal("100"),
                current_price=Decimal("112"),
                status="closed",
                closed_at=date(2026, 4, 29),
                exit_price=Decimal("110"),
            )
        ],
    )
    repository.save_paper_positions(
        future_context,
        [
            PaperPosition(
                symbol="512000",
                opened_at=date(2026, 5, 4),
                quantity=100,
                entry_price=Decimal("10"),
                current_price=Decimal("12"),
                status="closed",
                closed_at=date(2026, 5, 6),
                exit_price=Decimal("12"),
            )
        ],
    )
    repository.save_paper_orders(
        first_context,
        [
            PaperOrder(
                order_id="paper-2026-04-29-510300-sell",
                symbol="510300",
                trade_date=date(2026, 4, 29),
                side="sell",
                quantity=100,
                price=Decimal("110"),
                amount=Decimal("11000"),
                slippage=Decimal("0.001"),
                reason="触发止损",
            ),
            PaperOrder(
                order_id="paper-2026-04-29-159915-sell",
                symbol="159915",
                trade_date=date(2026, 4, 29),
                side="sell",
                quantity=50,
                price=Decimal("90"),
                amount=Decimal("4500"),
                slippage=Decimal("0.001"),
                reason="趋势走弱卖出",
            ),
        ],
    )
    repository.save_paper_orders(
        second_context,
        [
            PaperOrder(
                order_id="paper-2026-04-30-512000-buy",
                symbol="512000",
                trade_date=date(2026, 4, 30),
                side="buy",
                quantity=100,
                price=Decimal("10"),
                amount=Decimal("1000"),
                slippage=Decimal("0.001"),
                reason="通过",
            )
        ],
    )
    repository.save_portfolio_snapshot(
        PipelineRunContext(trade_date=date(2026, 4, 28), run_id="snapshot-1"),
        PortfolioSnapshot(
            trade_date=date(2026, 4, 28),
            cash=Decimal("90000"),
            market_value=Decimal("10000"),
            total_value=Decimal("100000"),
            open_positions=1,
        ),
    )
    repository.save_portfolio_snapshot(
        PipelineRunContext(trade_date=date(2026, 4, 29), run_id="snapshot-2"),
        PortfolioSnapshot(
            trade_date=date(2026, 4, 29),
            cash=Decimal("92000"),
            market_value=Decimal("10000"),
            total_value=Decimal("102000"),
            open_positions=1,
        ),
    )
    repository.save_portfolio_snapshot(
        PipelineRunContext(trade_date=date(2026, 4, 30), run_id="snapshot-3"),
        PortfolioSnapshot(
            trade_date=date(2026, 4, 30),
            cash=Decimal("95000"),
            market_value=Decimal("0"),
            total_value=Decimal("95000"),
            open_positions=0,
        ),
    )

    metrics = ReviewMetricsAgent(repository).metrics_as_of(date(2026, 4, 30))

    assert metrics.realized_pnl == Decimal("500")
    assert metrics.win_rate == 0.5
    assert metrics.average_holding_days == 2.0
    assert metrics.sell_reason_distribution == {"触发止损": 1, "趋势走弱卖出": 1}
    assert round(metrics.max_drawdown, 10) == 0.068627451


def test_review_metrics_returns_zero_values_without_closed_trades_or_drawdown() -> None:
    repository = InMemoryRepository()

    metrics = ReviewMetricsAgent(repository).metrics_as_of(date(2026, 4, 30))

    assert metrics.realized_pnl == Decimal("0")
    assert metrics.win_rate == 0
    assert metrics.average_holding_days == 0
    assert metrics.sell_reason_distribution == {}
    assert metrics.max_drawdown == 0


def test_review_metrics_counts_sell_reasons_only_from_successful_intraday_orders() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 30)
    intraday_context = PipelineRunContext(trade_date=trade_date, run_id="intraday-run")
    legacy_context = PipelineRunContext(trade_date=trade_date, run_id="legacy-post-review")
    repository.save_pipeline_run(
        intraday_context,
        "intraday_watch",
        "success",
        {"order_count": 1},
    )
    repository.save_pipeline_run(
        legacy_context,
        "post_market_review",
        "success",
        {"reviewed_order_count": 1},
    )
    repository.save_paper_orders(
        intraday_context,
        [
            PaperOrder(
                order_id="intraday-sell",
                symbol="510300",
                trade_date=trade_date,
                side="sell",
                quantity=100,
                price=Decimal("95"),
                amount=Decimal("9500"),
                slippage=Decimal("0.001"),
                reason="触发止损",
            )
        ],
    )
    repository.save_paper_orders(
        legacy_context,
        [
            PaperOrder(
                order_id="legacy-post-sell",
                symbol="159915",
                trade_date=trade_date,
                side="sell",
                quantity=100,
                price=Decimal("90"),
                amount=Decimal("9000"),
                slippage=Decimal("0.001"),
                reason="旧盘后卖出原因不应计入",
            )
        ],
    )

    metrics = ReviewMetricsAgent(repository).metrics_as_of(trade_date)

    assert metrics.sell_reason_distribution == {"触发止损": 1}


def test_review_metrics_rejects_malformed_position_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="broken-position")
    repository.save_raw_payload(
        "paper_positions",
        context,
        "510300",
        {
            "symbol": "510300",
            "opened_at": "2026-04-29",
            "quantity": 100,
            "entry_price": "not-a-number",
            "current_price": "100",
            "status": "closed",
            "closed_at": "2026-04-30",
            "exit_price": "99",
        },
    )

    with pytest.raises(ValueError, match="paper_positions"):
        ReviewMetricsAgent(repository).metrics_as_of(date(2026, 4, 30))


def test_review_metrics_rejects_real_trade_order_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="real-order")
    repository.save_pipeline_run(context, "intraday_watch", "success", {"order_count": 1})
    repository.save_raw_payload(
        "paper_orders",
        context,
        "510300",
        {
            "order_id": "real-order",
            "symbol": "510300",
            "trade_date": "2026-04-30",
            "side": "sell",
            "quantity": 100,
            "price": "100",
            "amount": "10000",
            "slippage": "0.001",
            "reason": "真实交易",
            "is_real_trade": True,
        },
    )

    with pytest.raises(ValueError, match="真实交易"):
        ReviewMetricsAgent(repository).metrics_as_of(date(2026, 4, 30))

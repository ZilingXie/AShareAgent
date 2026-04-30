from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.domain import (
    PaperOrder,
    PaperPosition,
    PipelineRunContext,
    PortfolioSnapshot,
)
from ashare_agent.repository import InMemoryRepository


def test_repository_restores_only_open_positions_after_closed_payload() -> None:
    repository = InMemoryRepository()
    symbol = "510300"
    open_context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="open-run")
    close_context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="close-run")

    repository.save_paper_positions(
        open_context,
        [
            PaperPosition(
                symbol=symbol,
                opened_at=date(2026, 4, 29),
                quantity=100,
                entry_price=Decimal("100"),
                current_price=Decimal("100"),
                status="open",
            )
        ],
    )
    repository.save_paper_positions(
        close_context,
        [
            PaperPosition(
                symbol=symbol,
                opened_at=date(2026, 4, 29),
                quantity=100,
                entry_price=Decimal("100"),
                current_price=Decimal("96"),
                status="closed",
                closed_at=date(2026, 4, 30),
                exit_price=Decimal("95.9040"),
            )
        ],
    )

    assert repository.load_open_positions() == []


def test_repository_restores_latest_snapshot_and_paper_orders() -> None:
    repository = InMemoryRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="review-run")
    order = PaperOrder(
        order_id="paper-2026-04-30-510300-sell",
        symbol="510300",
        trade_date=date(2026, 4, 30),
        side="sell",
        quantity=100,
        price=Decimal("95.9040"),
        amount=Decimal("9590.40"),
        slippage=Decimal("0.001"),
        reason="触发止损",
    )
    snapshot = PortfolioSnapshot(
        trade_date=date(2026, 4, 30),
        cash=Decimal("99590.40"),
        market_value=Decimal("0"),
        total_value=Decimal("99590.40"),
        open_positions=0,
    )

    repository.save_paper_orders(context, [order])
    repository.save_portfolio_snapshot(context, snapshot)

    assert repository.load_paper_orders(date(2026, 4, 30))[0].side == "sell"
    assert repository.load_paper_orders(date(2026, 4, 30))[0].is_real_trade is False
    assert repository.load_latest_portfolio_snapshot() == snapshot


def test_repository_payload_rows_filter_by_table_date_and_run_id() -> None:
    repository = InMemoryRepository()
    first_context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="first-run")
    second_context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="second-run")

    repository.save_pipeline_run(first_context, "pre_market", "success", {"report_path": "a.md"})
    repository.save_pipeline_run(second_context, "pre_market", "success", {"report_path": "b.md"})

    assert len(repository.payload_rows("pipeline_runs")) == 2
    assert repository.payload_rows("pipeline_runs", trade_date=date(2026, 4, 29))[0][
        "run_id"
    ] == "first-run"
    assert repository.payload_rows("pipeline_runs", run_id="second-run")[0][
        "run_id"
    ] == "second-run"


def test_repository_payload_rows_rejects_unknown_table() -> None:
    repository = InMemoryRepository()

    try:
        repository.payload_rows("unknown_table")
    except ValueError as exc:
        assert "unknown_table" in str(exc)
    else:
        raise AssertionError("未知 payload table 必须显式失败")

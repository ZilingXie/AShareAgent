from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.domain import (
    DataQualityReport,
    PaperOrder,
    PaperPosition,
    PipelineRunContext,
    PortfolioSnapshot,
    TradingCalendarDay,
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


def test_repository_filters_paper_orders_by_successful_pipeline_stage() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 30)
    legacy_context = PipelineRunContext(trade_date=trade_date, run_id="legacy-post-review")
    failed_intraday_context = PipelineRunContext(trade_date=trade_date, run_id="failed-intraday")
    intraday_context = PipelineRunContext(trade_date=trade_date, run_id="intraday-run")

    repository.save_pipeline_run(
        legacy_context,
        "post_market_review",
        "success",
        {"reviewed_order_count": 1},
    )
    repository.save_pipeline_run(
        failed_intraday_context,
        "intraday_watch",
        "failed",
        {"failure_reason": "盘中执行失败"},
    )
    repository.save_pipeline_run(
        intraday_context,
        "intraday_watch",
        "success",
        {"order_count": 1},
    )
    repository.save_paper_orders(
        legacy_context,
        [
            PaperOrder(
                order_id="legacy-post-buy",
                symbol="510300",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("4.0000"),
                amount=Decimal("400.00"),
                slippage=Decimal("0.001"),
                reason="旧盘后买单",
            )
        ],
    )
    repository.save_paper_orders(
        failed_intraday_context,
        [
            PaperOrder(
                order_id="failed-intraday-buy",
                symbol="159915",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("2.0000"),
                amount=Decimal("200.00"),
                slippage=Decimal("0.001"),
                reason="失败 run 订单不应计入",
            )
        ],
    )
    repository.save_paper_orders(
        intraday_context,
        [
            PaperOrder(
                order_id="intraday-buy",
                symbol="510300",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("4.1041"),
                amount=Decimal("410.41"),
                slippage=Decimal("0.001"),
                reason="盘中模拟买入",
            )
        ],
    )

    assert [order.order_id for order in repository.load_paper_orders(trade_date)] == [
        "legacy-post-buy",
        "failed-intraday-buy",
        "intraday-buy",
    ]
    assert [
        order.order_id
        for order in repository.load_paper_orders(trade_date, stage="intraday_watch")
    ] == ["intraday-buy"]


def test_repository_stage_filter_returns_empty_without_successful_stage_run() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 30)
    legacy_context = PipelineRunContext(trade_date=trade_date, run_id="legacy-post-review")
    repository.save_pipeline_run(
        legacy_context,
        "post_market_review",
        "success",
        {"reviewed_order_count": 1},
    )
    repository.save_paper_orders(
        legacy_context,
        [
            PaperOrder(
                order_id="legacy-post-buy",
                symbol="510300",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("4.0000"),
                amount=Decimal("400.00"),
                slippage=Decimal("0.001"),
                reason="旧盘后买单",
            )
        ],
    )

    assert repository.load_paper_orders(trade_date, stage="intraday_watch") == []


def test_repository_scopes_backtest_state_away_from_normal_account() -> None:
    repository = InMemoryRepository()
    normal_context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="normal-run")
    backtest_context = PipelineRunContext(
        trade_date=date(2026, 4, 29),
        run_id="backtest-run",
        run_mode="backtest",
        backtest_id="bt-signal-v1",
    )
    repository.save_paper_positions(
        normal_context,
        [
            PaperPosition(
                symbol="510300",
                opened_at=date(2026, 4, 29),
                quantity=100,
                entry_price=Decimal("100"),
                current_price=Decimal("101"),
                status="open",
            )
        ],
    )
    repository.save_paper_positions(
        backtest_context,
        [
            PaperPosition(
                symbol="159915",
                opened_at=date(2026, 4, 29),
                quantity=200,
                entry_price=Decimal("10"),
                current_price=Decimal("11"),
                status="open",
            )
        ],
    )
    repository.save_portfolio_snapshot(
        normal_context,
        PortfolioSnapshot(
            trade_date=date(2026, 4, 29),
            cash=Decimal("90000"),
            market_value=Decimal("10100"),
            total_value=Decimal("100100"),
            open_positions=1,
        ),
    )
    repository.save_portfolio_snapshot(
        backtest_context,
        PortfolioSnapshot(
            trade_date=date(2026, 4, 29),
            cash=Decimal("80000"),
            market_value=Decimal("2200"),
            total_value=Decimal("82200"),
            open_positions=1,
        ),
    )

    assert [position.symbol for position in repository.load_open_positions()] == ["510300"]
    assert [
        position.symbol
        for position in repository.load_open_positions(
            run_mode="backtest",
            backtest_id="bt-signal-v1",
        )
    ] == ["159915"]
    assert repository.load_latest_cash(default_cash=Decimal("0")) == Decimal("90000")
    assert repository.load_latest_cash(
        default_cash=Decimal("0"),
        run_mode="backtest",
        backtest_id="bt-signal-v1",
    ) == Decimal("80000")
    assert repository.records_for("paper_positions")[-1]["payload"]["run_mode"] == "backtest"
    assert repository.records_for("paper_positions")[-1]["payload"]["backtest_id"] == (
        "bt-signal-v1"
    )


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


def test_repository_saves_data_quality_report_payload() -> None:
    repository = InMemoryRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="quality-run")

    repository.save_data_quality_report(
        context,
        DataQualityReport(
            trade_date=context.trade_date,
            stage="pre_market",
            status="passed",
            source_failure_rate=0,
            total_sources=2,
            failed_source_count=0,
            empty_source_count=0,
            missing_market_bar_count=0,
            abnormal_price_count=0,
            is_trade_date=True,
            issues=[],
        ),
    )

    rows = repository.payload_rows("data_quality_reports")

    assert rows[0]["run_id"] == "quality-run"
    assert rows[0]["payload"]["status"] == "passed"


def test_repository_upserts_structured_trading_calendar_days() -> None:
    repository = InMemoryRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="calendar-run")

    repository.save_trading_calendar_days(
        context,
        [TradingCalendarDay(date(2026, 4, 29), True, "trade_calendar")],
    )
    repository.save_trading_calendar_days(
        context,
        [TradingCalendarDay(date(2026, 4, 29), False, "trade_calendar")],
    )

    rows = repository.trading_calendar_days(
        start_date=date(2026, 4, 29),
        end_date=date(2026, 4, 29),
    )

    assert [(row.calendar_date, row.is_trade_date, row.source) for row in rows] == [
        (date(2026, 4, 29), False, "trade_calendar")
    ]


def test_repository_payload_rows_rejects_unknown_table() -> None:
    repository = InMemoryRepository()

    try:
        repository.payload_rows("unknown_table")
    except ValueError as exc:
        assert "unknown_table" in str(exc)
    else:
        raise AssertionError("未知 payload table 必须显式失败")

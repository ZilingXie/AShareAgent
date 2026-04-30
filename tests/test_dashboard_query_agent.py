from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ashare_agent.agents.dashboard_query_agent import DashboardQueryAgent
from ashare_agent.domain import (
    DataQualityIssue,
    DataQualityReport,
    PaperOrder,
    PaperPosition,
    PipelineRunContext,
    PortfolioSnapshot,
    ReviewReport,
    RiskDecision,
    Signal,
    SourceSnapshot,
    WatchlistCandidate,
)
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


def test_dashboard_query_builds_runs_and_day_summary_from_stable_dtos() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 29)
    failed_context = PipelineRunContext(trade_date=trade_date, run_id="failed-run")
    old_pre_market_context = PipelineRunContext(trade_date=trade_date, run_id="old-pre-market-run")
    pre_market_context = PipelineRunContext(trade_date=trade_date, run_id="pre-market-run")
    review_context = PipelineRunContext(trade_date=trade_date, run_id="review-run")

    repository.save_pipeline_run(
        failed_context,
        "pre_market",
        "failed",
        {"failure_reason": "必需数据源失败: market_bars"},
    )
    repository.save_pipeline_run(
        old_pre_market_context,
        "pre_market",
        "success",
        {"report_path": "reports/2026-04-29/old-pre-market.md"},
    )
    repository.save_watchlist_candidates(
        old_pre_market_context,
        [
            WatchlistCandidate(
                symbol="159915",
                trade_date=trade_date,
                score=0.99,
                score_breakdown={"technical": 0.99},
                reasons=["旧 run 不应展示"],
            )
        ],
    )
    repository.save_pipeline_run(
        pre_market_context,
        "pre_market",
        "success",
        {"report_path": "reports/2026-04-29/pre-market.md"},
    )
    repository.save_pipeline_run(
        review_context,
        "post_market_review",
        "success",
        {"report_path": "reports/2026-04-29/post-market-review.md"},
    )
    repository.save_watchlist_candidates(
        pre_market_context,
        [
            WatchlistCandidate(
                symbol="510300",
                trade_date=trade_date,
                score=0.82,
                score_breakdown={"technical": 0.45, "market": 0.2},
                reasons=["趋势改善"],
            )
        ],
    )
    repository.save_signals(
        pre_market_context,
        [
            Signal(
                symbol="510300",
                trade_date=trade_date,
                action="paper_buy",
                score=0.82,
                score_breakdown={"technical": 0.45, "market": 0.2},
                reasons=["进入模拟买入候选"],
            )
        ],
    )
    repository.save_risk_decisions(
        pre_market_context,
        [
            RiskDecision(
                symbol="510300",
                trade_date=trade_date,
                signal_action="paper_buy",
                approved=False,
                reasons=["接近涨停，不买入"],
                target_position_pct=Decimal("0"),
            )
        ],
    )
    repository.save_paper_orders(
        review_context,
        [
            PaperOrder(
                order_id="paper-2026-04-29-510300-buy",
                symbol="510300",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("4.1041"),
                amount=Decimal("410.41"),
                slippage=Decimal("0.001"),
                reason="通过",
            ),
            PaperOrder(
                order_id="paper-2026-04-29-159915-sell",
                symbol="159915",
                trade_date=trade_date,
                side="sell",
                quantity=50,
                price=Decimal("110"),
                amount=Decimal("5500"),
                slippage=Decimal("0.001"),
                reason="趋势走弱卖出",
            )
        ],
    )
    repository.save_paper_positions(
        review_context,
        [
            PaperPosition(
                symbol="510300",
                opened_at=date(2026, 4, 27),
                quantity=100,
                entry_price=Decimal("4.00"),
                current_price=Decimal("4.20"),
                status="open",
            ),
            PaperPosition(
                symbol="159915",
                opened_at=date(2026, 4, 27),
                quantity=50,
                entry_price=Decimal("100"),
                current_price=Decimal("110"),
                status="closed",
                closed_at=trade_date,
                exit_price=Decimal("110"),
            )
        ],
    )
    repository.save_portfolio_snapshot(
        PipelineRunContext(trade_date=date(2026, 4, 28), run_id="previous-snapshot"),
        PortfolioSnapshot(
            trade_date=date(2026, 4, 28),
            cash=Decimal("90000"),
            market_value=Decimal("11000"),
            total_value=Decimal("101000"),
            open_positions=1,
        ),
    )
    repository.save_portfolio_snapshot(
        review_context,
        PortfolioSnapshot(
            trade_date=trade_date,
            cash=Decimal("99589.59"),
            market_value=Decimal("420"),
            total_value=Decimal("100009.59"),
            open_positions=1,
        ),
    )
    repository.save_review_report(
        review_context,
        ReviewReport(
            trade_date=trade_date,
            summary="模拟账户总资产 100009.59。",
            stats={"total_value": 100009.59},
            attribution=["510300: 当前价 4.20, 成本 4.00"],
            parameter_suggestions=["继续观察。"],
        ),
    )
    repository.save_raw_source_snapshots(
        failed_context,
        [
            SourceSnapshot(
                source="market_bars",
                trade_date=trade_date,
                status="failed",
                failure_reason="EastMoney endpoint disconnected",
            )
        ],
    )
    repository.save_data_quality_report(
        failed_context,
        DataQualityReport(
            trade_date=trade_date,
            stage="pre_market",
            status="failed",
            source_failure_rate=0.2,
            total_sources=5,
            failed_source_count=1,
            empty_source_count=0,
            missing_market_bar_count=1,
            abnormal_price_count=0,
            is_trade_date=True,
            issues=[
                DataQualityIssue(
                    severity="error",
                    check_name="missing_market_bar",
                    source="market_bars",
                    symbol="510300",
                    message="510300 缺少 2026-04-29 当日行情",
                    metadata={"trade_date": "2026-04-29"},
                )
            ],
        ),
    )

    agent = DashboardQueryAgent(repository)
    runs = agent.list_pipeline_runs(limit=10)
    day = agent.day_summary(trade_date)

    assert runs[0].run_id == "review-run"
    assert any(run.failure_reason == "必需数据源失败: market_bars" for run in runs)
    assert day.trade_date == "2026-04-29"
    assert [item.symbol for item in day.watchlist] == ["510300"]
    assert day.signals[0].action == "paper_buy"
    assert day.risk_decisions[0].approved is False
    assert day.paper_orders[0].is_real_trade is False
    assert day.paper_orders[0].price == "4.1041"
    assert day.positions[0].pnl_amount == "20.00"
    assert day.positions[0].holding_days == 2
    assert day.portfolio_snapshot is not None
    assert day.portfolio_snapshot.total_value == "100009.59"
    assert day.review_report is not None
    assert day.review_report.summary == "模拟账户总资产 100009.59。"
    assert day.review_report.metrics.realized_pnl == "500.00"
    assert day.review_report.metrics.win_rate == 1.0
    assert day.review_report.metrics.average_holding_days == 2.0
    assert day.review_report.metrics.sell_reason_distribution == {"趋势走弱卖出": 1}
    assert round(day.review_report.metrics.max_drawdown, 10) == 0.0098060396
    assert day.source_snapshots[0].stage == "pre_market"
    assert day.source_snapshots[0].failure_reason == "EastMoney endpoint disconnected"
    assert day.data_quality_reports[0].status == "failed"
    assert day.data_quality_reports[0].issues[0].symbol == "510300"


def test_dashboard_query_keeps_failed_runs_visible_without_successful_pre_market() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 29)
    failed_context = PipelineRunContext(trade_date=trade_date, run_id="failed-run")
    repository.save_pipeline_run(
        failed_context,
        "pre_market",
        "failed",
        {"failure_reason": "必需数据源失败: market_bars"},
    )
    repository.save_raw_source_snapshots(
        failed_context,
        [
            SourceSnapshot(
                source="market_bars",
                trade_date=trade_date,
                status="failed",
                failure_reason="行情接口失败",
            )
        ],
    )

    day = DashboardQueryAgent(repository).day_summary(trade_date)

    assert day.runs[0].status == "failed"
    assert day.watchlist == []
    assert day.signals == []
    assert day.risk_decisions == []
    assert day.source_snapshots[0].failure_reason == "行情接口失败"


def test_dashboard_query_positions_as_of_date_use_latest_record_per_symbol() -> None:
    repository = InMemoryRepository()
    open_context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="open-run")
    close_context = PipelineRunContext(trade_date=date(2026, 4, 30), run_id="close-run")
    repository.save_paper_positions(
        open_context,
        [
            PaperPosition(
                symbol="510300",
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
                symbol="510300",
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

    agent = DashboardQueryAgent(repository)
    open_day = agent.day_summary(date(2026, 4, 29))
    closed_day = agent.day_summary(date(2026, 4, 30))

    assert open_day.positions[0].status == "open"
    assert open_day.positions[0].pnl_amount == "0.00"
    assert closed_day.positions[0].status == "closed"
    assert closed_day.positions[0].exit_price == "95.9040"
    assert closed_day.positions[0].pnl_amount == "-409.60"


def test_dashboard_query_rejects_malformed_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="broken-run")
    repository.save_pipeline_run(context, "pre_market", "success", {"report_path": "report.md"})
    repository.save_raw_payload(
        "watchlist_candidates",
        context,
        "510300",
        {"symbol": "510300", "score": "not-a-number", "reasons": []},
    )

    with pytest.raises(ValueError, match="watchlist_candidates"):
        DashboardQueryAgent(repository).day_summary(context.trade_date)


def test_dashboard_query_rejects_real_trade_order_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="review-run")
    repository.save_pipeline_run(context, "post_market_review", "success", {"report_path": "x.md"})
    repository.save_raw_payload(
        "paper_orders",
        context,
        "510300",
        {
            "order_id": "real-order",
            "symbol": "510300",
            "trade_date": "2026-04-29",
            "side": "buy",
            "quantity": 100,
            "price": "4.10",
            "amount": "410",
            "slippage": "0.001",
            "reason": "should fail",
            "is_real_trade": True,
        },
    )

    with pytest.raises(ValueError, match="真实交易"):
        DashboardQueryAgent(repository).day_summary(context.trade_date)


def test_dashboard_query_rejects_malformed_data_quality_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="quality-run")
    repository.save_pipeline_run(context, "pre_market", "success", {"report_path": "x.md"})
    repository.save_raw_payload(
        "data_quality_reports",
        context,
        None,
        {
            "trade_date": "2026-04-29",
            "stage": "pre_market",
            "status": "unknown",
            "source_failure_rate": 0,
            "total_sources": 1,
            "failed_source_count": 0,
            "empty_source_count": 0,
            "missing_market_bar_count": 0,
            "abnormal_price_count": 0,
            "is_trade_date": True,
            "issues": [],
        },
    )

    with pytest.raises(ValueError, match="data_quality_reports"):
        DashboardQueryAgent(repository).day_summary(context.trade_date)

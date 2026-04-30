from __future__ import annotations

from datetime import date
from decimal import Decimal

from ashare_agent.dashboard import DashboardQueryService
from ashare_agent.domain import (
    PaperOrder,
    PaperPosition,
    PipelineRunContext,
    PortfolioSnapshot,
    ReviewReport,
    RiskDecision,
    SourceSnapshot,
    WatchlistCandidate,
)
from ashare_agent.repository import InMemoryRepository


def test_dashboard_query_builds_run_list_and_day_summary() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 29)
    failed_context = PipelineRunContext(trade_date=trade_date, run_id="failed-run")
    pre_market_context = PipelineRunContext(trade_date=trade_date, run_id="pre-market-run")
    review_context = PipelineRunContext(trade_date=trade_date, run_id="review-run")

    repository.save_pipeline_run(
        failed_context,
        "pre_market",
        "failed",
        {"failure_reason": "必需数据源失败: market_bars"},
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
            )
        ],
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

    service = DashboardQueryService(repository)
    runs = service.list_runs(limit=10)
    day = service.day_summary(trade_date)

    assert runs[0].run_id == "review-run"
    assert any(run.failure_reason == "必需数据源失败: market_bars" for run in runs)
    assert day.watchlist[0].symbol == "510300"
    assert day.risk_decisions[0].approved is False
    assert day.paper_orders[0].is_real_trade is False
    assert day.positions[0].pnl_amount == "20.00"
    assert day.positions[0].holding_days == 2
    assert day.portfolio_snapshot is not None
    assert day.review_report is not None
    assert day.source_snapshots[0].failure_reason == "EastMoney endpoint disconnected"

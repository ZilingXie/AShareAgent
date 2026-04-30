from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ashare_agent.agents.dashboard_query_agent import DashboardQueryAgent
from ashare_agent.domain import (
    DataQualityIssue,
    DataQualityReport,
    DataReliabilityIssue,
    DataReliabilityReport,
    DataSourceHealth,
    MarketBarGap,
    PaperOrder,
    PaperPosition,
    PipelineRunContext,
    PortfolioSnapshot,
    ReviewReport,
    RiskDecision,
    Signal,
    SourceSnapshot,
    TradingCalendarDay,
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
    repository.save_trading_calendar_days(
        pre_market_context,
        [TradingCalendarDay(trade_date, True, "trade_calendar")],
    )
    repository.save_data_reliability_report(
        pre_market_context,
        DataReliabilityReport(
            trade_date=trade_date,
            status="failed",
            is_trade_date=True,
            lookback_trade_days=30,
            total_sources=1,
            failed_source_count=1,
            empty_source_count=0,
            source_failure_rate=1.0,
            missing_market_bar_count=1,
            source_health=[
                DataSourceHealth(
                    source="market_bars",
                    status="failed",
                    total_snapshots=1,
                    failed_snapshots=1,
                    empty_snapshots=0,
                    row_count=0,
                    failure_rate=1.0,
                    last_failure_reason="EastMoney endpoint disconnected",
                    required=True,
                )
            ],
            market_bar_gaps=[
                MarketBarGap(
                    symbol="510300",
                    missing_dates=["2026-04-29"],
                    missing_count=1,
                )
            ],
            issues=[
                DataReliabilityIssue(
                    severity="error",
                    check_name="market_bar_gap",
                    message="510300 近 30 个交易日缺少 1 天行情",
                    source="market_bars",
                    symbol="510300",
                    metadata={"missing_dates": ["2026-04-29"]},
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
    assert day.trading_calendar is not None
    assert day.trading_calendar.is_trade_date is True
    assert day.data_reliability_reports[0].status == "failed"
    assert day.data_reliability_reports[0].missing_market_bar_count == 1
    assert day.data_quality_reports[0].status == "failed"
    assert day.data_quality_reports[0].issues[0].symbol == "510300"


def test_dashboard_query_builds_range_trends_from_latest_successful_pre_market_runs() -> None:
    repository = InMemoryRepository()
    first_date = date(2026, 4, 28)
    second_date = date(2026, 4, 29)
    third_date = date(2026, 4, 30)
    old_context = PipelineRunContext(trade_date=second_date, run_id="old-pre")
    latest_context = PipelineRunContext(trade_date=second_date, run_id="latest-pre")
    third_context = PipelineRunContext(trade_date=third_date, run_id="third-pre")

    repository.save_pipeline_run(
        old_context,
        "pre_market",
        "success",
        {"report_path": "reports/2026-04-29/old.md"},
    )
    repository.save_signals(
        old_context,
        [
            Signal(
                symbol="159915",
                trade_date=second_date,
                action="paper_buy",
                score=0.99,
                score_breakdown={"technical": 0.99},
                reasons=["旧 run 不应进入趋势"],
            )
        ],
    )
    repository.save_pipeline_run(
        latest_context,
        "pre_market",
        "success",
        {"report_path": "reports/2026-04-29/latest.md"},
    )
    repository.save_signals(
        latest_context,
        [
            Signal(
                symbol="510300",
                trade_date=second_date,
                action="paper_buy",
                score=0.91,
                score_breakdown={"technical": 0.5},
                reasons=["趋势改善"],
            ),
            Signal(
                symbol="000001",
                trade_date=second_date,
                action="observe",
                score=0.73,
                score_breakdown={"technical": 0.3},
                reasons=["观察"],
            ),
        ],
    )
    repository.save_risk_decisions(
        latest_context,
        [
            RiskDecision(
                symbol="510300",
                trade_date=second_date,
                signal_action="paper_buy",
                approved=True,
                reasons=["通过"],
                target_position_pct=Decimal("0.1"),
            ),
            RiskDecision(
                symbol="000001",
                trade_date=second_date,
                signal_action="observe",
                approved=False,
                reasons=["接近涨停，不买入"],
                target_position_pct=Decimal("0"),
            ),
        ],
    )
    repository.save_pipeline_run(
        third_context,
        "pre_market",
        "success",
        {"report_path": "reports/2026-04-30/pre-market.md"},
    )
    repository.save_risk_decisions(
        third_context,
        [
            RiskDecision(
                symbol="159915",
                trade_date=third_date,
                signal_action="paper_buy",
                approved=False,
                reasons=["接近涨停，不买入", "单日亏损超过限制"],
                target_position_pct=Decimal("0"),
            )
        ],
    )

    for snapshot_date, total_value in [
        (first_date, Decimal("100000")),
        (second_date, Decimal("100500")),
        (third_date, Decimal("100200")),
    ]:
        repository.save_portfolio_snapshot(
            PipelineRunContext(trade_date=snapshot_date, run_id=f"snapshot-{snapshot_date}"),
            PortfolioSnapshot(
                trade_date=snapshot_date,
                cash=Decimal("90000"),
                market_value=total_value - Decimal("90000"),
                total_value=total_value,
                open_positions=1,
            ),
        )

    repository.save_data_quality_report(
        PipelineRunContext(trade_date=first_date, run_id="quality-1"),
        DataQualityReport(
            trade_date=first_date,
            stage="pre_market",
            status="passed",
            source_failure_rate=0,
            total_sources=5,
            failed_source_count=0,
            empty_source_count=0,
            missing_market_bar_count=0,
            abnormal_price_count=0,
            is_trade_date=True,
            issues=[],
        ),
    )
    repository.save_data_quality_report(
        PipelineRunContext(trade_date=second_date, run_id="quality-2"),
        DataQualityReport(
            trade_date=second_date,
            stage="pre_market",
            status="warning",
            source_failure_rate=0.2,
            total_sources=5,
            failed_source_count=1,
            empty_source_count=0,
            missing_market_bar_count=0,
            abnormal_price_count=0,
            is_trade_date=True,
            issues=[
                DataQualityIssue(
                    severity="warning",
                    check_name="empty_optional_source",
                    source="news",
                    symbol=None,
                    message="news 为空",
                    metadata={},
                )
            ],
        ),
    )
    repository.save_data_quality_report(
        PipelineRunContext(trade_date=third_date, run_id="quality-3"),
        DataQualityReport(
            trade_date=third_date,
            stage="pre_market",
            status="failed",
            source_failure_rate=0.6,
            total_sources=5,
            failed_source_count=3,
            empty_source_count=0,
            missing_market_bar_count=1,
            abnormal_price_count=0,
            is_trade_date=True,
            issues=[
                DataQualityIssue(
                    severity="error",
                    check_name="missing_market_bar",
                    source="market_bars",
                    symbol="159915",
                    message="159915 缺少当日行情",
                    metadata={},
                ),
                DataQualityIssue(
                    severity="warning",
                    check_name="source_failed",
                    source="news",
                    symbol=None,
                    message="news 失败",
                    metadata={},
                ),
                DataQualityIssue(
                    severity="warning",
                    check_name="source_failed",
                    source="policy",
                    symbol=None,
                    message="policy 失败",
                    metadata={},
                ),
            ],
        ),
    )

    trend = DashboardQueryAgent(repository).trends(first_date, third_date)

    assert trend.start_date == "2026-04-28"
    assert trend.end_date == "2026-04-30"
    assert [point.trade_date for point in trend.points] == [
        "2026-04-28",
        "2026-04-29",
        "2026-04-30",
    ]
    assert [point.total_value for point in trend.points] == ["100000", "100500", "100200"]
    assert trend.points[1].signal_count == 2
    assert trend.points[1].approved_count == 1
    assert trend.points[1].rejected_count == 1
    assert trend.points[1].max_signal_score == 0.91
    assert trend.points[2].signal_count == 0
    assert trend.points[2].approved_count == 0
    assert trend.points[2].rejected_count == 1
    assert trend.points[2].source_failure_rate == 0.6
    assert trend.points[2].blocked_count == 1
    assert trend.points[2].warning_count == 2
    assert trend.risk_reject_reasons == {
        "接近涨停，不买入": 2,
        "单日亏损超过限制": 1,
    }


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

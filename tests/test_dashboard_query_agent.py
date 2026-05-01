from __future__ import annotations

from datetime import date, datetime
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
    LLMAnalysis,
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
    intraday_context = PipelineRunContext(trade_date=trade_date, run_id="intraday-run")
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
    repository.save_llm_analysis(
        pre_market_context,
        LLMAnalysis(
            trade_date=trade_date,
            model="mock-llm",
            summary="盘前关注指数趋势和量能。",
            key_points=["沪深300ETF 位于观察名单前列"],
            risk_notes=["仅用于模拟研究，不构成投资建议。"],
            raw_response={"provider": "mock"},
        ),
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
    repository.save_pipeline_run(
        intraday_context,
        "intraday_watch",
        "success",
        {
            "report_path": "reports/2026-04-29/intraday-watch.md",
            "order_count": 2,
            "execution_events": [
                {
                    "symbol": "512000",
                    "trade_date": "2026-04-29",
                    "side": "buy",
                    "status": "rejected",
                    "execution_method": "first_valid_1m_bar",
                    "used_daily_fallback": False,
                    "failure_reason": "无分钟线，无法成交",
                }
            ],
        },
    )
    repository.save_paper_orders(
        intraday_context,
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
                execution_source="mock_intraday",
                execution_timestamp=datetime(2026, 4, 29, 9, 31),
                execution_method="first_valid_1m_bar",
                reference_price=Decimal("4.1000"),
                used_daily_fallback=False,
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
                execution_source="mock_intraday",
                execution_timestamp=datetime(2026, 4, 29, 9, 31),
                execution_method="first_valid_1m_bar",
                reference_price=Decimal("110"),
                used_daily_fallback=False,
            )
        ],
    )
    repository.save_paper_orders(
        review_context,
        [
            PaperOrder(
                order_id="legacy-post-market-buy",
                symbol="512000",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("1.0000"),
                amount=Decimal("100.00"),
                slippage=Decimal("0.001"),
                reason="旧盘后订单不应出现在盘中模拟订单",
            )
        ],
    )
    repository.save_pipeline_run(
        review_context,
        "post_market_review",
        "success",
        {"report_path": "reports/2026-04-29/post-market-review.md"},
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
    repository.save_raw_source_snapshots(
        intraday_context,
        [
            SourceSnapshot(
                source="intraday_bars",
                trade_date=trade_date,
                status="success",
                row_count=3,
                metadata={
                    "intraday_source": "akshare_em,akshare_sina",
                    "requested_symbols": ["510300"],
                    "returned_symbols": ["510300"],
                    "missing_symbols": [],
                    "period": "1",
                    "timeout_seconds": 2.0,
                    "retry_attempts": 2,
                    "source_attempts": [
                        {
                            "source": "akshare_em",
                            "symbol": "510300",
                            "status": "failed",
                            "returned_rows": 0,
                            "retry_attempts": 2,
                            "timeout_seconds": 2.0,
                            "last_error": "RemoteDisconnected",
                        },
                        {
                            "source": "akshare_sina",
                            "symbol": "510300",
                            "status": "success",
                            "returned_rows": 3,
                            "retry_attempts": 2,
                            "timeout_seconds": 2.0,
                            "last_error": None,
                        },
                    ],
                },
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
    assert day.llm_analysis is not None
    assert day.llm_analysis.run_id == "pre-market-run"
    assert day.llm_analysis.model == "mock-llm"
    assert day.llm_analysis.summary == "盘前关注指数趋势和量能。"
    assert day.llm_analysis.key_points == ["沪深300ETF 位于观察名单前列"]
    assert day.llm_analysis.risk_notes == ["仅用于模拟研究，不构成投资建议。"]
    assert day.signals[0].action == "paper_buy"
    assert day.risk_decisions[0].approved is False
    assert [order.order_id for order in day.paper_orders] == [
        "paper-2026-04-29-510300-buy",
        "paper-2026-04-29-159915-sell",
    ]
    assert day.paper_orders[0].is_real_trade is False
    assert day.paper_orders[0].price == "4.1041"
    assert day.paper_orders[0].execution_source == "mock_intraday"
    assert day.paper_orders[0].execution_timestamp == "2026-04-29T09:31:00"
    assert day.paper_orders[0].execution_method == "first_valid_1m_bar"
    assert day.paper_orders[0].reference_price == "4.1000"
    assert day.paper_orders[0].used_daily_fallback is False
    assert day.paper_orders[0].execution_failure_reason is None
    assert day.execution_events[0].status == "rejected"
    assert day.execution_events[0].failure_reason == "无分钟线，无法成交"
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
    assert day.intraday_source_health[0].source == "akshare_em"
    assert day.intraday_source_health[0].symbol == "510300"
    assert day.intraday_source_health[0].status == "failed"
    assert day.intraday_source_health[0].retry_attempts == 2
    assert day.intraday_source_health[0].timeout_seconds == 2.0
    assert day.intraday_source_health[0].last_error == "RemoteDisconnected"
    assert day.intraday_source_health[1].source == "akshare_sina"
    assert day.intraday_source_health[1].status == "success"
    assert day.intraday_source_health[1].returned_rows == 3
    assert day.trading_calendar is not None
    assert day.trading_calendar.is_trade_date is True
    assert day.data_reliability_reports[0].status == "failed"
    assert day.data_reliability_reports[0].missing_market_bar_count == 1
    assert day.data_quality_reports[0].status == "failed"
    assert day.data_quality_reports[0].issues[0].symbol == "510300"


def test_dashboard_query_hides_legacy_post_market_orders_without_intraday_success() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 29)
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
                order_id="legacy-post-market-buy",
                symbol="510300",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("4.0000"),
                amount=Decimal("400.00"),
                slippage=Decimal("0.001"),
                reason="旧流程盘后买单",
            )
        ],
    )

    day = DashboardQueryAgent(repository).day_summary(trade_date)

    assert day.paper_orders == []


def test_dashboard_query_deduplicates_backtest_summaries_by_latest_row() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 30)
    old_context = PipelineRunContext(
        trade_date=trade_date,
        run_id="old-backtest-summary",
        run_mode="backtest",
        backtest_id="bt-repeat",
    )
    latest_context = PipelineRunContext(
        trade_date=trade_date,
        run_id="latest-backtest-summary",
        run_mode="backtest",
        backtest_id="bt-repeat",
    )

    repository.save_pipeline_run(
        old_context,
        "backtest",
        "success",
        {
            "strategy_params_version": "signal-old",
            "provider": "mock",
            "start_date": "2026-04-27",
            "end_date": "2026-04-29",
            "attempted_days": 3,
            "succeeded_days": 3,
            "failed_days": 0,
        },
    )
    repository.save_pipeline_run(
        latest_context,
        "backtest",
        "success",
        {
            "strategy_params_version": "signal-latest",
            "provider": "mock",
            "start_date": "2026-04-27",
            "end_date": "2026-04-30",
            "attempted_days": 4,
            "succeeded_days": 4,
            "failed_days": 0,
        },
    )

    backtests = DashboardQueryAgent(repository).list_backtests()

    assert [item.backtest_id for item in backtests] == ["bt-repeat"]
    assert backtests[0].strategy_params_version == "signal-latest"
    assert backtests[0].attempted_days == 4


def test_dashboard_query_deduplicates_strategy_comparison_requested_ids() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 30)
    for backtest_id, version in [
        ("bt-repeat", "signal-v1"),
        ("bt-other", "signal-v2"),
    ]:
        repository.save_pipeline_run(
            PipelineRunContext(
                trade_date=trade_date,
                run_id=f"{backtest_id}-summary",
                run_mode="backtest",
                backtest_id=backtest_id,
            ),
            "backtest",
            "success",
            {
                "strategy_params_version": version,
                "provider": "mock",
                "start_date": "2026-04-27",
                "end_date": "2026-04-30",
                "attempted_days": 4,
                "succeeded_days": 4,
                "failed_days": 0,
                "strategy_params_snapshot": {
                    "paper_trader": {"initial_cash": "100000"}
                },
            },
        )

    comparison = DashboardQueryAgent(repository).strategy_comparison(
        ["bt-repeat", "bt-repeat", "bt-other"]
    )

    assert comparison.backtest_ids == ["bt-repeat", "bt-other"]
    assert [item.backtest_id for item in comparison.items] == ["bt-repeat", "bt-other"]
    assert [item.strategy_params_version for item in comparison.items] == [
        "signal-v1",
        "signal-v2",
    ]


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


def test_dashboard_query_compares_strategy_versions_by_backtest_id() -> None:
    repository = InMemoryRepository()
    first_day = date(2026, 4, 27)
    second_day = date(2026, 4, 28)
    strategy_snapshot = {
        "version": "signal-v1",
        "paper_trader": {"initial_cash": "100000"},
        "signal": {"max_daily_signals": 2},
    }
    summary_context = PipelineRunContext(
        trade_date=second_day,
        run_id="bt-1-summary",
        run_mode="backtest",
        backtest_id="bt-1",
    )
    pre_context = PipelineRunContext(
        trade_date=first_day,
        run_id="bt-1-pre",
        run_mode="backtest",
        backtest_id="bt-1",
    )
    post_context = PipelineRunContext(
        trade_date=second_day,
        run_id="bt-1-post",
        run_mode="backtest",
        backtest_id="bt-1",
    )
    repository.save_pipeline_run(
        summary_context,
        "backtest",
        "success",
        {
            "provider": "mock",
            "start_date": first_day.isoformat(),
            "end_date": second_day.isoformat(),
            "attempted_days": 2,
            "succeeded_days": 2,
            "failed_days": 0,
            "strategy_params_version": "signal-v1",
            "strategy_params_snapshot": strategy_snapshot,
        },
    )
    repository.save_risk_decisions(
        pre_context,
        [
            RiskDecision(
                symbol="510300",
                trade_date=first_day,
                signal_action="paper_buy",
                approved=True,
                reasons=["通过"],
                target_position_pct=Decimal("0.1"),
            ),
            RiskDecision(
                symbol="159915",
                trade_date=first_day,
                signal_action="paper_buy",
                approved=False,
                reasons=["接近涨停，不买入"],
                target_position_pct=Decimal("0"),
            ),
        ],
    )
    repository.save_paper_positions(
        post_context,
        [
            PaperPosition(
                symbol="510300",
                opened_at=first_day,
                quantity=100,
                entry_price=Decimal("100"),
                current_price=Decimal("110"),
                status="closed",
                closed_at=second_day,
                exit_price=Decimal("110"),
            )
        ],
    )
    repository.save_portfolio_snapshot(
        pre_context,
        PortfolioSnapshot(
            trade_date=first_day,
            cash=Decimal("90000"),
            market_value=Decimal("10000"),
            total_value=Decimal("100000"),
            open_positions=1,
        ),
    )
    repository.save_portfolio_snapshot(
        post_context,
        PortfolioSnapshot(
            trade_date=second_day,
            cash=Decimal("101000"),
            market_value=Decimal("0"),
            total_value=Decimal("101000"),
            open_positions=0,
        ),
    )
    repository.save_data_quality_report(
        pre_context,
        DataQualityReport(
            trade_date=first_day,
            stage="pre_market",
            status="failed",
            source_failure_rate=0.5,
            total_sources=2,
            failed_source_count=1,
            empty_source_count=0,
            missing_market_bar_count=1,
            abnormal_price_count=0,
            is_trade_date=True,
            issues=[],
        ),
    )
    second_summary_context = PipelineRunContext(
        trade_date=second_day,
        run_id="bt-2-summary",
        run_mode="backtest",
        backtest_id="bt-2",
    )
    repository.save_pipeline_run(
        second_summary_context,
        "backtest",
        "failed",
        {
            "provider": "mock",
            "start_date": first_day.isoformat(),
            "end_date": second_day.isoformat(),
            "attempted_days": 2,
            "succeeded_days": 1,
            "failed_days": 1,
            "strategy_params_version": "signal-v2",
            "strategy_params_snapshot": {
                "version": "signal-v2",
                "paper_trader": {"initial_cash": "100000"},
            },
        },
    )

    agent = DashboardQueryAgent(repository)
    backtests = agent.list_backtests(limit=10)
    comparison = agent.strategy_comparison(["bt-1", "bt-2"])

    assert [item.backtest_id for item in backtests] == ["bt-2", "bt-1"]
    assert comparison.backtest_ids == ["bt-1", "bt-2"]
    first = comparison.items[0]
    assert first.backtest_id == "bt-1"
    assert first.strategy_params_version == "signal-v1"
    assert first.provider == "mock"
    assert first.win_rate == 1.0
    assert first.total_return == 0.01
    assert first.risk_reject_rate == 0.5
    assert first.data_quality_failure_rate == 0.5
    assert first.failed_days == 0
    assert comparison.items[1].failed_days == 1


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
    assert day.llm_analysis is None
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


def test_dashboard_day_summary_ignores_backtest_state_for_normal_views() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 29)
    normal_context = PipelineRunContext(trade_date=trade_date, run_id="normal-pre")
    backtest_context = PipelineRunContext(
        trade_date=trade_date,
        run_id="backtest-pre",
        run_mode="backtest",
        backtest_id="bt-hidden",
    )
    repository.save_pipeline_run(normal_context, "pre_market", "success", {"report_path": "n.md"})
    repository.save_pipeline_run(
        backtest_context,
        "pre_market",
        "success",
        {"report_path": "bt.md", "strategy_params_version": "bt-v1"},
    )
    repository.save_signals(
        normal_context,
        [
            Signal(
                symbol="510300",
                trade_date=trade_date,
                action="paper_buy",
                score=0.8,
                score_breakdown={"technical": 0.5},
                reasons=["normal"],
            )
        ],
    )
    repository.save_signals(
        backtest_context,
        [
            Signal(
                symbol="159915",
                trade_date=trade_date,
                action="paper_buy",
                score=0.99,
                score_breakdown={"technical": 0.9},
                reasons=["backtest"],
            )
        ],
    )
    repository.save_paper_positions(
        backtest_context,
        [
            PaperPosition(
                symbol="159915",
                opened_at=trade_date,
                quantity=100,
                entry_price=Decimal("10"),
                current_price=Decimal("11"),
                status="open",
            )
        ],
    )

    day = DashboardQueryAgent(repository).day_summary(trade_date)

    assert [run.run_id for run in day.runs] == ["normal-pre"]
    assert [signal.symbol for signal in day.signals] == ["510300"]
    assert day.positions == []


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


def test_dashboard_query_rejects_malformed_llm_analysis_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="pre-market-run")
    repository.save_pipeline_run(context, "pre_market", "success", {"report_path": "x.md"})
    repository.save_raw_payload(
        "llm_analyses",
        context,
        None,
        {
            "trade_date": "2026-04-29",
            "model": "mock-llm",
            "summary": "缺少 key_points",
            "risk_notes": [],
            "raw_response": {},
            "created_at": "2026-04-29T08:00:00+00:00",
        },
    )

    with pytest.raises(ValueError, match="llm_analyses"):
        DashboardQueryAgent(repository).day_summary(context.trade_date)


def test_dashboard_query_rejects_real_trade_order_payload() -> None:
    repository = RawPayloadRepository()
    context = PipelineRunContext(trade_date=date(2026, 4, 29), run_id="intraday-run")
    repository.save_pipeline_run(context, "intraday_watch", "success", {"report_path": "x.md"})
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

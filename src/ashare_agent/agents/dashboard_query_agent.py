from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol, TypeVar, cast

from ashare_agent.agents.review_metrics_agent import ReviewMetricsAgent
from ashare_agent.domain import TradingCalendarDay
from ashare_agent.repository import PayloadRecord

DashboardRowDto = TypeVar("DashboardRowDto")

_STAGE_RUN_GROUP_ORDER = {
    "morning_collect": 0,
    "pre_market": 1,
    "pre_market_brief": 2,
    "call_auction": 3,
    "intraday_watch": 4,
    "intraday_decision": 5,
    "close_collect": 6,
    "post_market_review": 7,
    "post_market_brief": 8,
    "strategy_insight": 9,
}


class DashboardQueryRepository(Protocol):
    def payload_rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]: ...

    def trading_calendar_days(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TradingCalendarDay]: ...


@dataclass(frozen=True)
class DashboardPipelineRun:
    run_id: str
    trade_date: str
    stage: str
    status: str
    report_path: str | None
    failure_reason: str | None
    created_at: str | None


@dataclass(frozen=True)
class DashboardStageRunGroup:
    group_id: str
    trade_date: str
    stage: str
    status: str
    total_run_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    latest_run_id: str
    latest_success_run_id: str | None
    member_run_ids: list[str]
    failure_reasons: list[str]
    created_at: str | None


@dataclass(frozen=True)
class DashboardWatchlistItem:
    run_id: str
    symbol: str
    trade_date: str
    score: float
    score_breakdown: dict[str, float]
    reasons: list[str]


@dataclass(frozen=True)
class DashboardSignalItem:
    run_id: str
    symbol: str
    trade_date: str
    action: str
    score: float
    score_breakdown: dict[str, float]
    reasons: list[str]


@dataclass(frozen=True)
class DashboardLLMAnalysis:
    run_id: str
    trade_date: str
    model: str
    summary: str
    key_points: list[str]
    risk_notes: list[str]
    created_at: str


@dataclass(frozen=True)
class DashboardRiskDecision:
    run_id: str
    symbol: str
    trade_date: str
    signal_action: str
    approved: bool
    reasons: list[str]
    target_position_pct: str


@dataclass(frozen=True)
class DashboardPaperOrder:
    run_id: str
    order_id: str
    symbol: str
    trade_date: str
    side: str
    quantity: int
    price: str
    amount: str
    slippage: str
    reason: str
    is_real_trade: bool
    execution_source: str | None
    execution_timestamp: str | None
    execution_method: str | None
    reference_price: str | None
    used_daily_fallback: bool
    execution_failure_reason: str | None
    created_at: str | None


@dataclass(frozen=True)
class DashboardExecutionEvent:
    run_id: str
    symbol: str
    trade_date: str
    side: str
    status: str
    execution_method: str
    used_daily_fallback: bool
    execution_source: str | None
    execution_timestamp: str | None
    reference_price: str | None
    estimated_price: str | None
    slippage: str | None
    failure_reason: str | None


@dataclass(frozen=True)
class DashboardPosition:
    run_id: str
    symbol: str
    opened_at: str
    quantity: int
    entry_price: str
    current_price: str
    status: str
    closed_at: str | None
    exit_price: str | None
    pnl_amount: str
    pnl_pct: float
    holding_days: int


@dataclass(frozen=True)
class DashboardPortfolioSnapshot:
    run_id: str
    trade_date: str
    cash: str
    market_value: str
    total_value: str
    open_positions: int


@dataclass(frozen=True)
class DashboardReviewMetrics:
    realized_pnl: str
    win_rate: float
    average_holding_days: float
    sell_reason_distribution: dict[str, int]
    max_drawdown: float


@dataclass(frozen=True)
class DashboardReviewReport:
    run_id: str
    trade_date: str
    summary: str
    stats: dict[str, float]
    attribution: list[str]
    parameter_suggestions: list[str]
    metrics: DashboardReviewMetrics



@dataclass(frozen=True)
class DashboardSourceSnapshot:
    run_id: str
    stage: str | None
    source: str
    trade_date: str
    status: str
    failure_reason: str | None
    row_count: int
    metadata: dict[str, object]
    collected_at: str | None


@dataclass(frozen=True)
class DashboardIntradaySourceHealth:
    run_id: str
    stage: str | None
    source: str
    symbol: str
    status: str
    returned_rows: int
    retry_attempts: int | None
    timeout_seconds: float | None
    last_error: str | None


@dataclass(frozen=True)
class DashboardDataQualityIssue:
    severity: str
    check_name: str
    source: str | None
    symbol: str | None
    message: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class DashboardDataQualityReport:
    run_id: str
    stage: str
    trade_date: str
    status: str
    source_failure_rate: float
    total_sources: int
    failed_source_count: int
    empty_source_count: int
    missing_market_bar_count: int
    abnormal_price_count: int
    is_trade_date: bool | None
    issues: list[DashboardDataQualityIssue]
    created_at: str | None


@dataclass(frozen=True)
class DashboardTradingCalendarDay:
    trade_date: str
    is_trade_date: bool
    source: str
    collected_at: str | None


@dataclass(frozen=True)
class DashboardDataReliabilityIssue:
    severity: str
    check_name: str
    source: str | None
    symbol: str | None
    message: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class DashboardDataSourceHealth:
    source: str
    status: str
    total_snapshots: int
    failed_snapshots: int
    empty_snapshots: int
    row_count: int
    failure_rate: float
    last_failure_reason: str | None
    required: bool


@dataclass(frozen=True)
class DashboardMarketBarGap:
    symbol: str
    missing_dates: list[str]
    missing_count: int


@dataclass(frozen=True)
class DashboardDataReliabilityReport:
    run_id: str
    trade_date: str
    status: str
    is_trade_date: bool | None
    lookback_trade_days: int
    total_sources: int
    failed_source_count: int
    empty_source_count: int
    source_failure_rate: float
    missing_market_bar_count: int
    source_health: list[DashboardDataSourceHealth]
    market_bar_gaps: list[DashboardMarketBarGap]
    issues: list[DashboardDataReliabilityIssue]
    created_at: str | None


@dataclass(frozen=True)
class DashboardTrendPoint:
    trade_date: str
    total_value: str | None
    signal_count: int
    approved_count: int
    rejected_count: int
    max_signal_score: float | None
    source_failure_rate: float
    blocked_count: int
    warning_count: int
    reliability_status: str
    reliability_source_failure_rate: float
    reliability_missing_market_bar_count: int


def _empty_trend_points() -> list[DashboardTrendPoint]:
    return []


def _empty_risk_reject_reasons() -> dict[str, int]:
    return {}


@dataclass(frozen=True)
class DashboardTrendSummary:
    start_date: str
    end_date: str
    points: list[DashboardTrendPoint] = field(default_factory=_empty_trend_points)
    risk_reject_reasons: dict[str, int] = field(default_factory=_empty_risk_reject_reasons)


@dataclass(frozen=True)
class DashboardBacktest:
    backtest_id: str
    strategy_params_version: str
    provider: str
    start_date: str
    end_date: str
    status: str
    attempted_days: int
    succeeded_days: int
    failed_days: int
    created_at: str | None


@dataclass(frozen=True)
class DashboardStrategyComparisonItem:
    backtest_id: str
    strategy_params_version: str
    provider: str
    start_date: str
    end_date: str
    attempted_days: int
    succeeded_days: int
    failed_days: int
    win_rate: float
    max_drawdown: float
    total_return: float
    risk_reject_rate: float
    data_quality_failure_rate: float


@dataclass(frozen=True)
class DashboardStrategyComparison:
    backtest_ids: list[str]
    items: list[DashboardStrategyComparisonItem]


@dataclass(frozen=True)
class DashboardStrategyEvaluationRecommendation:
    summary: str
    recommended_variant_ids: list[str]


@dataclass(frozen=True)
class DashboardStrategyEvaluationVariant:
    id: str
    label: str
    version: str
    backtest_id: str
    success: bool
    attempted_days: int
    succeeded_days: int
    failed_days: int
    source_failure_rate: float
    data_quality_failure_rate: float
    signal_count: int
    risk_approved_count: int
    risk_rejected_count: int
    order_count: int
    execution_failed_count: int
    closed_trade_count: int
    signal_hit_count: int
    signal_hit_rate: float
    open_position_count: int
    holding_pnl: str
    total_return: float
    max_drawdown: float
    is_recommended: bool
    not_recommended_reasons: list[str]


@dataclass(frozen=True)
class DashboardStrategyEvaluation:
    evaluation_id: str
    provider: str
    start_date: str
    end_date: str
    report_path: str
    variant_count: int
    recommendation: DashboardStrategyEvaluationRecommendation
    variants: list[DashboardStrategyEvaluationVariant]


@dataclass(frozen=True)
class DashboardStrategyInsightHypothesis:
    area: str
    direction: str
    reason: str
    risk: str


@dataclass(frozen=True)
class DashboardStrategyInsightExperiment:
    name: str
    param: str
    candidate_value: str
    policy_status: str
    policy_reason: str | None
    variant_id: str | None
    overrides: dict[str, object]


@dataclass(frozen=True)
class DashboardStrategyInsightWindow:
    window_trade_days: int
    evaluation_id: str
    report_path: str
    recommended_variant_ids: list[str]
    passed_variant_ids: list[str]
    failed_variant_reasons: dict[str, list[str]]


@dataclass(frozen=True)
class DashboardStrategyInsight:
    insight_id: str
    trade_date: str
    provider: str
    summary: str
    attribution: list[str]
    manual_status: str
    report_path: str
    hypotheses: list[DashboardStrategyInsightHypothesis]
    experiments: list[DashboardStrategyInsightExperiment]
    evaluation_windows: list[DashboardStrategyInsightWindow]
    recommended_variant_ids: list[str]


def _empty_stage_group_runs() -> list[DashboardPipelineRun]:
    return []


def _empty_llm_analyses() -> list[DashboardLLMAnalysis]:
    return []


def _empty_portfolio_snapshots() -> list[DashboardPortfolioSnapshot]:
    return []


def _empty_review_reports() -> list[DashboardReviewReport]:
    return []


def _empty_runs() -> list[DashboardPipelineRun]:
    return []


def _empty_watchlist() -> list[DashboardWatchlistItem]:
    return []


def _empty_signals() -> list[DashboardSignalItem]:
    return []


def _empty_risk_decisions() -> list[DashboardRiskDecision]:
    return []


def _empty_paper_orders() -> list[DashboardPaperOrder]:
    return []


def _empty_execution_events() -> list[DashboardExecutionEvent]:
    return []


def _empty_positions() -> list[DashboardPosition]:
    return []


def _empty_source_snapshots() -> list[DashboardSourceSnapshot]:
    return []


def _empty_intraday_source_health() -> list[DashboardIntradaySourceHealth]:
    return []


def _unique_nonempty_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _empty_data_quality_reports() -> list[DashboardDataQualityReport]:
    return []


def _empty_data_reliability_reports() -> list[DashboardDataReliabilityReport]:
    return []


@dataclass(frozen=True)
class DashboardStageRunGroupDetail:
    group: DashboardStageRunGroup
    runs: list[DashboardPipelineRun] = field(default_factory=_empty_stage_group_runs)
    watchlist: list[DashboardWatchlistItem] = field(default_factory=_empty_watchlist)
    signals: list[DashboardSignalItem] = field(default_factory=_empty_signals)
    llm_analyses: list[DashboardLLMAnalysis] = field(default_factory=_empty_llm_analyses)
    risk_decisions: list[DashboardRiskDecision] = field(default_factory=_empty_risk_decisions)
    paper_orders: list[DashboardPaperOrder] = field(default_factory=_empty_paper_orders)
    execution_events: list[DashboardExecutionEvent] = field(
        default_factory=_empty_execution_events
    )
    positions: list[DashboardPosition] = field(default_factory=_empty_positions)
    portfolio_snapshots: list[DashboardPortfolioSnapshot] = field(
        default_factory=_empty_portfolio_snapshots
    )
    review_reports: list[DashboardReviewReport] = field(default_factory=_empty_review_reports)
    source_snapshots: list[DashboardSourceSnapshot] = field(
        default_factory=_empty_source_snapshots
    )
    intraday_source_health: list[DashboardIntradaySourceHealth] = field(
        default_factory=_empty_intraday_source_health
    )
    data_quality_reports: list[DashboardDataQualityReport] = field(
        default_factory=_empty_data_quality_reports
    )
    data_reliability_reports: list[DashboardDataReliabilityReport] = field(
        default_factory=_empty_data_reliability_reports
    )


@dataclass(frozen=True)
class DashboardDaySummary:
    trade_date: str
    runs: list[DashboardPipelineRun] = field(default_factory=_empty_runs)
    watchlist: list[DashboardWatchlistItem] = field(default_factory=_empty_watchlist)
    signals: list[DashboardSignalItem] = field(default_factory=_empty_signals)
    llm_analysis: DashboardLLMAnalysis | None = None
    risk_decisions: list[DashboardRiskDecision] = field(default_factory=_empty_risk_decisions)
    paper_orders: list[DashboardPaperOrder] = field(default_factory=_empty_paper_orders)
    execution_events: list[DashboardExecutionEvent] = field(
        default_factory=_empty_execution_events
    )
    positions: list[DashboardPosition] = field(default_factory=_empty_positions)
    portfolio_snapshot: DashboardPortfolioSnapshot | None = None
    review_report: DashboardReviewReport | None = None
    source_snapshots: list[DashboardSourceSnapshot] = field(
        default_factory=_empty_source_snapshots
    )
    intraday_source_health: list[DashboardIntradaySourceHealth] = field(
        default_factory=_empty_intraday_source_health
    )
    trading_calendar: DashboardTradingCalendarDay | None = None
    data_quality_reports: list[DashboardDataQualityReport] = field(
        default_factory=_empty_data_quality_reports
    )
    data_reliability_reports: list[DashboardDataReliabilityReport] = field(
        default_factory=_empty_data_reliability_reports
    )


class DashboardQueryAgent:
    def __init__(self, repository: DashboardQueryRepository) -> None:
        self.repository = repository
        self.review_metrics_agent = ReviewMetricsAgent(repository)

    def list_pipeline_runs(self, limit: int = 50) -> list[DashboardPipelineRun]:
        rows = sorted(
            [
                row
                for row in self.repository.payload_rows("pipeline_runs")
                if _is_normal_row(row, "pipeline_runs")
            ],
            key=lambda row: _row_id(row, "pipeline_runs"),
            reverse=True,
        )
        return [self._pipeline_run(row) for row in rows[:limit]]

    def list_stage_run_groups(self, limit: int = 50) -> list[DashboardStageRunGroup]:
        rows = sorted(
            [
                row
                for row in self.repository.payload_rows("pipeline_runs")
                if _is_normal_row(row, "pipeline_runs")
            ],
            key=lambda row: _row_id(row, "pipeline_runs"),
            reverse=True,
        )
        grouped: dict[tuple[date, str], list[PayloadRecord]] = {}
        for row in rows:
            payload = _payload(row, "pipeline_runs")
            stage = _required_str(payload, "pipeline_runs", "stage")
            grouped.setdefault((_row_date(row, "pipeline_runs"), stage), []).append(row)

        groups = [
            self._stage_run_group(trade_day, stage, group_rows)
            for (trade_day, stage), group_rows in grouped.items()
        ]
        return sorted(groups, key=self._stage_run_group_sort_key)[:limit]

    def stage_run_group_detail(
        self,
        trade_date: date,
        stage: str,
    ) -> DashboardStageRunGroupDetail | None:
        rows = self._stage_run_rows(trade_date, stage)
        if not rows:
            return None
        group = self._stage_run_group(trade_date, stage, rows)
        member_run_ids = set(group.member_run_ids)
        run_stage_by_id = {run_id: stage for run_id in member_run_ids}

        return DashboardStageRunGroupDetail(
            group=group,
            runs=[self._pipeline_run(row) for row in rows],
            watchlist=self._rows_by_member_run(
                "watchlist_candidates",
                trade_date,
                member_run_ids,
                self._watchlist_item,
            ),
            signals=self._rows_by_member_run(
                "signals",
                trade_date,
                member_run_ids,
                self._signal_item,
            ),
            llm_analyses=self._rows_by_member_run(
                "llm_analyses",
                trade_date,
                member_run_ids,
                self._llm_analysis,
            ),
            risk_decisions=self._rows_by_member_run(
                "risk_decisions",
                trade_date,
                member_run_ids,
                self._risk_decision,
            ),
            paper_orders=(
                self._rows_by_member_run(
                    "paper_orders",
                    trade_date,
                    member_run_ids,
                    self._paper_order,
                )
                if stage == "intraday_watch"
                else []
            ),
            execution_events=self._execution_events_for_rows(rows),
            positions=self._rows_by_member_run(
                "paper_positions",
                trade_date,
                member_run_ids,
                lambda row: self._position(row, trade_date),
            ),
            portfolio_snapshots=self._rows_by_member_run(
                "portfolio_snapshots",
                trade_date,
                member_run_ids,
                self._portfolio_snapshot,
            ),
            review_reports=self._rows_by_member_run(
                "review_reports",
                trade_date,
                member_run_ids,
                self._review_report,
            ),
            source_snapshots=self._source_snapshots_for_member_runs(
                trade_date,
                member_run_ids,
                run_stage_by_id,
            ),
            intraday_source_health=self._intraday_source_health_for_member_runs(
                trade_date,
                member_run_ids,
                run_stage_by_id,
            ),
            data_quality_reports=self._rows_by_member_run(
                "data_quality_reports",
                trade_date,
                member_run_ids,
                self._data_quality_report,
            ),
            data_reliability_reports=self._rows_by_member_run(
                "data_reliability_reports",
                trade_date,
                member_run_ids,
                self._data_reliability_report,
            ),
        )

    def list_backtests(self, limit: int = 50) -> list[DashboardBacktest]:
        rows: list[PayloadRecord] = []
        seen_backtest_ids: set[str] = set()
        for row in sorted(
            self.repository.payload_rows("pipeline_runs"),
            key=lambda item: _row_id(item, "pipeline_runs"),
            reverse=True,
        ):
            if not self._is_backtest_summary(row):
                continue
            backtest_id = _required_str(
                _payload(row, "pipeline_runs"),
                "pipeline_runs",
                "backtest_id",
            )
            if backtest_id in seen_backtest_ids:
                continue
            seen_backtest_ids.add(backtest_id)
            rows.append(row)
            if len(rows) >= limit:
                break
        return [self._backtest(row) for row in rows]

    def strategy_comparison(self, backtest_ids: list[str]) -> DashboardStrategyComparison:
        requested_ids = _unique_nonempty_strings(backtest_ids)
        items: list[DashboardStrategyComparisonItem] = []
        for backtest_id in requested_ids:
            summary_row = self._latest_backtest_summary_row(backtest_id)
            if summary_row is None:
                continue
            payload = _payload(summary_row, "pipeline_runs")
            if not payload.get("strategy_params_version"):
                continue
            items.append(self._strategy_comparison_item(backtest_id, payload))
        return DashboardStrategyComparison(backtest_ids=requested_ids, items=items)

    def list_strategy_evaluations(self, limit: int = 50) -> list[DashboardStrategyEvaluation]:
        rows: list[PayloadRecord] = []
        seen_evaluation_ids: set[str] = set()
        for row in sorted(
            self.repository.payload_rows("pipeline_runs"),
            key=lambda item: _row_id(item, "pipeline_runs"),
            reverse=True,
        ):
            if not self._is_strategy_evaluation_row(row):
                continue
            payload = _payload(row, "pipeline_runs")
            evaluation_id = _required_str(payload, "pipeline_runs", "evaluation_id")
            if evaluation_id in seen_evaluation_ids:
                continue
            seen_evaluation_ids.add(evaluation_id)
            rows.append(row)
            if len(rows) >= limit:
                break
        return [self._strategy_evaluation(row) for row in rows]

    def strategy_evaluation(self, evaluation_id: str) -> DashboardStrategyEvaluation | None:
        row = self._latest_strategy_evaluation_row(evaluation_id)
        if row is None:
            return None
        return self._strategy_evaluation(row)

    def list_strategy_insights(self, limit: int = 50) -> list[DashboardStrategyInsight]:
        rows: list[PayloadRecord] = []
        seen_insight_ids: set[str] = set()
        for row in sorted(
            self.repository.payload_rows("pipeline_runs"),
            key=lambda item: _row_id(item, "pipeline_runs"),
            reverse=True,
        ):
            if not self._is_strategy_insight_row(row):
                continue
            payload = _payload(row, "pipeline_runs")
            insight_id = _required_str(payload, "pipeline_runs", "insight_id")
            if insight_id in seen_insight_ids:
                continue
            seen_insight_ids.add(insight_id)
            rows.append(row)
            if len(rows) >= limit:
                break
        return [self._strategy_insight(row) for row in rows]

    def strategy_insight(self, insight_id: str) -> DashboardStrategyInsight | None:
        row = self._latest_strategy_insight_row(insight_id)
        if row is None:
            return None
        return self._strategy_insight(row)

    def day_summary(self, trade_date: date) -> DashboardDaySummary:
        runs = self._pipeline_runs_for_day(trade_date)
        run_stage_by_id = {run.run_id: run.stage for run in runs}
        pre_market_run_id = self._latest_successful_run_id(trade_date, "pre_market")

        return DashboardDaySummary(
            trade_date=trade_date.isoformat(),
            runs=runs,
            watchlist=self.watchlist(trade_date, pre_market_run_id),
            signals=self.signals(trade_date, pre_market_run_id),
            llm_analysis=self.llm_analysis(trade_date, pre_market_run_id),
            risk_decisions=self.risk_decisions(trade_date, pre_market_run_id),
            paper_orders=self.paper_orders(trade_date),
            execution_events=self.execution_events(trade_date),
            positions=self.positions_as_of(trade_date),
            portfolio_snapshot=self.latest_portfolio_snapshot(trade_date),
            review_report=self.latest_review_report(trade_date),
            source_snapshots=self.source_snapshots(trade_date, run_stage_by_id),
            intraday_source_health=self.intraday_source_health(trade_date, run_stage_by_id),
            trading_calendar=self.trading_calendar_day(trade_date),
            data_quality_reports=self.data_quality_reports(trade_date),
            data_reliability_reports=self.data_reliability_reports(trade_date),
        )

    def trends(self, start_date: date, end_date: date) -> DashboardTrendSummary:
        if start_date > end_date:
            raise ValueError("start_date 不能晚于 end_date")

        latest_pre_market_run_id_by_date = self._latest_successful_run_ids_by_date(
            start_date,
            end_date,
            "pre_market",
        )
        trend_dates = self._trend_dates(start_date, end_date, latest_pre_market_run_id_by_date)
        portfolio_total_value_by_date = self._portfolio_total_values_by_date(
            start_date,
            end_date,
        )
        quality_by_date = self._data_quality_trends_by_date(start_date, end_date)
        reliability_by_date = self._data_reliability_trends_by_date(start_date, end_date)
        risk_reject_reasons: Counter[str] = Counter()
        points: list[DashboardTrendPoint] = []

        for trade_day in trend_dates:
            run_id = latest_pre_market_run_id_by_date.get(trade_day)
            signals = self.signals(trade_day, run_id) if run_id is not None else []
            risk_decisions = self.risk_decisions(trade_day, run_id) if run_id is not None else []
            approved_count = len([decision for decision in risk_decisions if decision.approved])
            rejected_decisions = [decision for decision in risk_decisions if not decision.approved]
            for decision in rejected_decisions:
                risk_reject_reasons.update(decision.reasons)
            source_failure_rate, blocked_count, warning_count = quality_by_date.get(
                trade_day,
                (0.0, 0, 0),
            )
            reliability_status, reliability_source_failure_rate, reliability_gap_count = (
                reliability_by_date.get(trade_day, ("none", 0.0, 0))
            )
            points.append(
                DashboardTrendPoint(
                    trade_date=trade_day.isoformat(),
                    total_value=portfolio_total_value_by_date.get(trade_day),
                    signal_count=len(signals),
                    approved_count=approved_count,
                    rejected_count=len(rejected_decisions),
                    max_signal_score=max((signal.score for signal in signals), default=None),
                    source_failure_rate=source_failure_rate,
                    blocked_count=blocked_count,
                    warning_count=warning_count,
                    reliability_status=reliability_status,
                    reliability_source_failure_rate=reliability_source_failure_rate,
                    reliability_missing_market_bar_count=reliability_gap_count,
                )
            )

        return DashboardTrendSummary(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            points=points,
            risk_reject_reasons=dict(risk_reject_reasons),
        )

    def watchlist(
        self,
        trade_date: date,
        run_id: str | None = None,
    ) -> list[DashboardWatchlistItem]:
        run_id = run_id or self._latest_successful_run_id(trade_date, "pre_market")
        if run_id is None:
            return []
        return [
            self._watchlist_item(row)
            for row in self.repository.payload_rows(
                "watchlist_candidates",
                trade_date=trade_date,
                run_id=run_id,
            )
        ]

    def signals(
        self,
        trade_date: date,
        run_id: str | None = None,
    ) -> list[DashboardSignalItem]:
        run_id = run_id or self._latest_successful_run_id(trade_date, "pre_market")
        if run_id is None:
            return []
        return [
            self._signal_item(row)
            for row in self.repository.payload_rows("signals", trade_date=trade_date, run_id=run_id)
        ]

    def llm_analysis(
        self,
        trade_date: date,
        run_id: str | None = None,
    ) -> DashboardLLMAnalysis | None:
        run_id = run_id or self._latest_successful_run_id(trade_date, "pre_market")
        if run_id is None:
            return None
        rows = self.repository.payload_rows(
            "llm_analyses",
            trade_date=trade_date,
            run_id=run_id,
        )
        if not rows:
            return None
        return self._llm_analysis(rows[-1])

    def risk_decisions(
        self,
        trade_date: date,
        run_id: str | None = None,
    ) -> list[DashboardRiskDecision]:
        run_id = run_id or self._latest_successful_run_id(trade_date, "pre_market")
        if run_id is None:
            return []
        return [
            self._risk_decision(row)
            for row in self.repository.payload_rows(
                "risk_decisions",
                trade_date=trade_date,
                run_id=run_id,
            )
        ]

    def paper_orders(self, trade_date: date) -> list[DashboardPaperOrder]:
        intraday_run_id = self._latest_successful_run_id(trade_date, "intraday_watch")
        if intraday_run_id is None:
            return []
        return [
            self._paper_order(row)
            for row in self.repository.payload_rows(
                "paper_orders",
                trade_date=trade_date,
                run_id=intraday_run_id,
            )
            if _is_normal_row(row, "paper_orders")
        ]

    def execution_events(self, trade_date: date) -> list[DashboardExecutionEvent]:
        intraday_run_id = self._latest_successful_run_id(trade_date, "intraday_watch")
        if intraday_run_id is None:
            return []
        rows = self.repository.payload_rows(
            "pipeline_runs",
            trade_date=trade_date,
            run_id=intraday_run_id,
        )
        if not rows:
            return []
        payload = _payload(rows[-1], "pipeline_runs")
        raw_events = payload.get("execution_events", [])
        if not isinstance(raw_events, list):
            raise ValueError("pipeline_runs 字段 execution_events 必须是 list")
        return [
            self._execution_event(item, intraday_run_id)
            for item in cast(list[object], raw_events)
        ]

    def positions_as_of(self, trade_date: date) -> list[DashboardPosition]:
        latest_by_symbol: dict[str, PayloadRecord] = {}
        for row in self.repository.payload_rows("paper_positions"):
            if not _is_normal_row(row, "paper_positions"):
                continue
            if _row_date(row, "paper_positions") > trade_date:
                continue
            payload = _payload(row, "paper_positions")
            symbol = _required_str(payload, "paper_positions", "symbol")
            latest_by_symbol[symbol] = row
        return [
            self._position(row, trade_date)
            for row in sorted(
                latest_by_symbol.values(),
                key=lambda item: _row_id(item, "paper_positions"),
            )
        ]

    def latest_portfolio_snapshot(self, trade_date: date) -> DashboardPortfolioSnapshot | None:
        rows = [
            row
            for row in self.repository.payload_rows("portfolio_snapshots")
            if _is_normal_row(row, "portfolio_snapshots")
            and _row_date(row, "portfolio_snapshots") <= trade_date
        ]
        if not rows:
            return None
        return self._portfolio_snapshot(rows[-1])

    def latest_review_report(self, trade_date: date) -> DashboardReviewReport | None:
        rows = [
            row
            for row in self.repository.payload_rows("review_reports", trade_date=trade_date)
            if _is_normal_row(row, "review_reports")
        ]
        if not rows:
            return None
        return self._review_report(rows[-1])

    def source_snapshots(
        self,
        trade_date: date,
        run_stage_by_id: Mapping[str, str] | None = None,
    ) -> list[DashboardSourceSnapshot]:
        stages = run_stage_by_id or {
            run.run_id: run.stage for run in self._pipeline_runs_for_day(trade_date)
        }
        return [
            self._source_snapshot(row, stages)
            for row in self.repository.payload_rows("raw_source_snapshots", trade_date=trade_date)
            if _is_normal_row(row, "raw_source_snapshots")
        ]

    def intraday_source_health(
        self,
        trade_date: date,
        run_stage_by_id: Mapping[str, str] | None = None,
    ) -> list[DashboardIntradaySourceHealth]:
        stages = run_stage_by_id or {
            run.run_id: run.stage for run in self._pipeline_runs_for_day(trade_date)
        }
        items: list[DashboardIntradaySourceHealth] = []
        for row in self.repository.payload_rows("raw_source_snapshots", trade_date=trade_date):
            if not _is_normal_row(row, "raw_source_snapshots"):
                continue
            items.extend(self._intraday_source_health_items(row, stages))
        return items

    def data_quality_reports(self, trade_date: date) -> list[DashboardDataQualityReport]:
        return [
            self._data_quality_report(row)
            for row in self.repository.payload_rows("data_quality_reports", trade_date=trade_date)
            if _is_normal_row(row, "data_quality_reports")
        ]

    def trading_calendar_day(self, trade_date: date) -> DashboardTradingCalendarDay | None:
        rows = self.repository.trading_calendar_days(start_date=trade_date, end_date=trade_date)
        if not rows:
            return None
        row = rows[-1]
        return DashboardTradingCalendarDay(
            trade_date=row.calendar_date.isoformat(),
            is_trade_date=row.is_trade_date,
            source=row.source,
            collected_at=row.collected_at.isoformat(),
        )

    def data_reliability_reports(self, trade_date: date) -> list[DashboardDataReliabilityReport]:
        return [
            self._data_reliability_report(row)
            for row in self.repository.payload_rows(
                "data_reliability_reports",
                trade_date=trade_date,
            )
        ]

    def _pipeline_runs_for_day(self, trade_date: date) -> list[DashboardPipelineRun]:
        rows = sorted(
            [
                row
                for row in self.repository.payload_rows("pipeline_runs", trade_date=trade_date)
                if _is_normal_row(row, "pipeline_runs")
            ],
            key=lambda row: _row_id(row, "pipeline_runs"),
            reverse=True,
        )
        return [self._pipeline_run(row) for row in rows]

    def _stage_run_rows(self, trade_date: date, stage: str) -> list[PayloadRecord]:
        return sorted(
            [
                row
                for row in self.repository.payload_rows("pipeline_runs", trade_date=trade_date)
                if _is_normal_row(row, "pipeline_runs")
                and _payload(row, "pipeline_runs").get("stage") == stage
            ],
            key=lambda row: _row_id(row, "pipeline_runs"),
            reverse=True,
        )

    def _stage_run_group(
        self,
        trade_date: date,
        stage: str,
        rows: list[PayloadRecord],
    ) -> DashboardStageRunGroup:
        if not rows:
            raise ValueError("阶段组必须至少包含一个 pipeline run")
        runs = [self._pipeline_run(row) for row in rows]
        success_count = len([run for run in runs if run.status == "success"])
        failed_count = len([run for run in runs if run.status == "failed"])
        skipped_count = len([run for run in runs if run.status == "skipped"])
        warning_count = len([run for run in runs if run.status == "warning"])
        latest_success = next((run for run in runs if run.status == "success"), None)
        failure_reasons = _unique_nonempty_strings(
            [run.failure_reason or "" for run in runs if run.status == "failed"]
        )
        return DashboardStageRunGroup(
            group_id=f"{trade_date.isoformat()}:{stage}",
            trade_date=trade_date.isoformat(),
            stage=stage,
            status=_stage_group_status(
                total_count=len(runs),
                success_count=success_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                warning_count=warning_count,
            ),
            total_run_count=len(runs),
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            latest_run_id=runs[0].run_id,
            latest_success_run_id=latest_success.run_id if latest_success is not None else None,
            member_run_ids=[run.run_id for run in runs],
            failure_reasons=failure_reasons,
            created_at=runs[0].created_at,
        )

    def _latest_group_row_id(self, run_ids: list[str]) -> int:
        member_run_ids = set(run_ids)
        return max(
            (
                _row_id(row, "pipeline_runs")
                for row in self.repository.payload_rows("pipeline_runs")
                if _row_run_id(row, "pipeline_runs") in member_run_ids
            ),
            default=0,
        )

    def _stage_run_group_sort_key(self, group: DashboardStageRunGroup) -> tuple[int, int, int]:
        trade_day = date.fromisoformat(group.trade_date)
        stage_order = _STAGE_RUN_GROUP_ORDER.get(
            group.stage,
            len(_STAGE_RUN_GROUP_ORDER),
        )
        return (
            -trade_day.toordinal(),
            stage_order,
            -self._latest_group_row_id(group.member_run_ids),
        )

    def _rows_by_member_run(
        self,
        table_name: str,
        trade_date: date,
        member_run_ids: set[str],
        convert: Callable[[PayloadRecord], DashboardRowDto],
    ) -> list[DashboardRowDto]:
        rows = sorted(
            [
                row
                for row in self.repository.payload_rows(table_name, trade_date=trade_date)
                if _is_normal_row(row, table_name)
                and _row_run_id(row, table_name) in member_run_ids
            ],
            key=lambda row: _row_id(row, table_name),
            reverse=True,
        )
        return [convert(row) for row in rows]

    def _execution_events_for_rows(
        self,
        rows: list[PayloadRecord],
    ) -> list[DashboardExecutionEvent]:
        events: list[DashboardExecutionEvent] = []
        for row in rows:
            payload = _payload(row, "pipeline_runs")
            raw_events = payload.get("execution_events", [])
            if not isinstance(raw_events, list):
                raise ValueError("pipeline_runs 字段 execution_events 必须是 list")
            run_id = _row_run_id(row, "pipeline_runs")
            events.extend(
                self._execution_event(item, run_id) for item in cast(list[object], raw_events)
            )
        return events

    def _source_snapshots_for_member_runs(
        self,
        trade_date: date,
        member_run_ids: set[str],
        run_stage_by_id: Mapping[str, str],
    ) -> list[DashboardSourceSnapshot]:
        rows = sorted(
            [
                row
                for row in self.repository.payload_rows(
                    "raw_source_snapshots",
                    trade_date=trade_date,
                )
                if _is_normal_row(row, "raw_source_snapshots")
                and _row_run_id(row, "raw_source_snapshots") in member_run_ids
            ],
            key=lambda row: _row_id(row, "raw_source_snapshots"),
            reverse=True,
        )
        return [self._source_snapshot(row, run_stage_by_id) for row in rows]

    def _intraday_source_health_for_member_runs(
        self,
        trade_date: date,
        member_run_ids: set[str],
        run_stage_by_id: Mapping[str, str],
    ) -> list[DashboardIntradaySourceHealth]:
        items: list[DashboardIntradaySourceHealth] = []
        rows = sorted(
            [
                row
                for row in self.repository.payload_rows(
                    "raw_source_snapshots",
                    trade_date=trade_date,
                )
                if _is_normal_row(row, "raw_source_snapshots")
                and _row_run_id(row, "raw_source_snapshots") in member_run_ids
            ],
            key=lambda row: _row_id(row, "raw_source_snapshots"),
            reverse=True,
        )
        for row in rows:
            items.extend(self._intraday_source_health_items(row, run_stage_by_id))
        return items

    def _is_backtest_summary(self, row: PayloadRecord) -> bool:
        payload = _payload(row, "pipeline_runs")
        return (
            payload.get("stage") == "backtest"
            and payload.get("run_mode") == "backtest"
            and bool(payload.get("backtest_id"))
            and bool(payload.get("strategy_params_version"))
        )

    def _is_strategy_evaluation_row(self, row: PayloadRecord) -> bool:
        payload = _payload(row, "pipeline_runs")
        return (
            payload.get("stage") == "strategy_evaluation"
            and payload.get("run_mode") == "backtest"
            and bool(payload.get("evaluation_id"))
        )

    def _is_strategy_insight_row(self, row: PayloadRecord) -> bool:
        payload = _payload(row, "pipeline_runs")
        return (
            payload.get("stage") == "strategy_insight"
            and payload.get("run_mode", "normal") == "normal"
            and bool(payload.get("insight_id"))
        )

    def _latest_backtest_summary_row(self, backtest_id: str) -> PayloadRecord | None:
        latest: PayloadRecord | None = None
        for row in self.repository.payload_rows("pipeline_runs"):
            payload = _payload(row, "pipeline_runs")
            if (
                payload.get("stage") == "backtest"
                and payload.get("run_mode") == "backtest"
                and payload.get("backtest_id") == backtest_id
                and (
                    latest is None
                    or _row_id(row, "pipeline_runs") > _row_id(latest, "pipeline_runs")
                )
            ):
                latest = row
        return latest

    def _latest_strategy_evaluation_row(self, evaluation_id: str) -> PayloadRecord | None:
        latest: PayloadRecord | None = None
        for row in self.repository.payload_rows("pipeline_runs"):
            if not self._is_strategy_evaluation_row(row):
                continue
            payload = _payload(row, "pipeline_runs")
            if payload.get("evaluation_id") != evaluation_id:
                continue
            if latest is None or _row_id(row, "pipeline_runs") > _row_id(latest, "pipeline_runs"):
                latest = row
        return latest

    def _latest_strategy_insight_row(self, insight_id: str) -> PayloadRecord | None:
        latest: PayloadRecord | None = None
        for row in self.repository.payload_rows("pipeline_runs"):
            if not self._is_strategy_insight_row(row):
                continue
            payload = _payload(row, "pipeline_runs")
            if payload.get("insight_id") != insight_id:
                continue
            if latest is None or _row_id(row, "pipeline_runs") > _row_id(latest, "pipeline_runs"):
                latest = row
        return latest

    def _backtest_rows(self, table_name: str, backtest_id: str) -> list[PayloadRecord]:
        return [
            row
            for row in self.repository.payload_rows(table_name)
            if _payload(row, table_name).get("run_mode") == "backtest"
            and _payload(row, table_name).get("backtest_id") == backtest_id
        ]

    def _latest_successful_run_id(self, trade_date: date, stage: str) -> str | None:
        rows = self.repository.payload_rows("pipeline_runs", trade_date=trade_date)
        for row in reversed(rows):
            if not _is_normal_row(row, "pipeline_runs"):
                continue
            payload = _payload(row, "pipeline_runs")
            if payload.get("stage") == stage and payload.get("status") == "success":
                return _row_run_id(row, "pipeline_runs")
        return None

    def _latest_successful_run_ids_by_date(
        self,
        start_date: date,
        end_date: date,
        stage: str,
    ) -> dict[date, str]:
        latest_by_date: dict[date, str] = {}
        for row in sorted(
            self.repository.payload_rows("pipeline_runs"),
            key=lambda item: _row_id(item, "pipeline_runs"),
        ):
            trade_day = _row_date(row, "pipeline_runs")
            if trade_day < start_date or trade_day > end_date:
                continue
            if not _is_normal_row(row, "pipeline_runs"):
                continue
            payload = _payload(row, "pipeline_runs")
            if payload.get("stage") == stage and payload.get("status") == "success":
                latest_by_date[trade_day] = _row_run_id(row, "pipeline_runs")
        return latest_by_date

    def _trend_dates(
        self,
        start_date: date,
        end_date: date,
        latest_pre_market_run_id_by_date: Mapping[date, str],
    ) -> list[date]:
        trend_dates = set(latest_pre_market_run_id_by_date)
        for table_name in (
            "pipeline_runs",
            "portfolio_snapshots",
            "data_quality_reports",
            "data_reliability_reports",
        ):
            for row in self.repository.payload_rows(table_name):
                if not _is_normal_row(row, table_name):
                    continue
                trade_day = _row_date(row, table_name)
                if start_date <= trade_day <= end_date:
                    trend_dates.add(trade_day)
        return sorted(trend_dates)

    def _portfolio_total_values_by_date(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, str]:
        latest_by_date: dict[date, str] = {}
        for row in sorted(
            self.repository.payload_rows("portfolio_snapshots"),
            key=lambda item: _row_id(item, "portfolio_snapshots"),
        ):
            trade_day = _row_date(row, "portfolio_snapshots")
            if start_date <= trade_day <= end_date:
                if not _is_normal_row(row, "portfolio_snapshots"):
                    continue
                latest_by_date[trade_day] = self._portfolio_snapshot(row).total_value
        return latest_by_date

    def _data_quality_trends_by_date(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, tuple[float, int, int]]:
        source_failure_rate_by_date: dict[date, float] = {}
        blocked_count_by_date: Counter[date] = Counter()
        warning_count_by_date: Counter[date] = Counter()

        for row in self.repository.payload_rows("data_quality_reports"):
            trade_day = _row_date(row, "data_quality_reports")
            if trade_day < start_date or trade_day > end_date:
                continue
            if not _is_normal_row(row, "data_quality_reports"):
                continue
            report = self._data_quality_report(row)
            source_failure_rate_by_date[trade_day] = max(
                source_failure_rate_by_date.get(trade_day, 0.0),
                report.source_failure_rate,
            )
            if report.status == "failed":
                blocked_count_by_date[trade_day] += 1
            warning_count_by_date[trade_day] += len(
                [issue for issue in report.issues if issue.severity == "warning"]
            )

        return {
            trade_day: (
                source_failure_rate_by_date.get(trade_day, 0.0),
                blocked_count_by_date[trade_day],
                warning_count_by_date[trade_day],
            )
            for trade_day in set(source_failure_rate_by_date)
            | set(blocked_count_by_date)
            | set(warning_count_by_date)
        }

    def _data_reliability_trends_by_date(
        self,
        start_date: date,
        end_date: date,
    ) -> dict[date, tuple[str, float, int]]:
        order = {"none": 0, "passed": 1, "skipped": 1, "warning": 2, "failed": 3}
        status_by_date: dict[date, str] = {}
        source_failure_rate_by_date: dict[date, float] = {}
        missing_count_by_date: Counter[date] = Counter()
        for row in self.repository.payload_rows("data_reliability_reports"):
            trade_day = _row_date(row, "data_reliability_reports")
            if trade_day < start_date or trade_day > end_date:
                continue
            report = self._data_reliability_report(row)
            current_status = status_by_date.get(trade_day, "none")
            if order[report.status] >= order[current_status]:
                status_by_date[trade_day] = report.status
            source_failure_rate_by_date[trade_day] = max(
                source_failure_rate_by_date.get(trade_day, 0.0),
                report.source_failure_rate,
            )
            missing_count_by_date[trade_day] += report.missing_market_bar_count
        return {
            trade_day: (
                status_by_date.get(trade_day, "none"),
                source_failure_rate_by_date.get(trade_day, 0.0),
                missing_count_by_date[trade_day],
            )
            for trade_day in set(status_by_date)
            | set(source_failure_rate_by_date)
            | set(missing_count_by_date)
        }

    def _pipeline_run(self, row: PayloadRecord) -> DashboardPipelineRun:
        payload = _payload(row, "pipeline_runs")
        return DashboardPipelineRun(
            run_id=_row_run_id(row, "pipeline_runs"),
            trade_date=_row_date(row, "pipeline_runs").isoformat(),
            stage=_required_str(payload, "pipeline_runs", "stage"),
            status=_required_str(payload, "pipeline_runs", "status"),
            report_path=_optional_str(payload.get("report_path")),
            failure_reason=_optional_str(payload.get("failure_reason")),
            created_at=_optional_str(payload.get("created_at")),
        )

    def _backtest(self, row: PayloadRecord) -> DashboardBacktest:
        payload = _payload(row, "pipeline_runs")
        return DashboardBacktest(
            backtest_id=_required_str(payload, "pipeline_runs", "backtest_id"),
            strategy_params_version=_required_str(
                payload,
                "pipeline_runs",
                "strategy_params_version",
            ),
            provider=_required_str(payload, "pipeline_runs", "provider"),
            start_date=_required_str(payload, "pipeline_runs", "start_date"),
            end_date=_required_str(payload, "pipeline_runs", "end_date"),
            status=_required_str(payload, "pipeline_runs", "status"),
            attempted_days=_required_int(payload, "pipeline_runs", "attempted_days"),
            succeeded_days=_required_int(payload, "pipeline_runs", "succeeded_days"),
            failed_days=_required_int(payload, "pipeline_runs", "failed_days"),
            created_at=_optional_str(payload.get("created_at")),
        )

    def _strategy_comparison_item(
        self,
        backtest_id: str,
        summary_payload: Mapping[str, object],
    ) -> DashboardStrategyComparisonItem:
        attempted_days = _required_int(summary_payload, "pipeline_runs", "attempted_days")
        return DashboardStrategyComparisonItem(
            backtest_id=backtest_id,
            strategy_params_version=_required_str(
                summary_payload,
                "pipeline_runs",
                "strategy_params_version",
            ),
            provider=_required_str(summary_payload, "pipeline_runs", "provider"),
            start_date=_required_str(summary_payload, "pipeline_runs", "start_date"),
            end_date=_required_str(summary_payload, "pipeline_runs", "end_date"),
            attempted_days=attempted_days,
            succeeded_days=_required_int(summary_payload, "pipeline_runs", "succeeded_days"),
            failed_days=_required_int(summary_payload, "pipeline_runs", "failed_days"),
            win_rate=self._backtest_win_rate(backtest_id),
            max_drawdown=self._backtest_max_drawdown(backtest_id),
            total_return=self._backtest_total_return(backtest_id, summary_payload),
            risk_reject_rate=self._backtest_risk_reject_rate(backtest_id),
            data_quality_failure_rate=self._backtest_data_quality_failure_rate(
                backtest_id,
                attempted_days,
            ),
        )

    def _strategy_evaluation(self, row: PayloadRecord) -> DashboardStrategyEvaluation:
        payload = _payload(row, "pipeline_runs")
        raw_variants = _required_list(payload, "pipeline_runs", "variants")
        variants = _strategy_evaluation_variants(raw_variants, payload)
        recommendation_payload = _required_mapping(payload, "pipeline_runs", "recommendation")
        return DashboardStrategyEvaluation(
            evaluation_id=_required_str(payload, "pipeline_runs", "evaluation_id"),
            provider=_required_str(payload, "pipeline_runs", "provider"),
            start_date=_required_str(payload, "pipeline_runs", "start_date"),
            end_date=_required_str(payload, "pipeline_runs", "end_date"),
            report_path=_required_str(payload, "pipeline_runs", "report_path"),
            variant_count=_required_int(payload, "pipeline_runs", "variant_count"),
            recommendation=DashboardStrategyEvaluationRecommendation(
                summary=_required_str(
                    recommendation_payload,
                    "pipeline_runs.recommendation",
                    "summary",
                ),
                recommended_variant_ids=_required_str_list(
                    recommendation_payload,
                    "pipeline_runs.recommendation",
                    "recommended_variant_ids",
                ),
            ),
            variants=variants,
        )

    def _strategy_insight(self, row: PayloadRecord) -> DashboardStrategyInsight:
        payload = _payload(row, "pipeline_runs")
        gate_summary = _required_mapping(payload, "pipeline_runs", "gate_summary")
        return DashboardStrategyInsight(
            insight_id=_required_str(payload, "pipeline_runs", "insight_id"),
            trade_date=str(payload.get("trade_date") or _row_date(row, "pipeline_runs")),
            provider=_required_str(payload, "pipeline_runs", "provider"),
            summary=_required_str(payload, "pipeline_runs", "summary"),
            attribution=_required_str_list(payload, "pipeline_runs", "attribution"),
            manual_status=_strategy_insight_status(
                _required_str(payload, "pipeline_runs", "manual_status")
            ),
            report_path=_required_str(payload, "pipeline_runs", "report_path"),
            hypotheses=_strategy_insight_hypotheses(
                _required_list(payload, "pipeline_runs", "hypotheses")
            ),
            experiments=_strategy_insight_experiments(
                _required_list(payload, "pipeline_runs", "experiments")
            ),
            evaluation_windows=_strategy_insight_windows(
                _required_list(payload, "pipeline_runs", "evaluation_windows")
            ),
            recommended_variant_ids=_required_str_list(
                gate_summary,
                "pipeline_runs.gate_summary",
                "recommended_variant_ids",
            ),
        )

    def _backtest_win_rate(self, backtest_id: str) -> float:
        latest_positions_by_symbol: dict[str, PayloadRecord] = {}
        for row in self._backtest_rows("paper_positions", backtest_id):
            payload = _payload(row, "paper_positions")
            symbol = _required_str(payload, "paper_positions", "symbol")
            latest_positions_by_symbol[symbol] = row
        closed_positions = [
            _payload(row, "paper_positions")
            for row in latest_positions_by_symbol.values()
            if _required_str(_payload(row, "paper_positions"), "paper_positions", "status")
            == "closed"
        ]
        if not closed_positions:
            return 0.0
        wins = 0
        for payload in closed_positions:
            entry = _required_decimal_value(payload, "paper_positions", "entry_price")
            exit_price = _required_decimal_value(payload, "paper_positions", "exit_price")
            if exit_price > entry:
                wins += 1
        return wins / len(closed_positions)

    def _backtest_max_drawdown(self, backtest_id: str) -> float:
        values = [
            _required_decimal_value(
                _payload(row, "portfolio_snapshots"),
                "portfolio_snapshots",
                "total_value",
            )
            for row in sorted(
                self._backtest_rows("portfolio_snapshots", backtest_id),
                key=lambda item: _row_id(item, "portfolio_snapshots"),
            )
        ]
        peak: Decimal | None = None
        max_drawdown = Decimal("0")
        for value in values:
            peak = value if peak is None else max(peak, value)
            if peak == 0:
                continue
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        return float(max_drawdown)

    def _backtest_total_return(
        self,
        backtest_id: str,
        summary_payload: Mapping[str, object],
    ) -> float:
        snapshots = sorted(
            self._backtest_rows("portfolio_snapshots", backtest_id),
            key=lambda item: _row_id(item, "portfolio_snapshots"),
        )
        if not snapshots:
            return 0.0
        latest_total = _required_decimal_value(
            _payload(snapshots[-1], "portfolio_snapshots"),
            "portfolio_snapshots",
            "total_value",
        )
        strategy_snapshot = _required_mapping(
            summary_payload,
            "pipeline_runs",
            "strategy_params_snapshot",
        )
        paper_trader = _required_mapping(
            strategy_snapshot,
            "strategy_params_snapshot",
            "paper_trader",
        )
        initial_cash = _required_decimal_value(
            paper_trader,
            "strategy_params_snapshot.paper_trader",
            "initial_cash",
        )
        if initial_cash == 0:
            return 0.0
        return float((latest_total - initial_cash) / initial_cash)

    def _backtest_risk_reject_rate(self, backtest_id: str) -> float:
        decisions = [
            self._risk_decision(row)
            for row in self._backtest_rows("risk_decisions", backtest_id)
        ]
        if not decisions:
            return 0.0
        rejected = len([decision for decision in decisions if not decision.approved])
        return rejected / len(decisions)

    def _backtest_data_quality_failure_rate(self, backtest_id: str, attempted_days: int) -> float:
        if attempted_days <= 0:
            return 0.0
        failed_dates = {
            _required_date(
                _payload(row, "data_quality_reports"),
                "data_quality_reports",
                "trade_date",
            )
            for row in self._backtest_rows("data_quality_reports", backtest_id)
            if _required_str(
                _payload(row, "data_quality_reports"),
                "data_quality_reports",
                "status",
            )
            == "failed"
        }
        return len(failed_dates) / attempted_days

    def _watchlist_item(self, row: PayloadRecord) -> DashboardWatchlistItem:
        payload = _payload(row, "watchlist_candidates")
        return DashboardWatchlistItem(
            run_id=_row_run_id(row, "watchlist_candidates"),
            symbol=_required_str(payload, "watchlist_candidates", "symbol"),
            trade_date=_required_date(payload, "watchlist_candidates", "trade_date").isoformat(),
            score=_required_float(payload, "watchlist_candidates", "score"),
            score_breakdown=_float_mapping(
                _required_mapping(payload, "watchlist_candidates", "score_breakdown"),
                "watchlist_candidates",
                "score_breakdown",
            ),
            reasons=_required_str_list(payload, "watchlist_candidates", "reasons"),
        )

    def _signal_item(self, row: PayloadRecord) -> DashboardSignalItem:
        payload = _payload(row, "signals")
        action = _required_str(payload, "signals", "action")
        if action not in {"observe", "paper_buy", "paper_sell"}:
            raise ValueError(f"signals 字段 action 未知: {action}")
        return DashboardSignalItem(
            run_id=_row_run_id(row, "signals"),
            symbol=_required_str(payload, "signals", "symbol"),
            trade_date=_required_date(payload, "signals", "trade_date").isoformat(),
            action=action,
            score=_required_float(payload, "signals", "score"),
            score_breakdown=_float_mapping(
                _required_mapping(payload, "signals", "score_breakdown"),
                "signals",
                "score_breakdown",
            ),
            reasons=_required_str_list(payload, "signals", "reasons"),
        )

    def _llm_analysis(self, row: PayloadRecord) -> DashboardLLMAnalysis:
        payload = _payload(row, "llm_analyses")
        _required_mapping(payload, "llm_analyses", "raw_response")
        return DashboardLLMAnalysis(
            run_id=_row_run_id(row, "llm_analyses"),
            trade_date=_required_date(payload, "llm_analyses", "trade_date").isoformat(),
            model=_required_json_str(payload, "llm_analyses", "model"),
            summary=_required_json_str(payload, "llm_analyses", "summary"),
            key_points=_required_json_str_list(payload, "llm_analyses", "key_points"),
            risk_notes=_required_json_str_list(payload, "llm_analyses", "risk_notes"),
            created_at=_required_json_str(payload, "llm_analyses", "created_at"),
        )

    def _risk_decision(self, row: PayloadRecord) -> DashboardRiskDecision:
        payload = _payload(row, "risk_decisions")
        return DashboardRiskDecision(
            run_id=_row_run_id(row, "risk_decisions"),
            symbol=_required_str(payload, "risk_decisions", "symbol"),
            trade_date=_required_date(payload, "risk_decisions", "trade_date").isoformat(),
            signal_action=_required_str(payload, "risk_decisions", "signal_action"),
            approved=_required_bool(payload, "risk_decisions", "approved"),
            reasons=_required_str_list(payload, "risk_decisions", "reasons"),
            target_position_pct=_required_decimal(
                payload,
                "risk_decisions",
                "target_position_pct",
            ),
        )

    def _paper_order(self, row: PayloadRecord) -> DashboardPaperOrder:
        payload = _payload(row, "paper_orders")
        is_real_trade = _required_bool(payload, "paper_orders", "is_real_trade")
        if is_real_trade:
            raise ValueError("dashboard 查询层检测到真实交易订单，违反 v1 安全边界")
        side = _required_str(payload, "paper_orders", "side")
        if side not in {"buy", "sell"}:
            raise ValueError(f"paper_orders 字段 side 未知: {side}")
        return DashboardPaperOrder(
            run_id=_row_run_id(row, "paper_orders"),
            order_id=_required_str(payload, "paper_orders", "order_id"),
            symbol=_required_str(payload, "paper_orders", "symbol"),
            trade_date=_required_date(payload, "paper_orders", "trade_date").isoformat(),
            side=side,
            quantity=_required_int(payload, "paper_orders", "quantity"),
            price=_required_decimal(payload, "paper_orders", "price"),
            amount=_required_decimal(payload, "paper_orders", "amount"),
            slippage=_required_decimal(payload, "paper_orders", "slippage"),
            reason=_required_str(payload, "paper_orders", "reason"),
            is_real_trade=is_real_trade,
            execution_source=_optional_str(payload.get("execution_source")),
            execution_timestamp=_optional_str(payload.get("execution_timestamp")),
            execution_method=_optional_str(payload.get("execution_method")),
            reference_price=_optional_decimal(payload.get("reference_price"), "paper_orders"),
            used_daily_fallback=bool(payload.get("used_daily_fallback", False)),
            execution_failure_reason=_optional_str(payload.get("execution_failure_reason")),
            created_at=_optional_str(payload.get("created_at")),
        )

    def _execution_event(self, value: object, run_id: str) -> DashboardExecutionEvent:
        if not isinstance(value, Mapping):
            raise ValueError("pipeline_runs execution_events item 必须是 object")
        payload = cast(Mapping[str, object], value)
        status = _required_str(payload, "execution_events", "status")
        if status not in {"filled", "rejected"}:
            raise ValueError(f"execution_events 字段 status 未知: {status}")
        side = _required_str(payload, "execution_events", "side")
        if side not in {"buy", "sell"}:
            raise ValueError(f"execution_events 字段 side 未知: {side}")
        return DashboardExecutionEvent(
            run_id=run_id,
            symbol=_required_str(payload, "execution_events", "symbol"),
            trade_date=_required_date(payload, "execution_events", "trade_date").isoformat(),
            side=side,
            status=status,
            execution_method=_required_str(payload, "execution_events", "execution_method"),
            used_daily_fallback=_required_bool(
                payload,
                "execution_events",
                "used_daily_fallback",
            ),
            execution_source=_optional_str(payload.get("execution_source")),
            execution_timestamp=_optional_str(payload.get("execution_timestamp")),
            reference_price=_optional_decimal(payload.get("reference_price"), "execution_events"),
            estimated_price=_optional_decimal(payload.get("estimated_price"), "execution_events"),
            slippage=_optional_decimal(payload.get("slippage"), "execution_events"),
            failure_reason=_optional_str(payload.get("failure_reason")),
        )

    def _position(self, row: PayloadRecord, trade_date: date) -> DashboardPosition:
        payload = _payload(row, "paper_positions")
        status = _required_str(payload, "paper_positions", "status")
        if status not in {"open", "closed"}:
            raise ValueError(f"paper_positions 字段 status 未知: {status}")
        opened_at = _required_date(payload, "paper_positions", "opened_at")
        closed_at = _optional_date(payload.get("closed_at"), "paper_positions", "closed_at")
        entry_price = _required_decimal_value(payload, "paper_positions", "entry_price")
        current_price = _required_decimal_value(payload, "paper_positions", "current_price")
        exit_price = _optional_decimal_value(
            payload.get("exit_price"),
            "paper_positions",
            "exit_price",
        )
        mark_price = exit_price if exit_price is not None else current_price
        quantity = _required_int(payload, "paper_positions", "quantity")
        pnl_amount = (mark_price - entry_price) * Decimal(quantity)
        pnl_pct = Decimal("0") if entry_price == 0 else (mark_price - entry_price) / entry_price
        holding_end = closed_at or trade_date
        return DashboardPosition(
            run_id=_row_run_id(row, "paper_positions"),
            symbol=_required_str(payload, "paper_positions", "symbol"),
            opened_at=opened_at.isoformat(),
            quantity=quantity,
            entry_price=_decimal_text(entry_price),
            current_price=_decimal_text(current_price),
            status=status,
            closed_at=closed_at.isoformat() if closed_at is not None else None,
            exit_price=_decimal_text(exit_price) if exit_price is not None else None,
            pnl_amount=_decimal_text(pnl_amount.quantize(Decimal("0.01"))),
            pnl_pct=float(pnl_pct),
            holding_days=max((holding_end - opened_at).days, 0),
        )

    def _portfolio_snapshot(self, row: PayloadRecord) -> DashboardPortfolioSnapshot:
        payload = _payload(row, "portfolio_snapshots")
        return DashboardPortfolioSnapshot(
            run_id=_row_run_id(row, "portfolio_snapshots"),
            trade_date=_required_date(payload, "portfolio_snapshots", "trade_date").isoformat(),
            cash=_required_decimal(payload, "portfolio_snapshots", "cash"),
            market_value=_required_decimal(payload, "portfolio_snapshots", "market_value"),
            total_value=_required_decimal(payload, "portfolio_snapshots", "total_value"),
            open_positions=_required_int(payload, "portfolio_snapshots", "open_positions"),
        )

    def _review_report(self, row: PayloadRecord) -> DashboardReviewReport:
        payload = _payload(row, "review_reports")
        trade_date = _required_date(payload, "review_reports", "trade_date")
        return DashboardReviewReport(
            run_id=_row_run_id(row, "review_reports"),
            trade_date=trade_date.isoformat(),
            summary=_required_str(payload, "review_reports", "summary"),
            stats=_float_mapping(
                _required_mapping(payload, "review_reports", "stats"),
                "review_reports",
                "stats",
            ),
            attribution=_required_str_list(payload, "review_reports", "attribution"),
            parameter_suggestions=_required_str_list(
                payload,
                "review_reports",
                "parameter_suggestions",
            ),
            metrics=self._review_metrics(trade_date),
        )

    def _review_metrics(self, trade_date: date) -> DashboardReviewMetrics:
        metrics = self.review_metrics_agent.metrics_as_of(trade_date)
        return DashboardReviewMetrics(
            realized_pnl=_decimal_text(metrics.realized_pnl.quantize(Decimal("0.01"))),
            win_rate=metrics.win_rate,
            average_holding_days=metrics.average_holding_days,
            sell_reason_distribution=metrics.sell_reason_distribution,
            max_drawdown=metrics.max_drawdown,
        )

    def _source_snapshot(
        self,
        row: PayloadRecord,
        run_stage_by_id: Mapping[str, str],
    ) -> DashboardSourceSnapshot:
        payload = _payload(row, "raw_source_snapshots")
        run_id = _row_run_id(row, "raw_source_snapshots")
        status = _required_str(payload, "raw_source_snapshots", "status")
        if status not in {"success", "failed"}:
            raise ValueError(f"raw_source_snapshots 字段 status 未知: {status}")
        return DashboardSourceSnapshot(
            run_id=run_id,
            stage=run_stage_by_id.get(run_id),
            source=_required_str(payload, "raw_source_snapshots", "source"),
            trade_date=_required_date(payload, "raw_source_snapshots", "trade_date").isoformat(),
            status=status,
            failure_reason=_optional_str(payload.get("failure_reason")),
            row_count=_required_int(payload, "raw_source_snapshots", "row_count"),
            metadata=dict(_required_mapping(payload, "raw_source_snapshots", "metadata")),
            collected_at=_optional_str(payload.get("collected_at")),
        )

    def _intraday_source_health_items(
        self,
        row: PayloadRecord,
        run_stage_by_id: Mapping[str, str],
    ) -> list[DashboardIntradaySourceHealth]:
        payload = _payload(row, "raw_source_snapshots")
        if payload.get("source") != "intraday_bars":
            return []
        metadata = _required_mapping(payload, "raw_source_snapshots", "metadata")
        raw_attempts = metadata.get("source_attempts", [])
        if raw_attempts is None:
            return []
        if not isinstance(raw_attempts, list):
            raise ValueError("raw_source_snapshots.metadata.source_attempts 必须是 list")
        run_id = _row_run_id(row, "raw_source_snapshots")
        items: list[DashboardIntradaySourceHealth] = []
        for raw_attempt in cast(list[object], raw_attempts):
            if not isinstance(raw_attempt, Mapping):
                raise ValueError("raw_source_snapshots.metadata.source_attempts item 必须是 object")
            attempt = cast(Mapping[str, object], raw_attempt)
            status = _required_str(attempt, "source_attempts", "status")
            if status not in {"success", "failed", "empty"}:
                raise ValueError(f"source_attempts 字段 status 未知: {status}")
            items.append(
                DashboardIntradaySourceHealth(
                    run_id=run_id,
                    stage=run_stage_by_id.get(run_id),
                    source=_required_str(attempt, "source_attempts", "source"),
                    symbol=_required_str(attempt, "source_attempts", "symbol"),
                    status=status,
                    returned_rows=_required_int(attempt, "source_attempts", "returned_rows"),
                    retry_attempts=_optional_int(
                        attempt.get("retry_attempts"),
                        "source_attempts",
                        "retry_attempts",
                    ),
                    timeout_seconds=_optional_float(
                        attempt.get("timeout_seconds"),
                        "source_attempts",
                        "timeout_seconds",
                    ),
                    last_error=_optional_str(attempt.get("last_error")),
                )
            )
        return items

    def _data_quality_report(self, row: PayloadRecord) -> DashboardDataQualityReport:
        payload = _payload(row, "data_quality_reports")
        status = _required_str(payload, "data_quality_reports", "status")
        if status not in {"passed", "warning", "failed"}:
            raise ValueError(f"data_quality_reports 字段 status 未知: {status}")
        return DashboardDataQualityReport(
            run_id=_row_run_id(row, "data_quality_reports"),
            stage=_required_str(payload, "data_quality_reports", "stage"),
            trade_date=_required_date(payload, "data_quality_reports", "trade_date").isoformat(),
            status=status,
            source_failure_rate=_required_float(
                payload,
                "data_quality_reports",
                "source_failure_rate",
            ),
            total_sources=_required_int(payload, "data_quality_reports", "total_sources"),
            failed_source_count=_required_int(
                payload,
                "data_quality_reports",
                "failed_source_count",
            ),
            empty_source_count=_required_int(
                payload,
                "data_quality_reports",
                "empty_source_count",
            ),
            missing_market_bar_count=_required_int(
                payload,
                "data_quality_reports",
                "missing_market_bar_count",
            ),
            abnormal_price_count=_required_int(
                payload,
                "data_quality_reports",
                "abnormal_price_count",
            ),
            is_trade_date=_optional_bool(payload.get("is_trade_date"), "data_quality_reports"),
            issues=_data_quality_issues(
                _required_list(payload, "data_quality_reports", "issues")
            ),
            created_at=_optional_str(payload.get("created_at")),
        )

    def _data_reliability_report(self, row: PayloadRecord) -> DashboardDataReliabilityReport:
        payload = _payload(row, "data_reliability_reports")
        status = _required_str(payload, "data_reliability_reports", "status")
        if status not in {"passed", "warning", "failed", "skipped"}:
            raise ValueError(f"data_reliability_reports 字段 status 未知: {status}")
        return DashboardDataReliabilityReport(
            run_id=_row_run_id(row, "data_reliability_reports"),
            trade_date=_required_date(
                payload,
                "data_reliability_reports",
                "trade_date",
            ).isoformat(),
            status=status,
            is_trade_date=_optional_bool(payload.get("is_trade_date"), "data_reliability_reports"),
            lookback_trade_days=_required_int(
                payload,
                "data_reliability_reports",
                "lookback_trade_days",
            ),
            total_sources=_required_int(payload, "data_reliability_reports", "total_sources"),
            failed_source_count=_required_int(
                payload,
                "data_reliability_reports",
                "failed_source_count",
            ),
            empty_source_count=_required_int(
                payload,
                "data_reliability_reports",
                "empty_source_count",
            ),
            source_failure_rate=_required_float(
                payload,
                "data_reliability_reports",
                "source_failure_rate",
            ),
            missing_market_bar_count=_required_int(
                payload,
                "data_reliability_reports",
                "missing_market_bar_count",
            ),
            source_health=_data_source_health(
                _required_list(payload, "data_reliability_reports", "source_health")
            ),
            market_bar_gaps=_market_bar_gaps(
                _required_list(payload, "data_reliability_reports", "market_bar_gaps")
            ),
            issues=_data_reliability_issues(
                _required_list(payload, "data_reliability_reports", "issues")
            ),
            created_at=_optional_str(payload.get("created_at")),
        )


def _payload(row: PayloadRecord, table_name: str) -> Mapping[str, object]:
    raw = row.get("payload")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{table_name} payload 必须是 JSON object")
    return cast(Mapping[str, object], raw)


def _stage_group_status(
    *,
    total_count: int,
    success_count: int,
    failed_count: int,
    skipped_count: int,
    warning_count: int,
) -> str:
    if success_count > 0 and failed_count > 0:
        return "partial_failure"
    if failed_count > 0:
        return "failed"
    if skipped_count == total_count:
        return "skipped"
    if warning_count > 0:
        return "warning"
    return "success"


def _is_normal_row(row: PayloadRecord, table_name: str) -> bool:
    payload = _payload(row, table_name)
    backtest_id = payload.get("backtest_id")
    return payload.get("run_mode", "normal") == "normal" and (
        backtest_id is None or str(backtest_id) == ""
    )


def _row_id(row: PayloadRecord, table_name: str) -> int:
    return _int_value(row.get("id"), table_name, "id")


def _row_run_id(row: PayloadRecord, table_name: str) -> str:
    value = row.get("run_id")
    if value is None:
        raise ValueError(f"{table_name} 缺少字段 run_id")
    return str(value)


def _row_date(row: PayloadRecord, table_name: str) -> date:
    value = row.get("trade_date")
    if value is None:
        raise ValueError(f"{table_name} 缺少字段 trade_date")
    return _date_value(value, table_name, "trade_date")


def _required(payload: Mapping[str, object], table_name: str, field_name: str) -> object:
    if field_name not in payload or payload[field_name] is None:
        raise ValueError(f"{table_name} 缺少字段 {field_name}")
    return payload[field_name]


def _required_str(payload: Mapping[str, object], table_name: str, field_name: str) -> str:
    return str(_required(payload, table_name, field_name))


def _required_json_str(payload: Mapping[str, object], table_name: str, field_name: str) -> str:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, str):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 string")
    return value


def _required_bool(payload: Mapping[str, object], table_name: str, field_name: str) -> bool:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 bool")
    return value


def _required_int(payload: Mapping[str, object], table_name: str, field_name: str) -> int:
    return _int_value(_required(payload, table_name, field_name), table_name, field_name)


def _required_float(payload: Mapping[str, object], table_name: str, field_name: str) -> float:
    return float(_required_decimal_value(payload, table_name, field_name))


def _required_decimal(
    payload: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> str:
    return _decimal_text(_required_decimal_value(payload, table_name, field_name))


def _required_decimal_value(
    payload: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> Decimal:
    return _decimal_value(_required(payload, table_name, field_name), table_name, field_name)


def _required_date(payload: Mapping[str, object], table_name: str, field_name: str) -> date:
    return _date_value(_required(payload, table_name, field_name), table_name, field_name)


def _required_str_list(
    payload: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> list[str]:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, list):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 list")
    values = cast(list[object], value)
    return [str(item) for item in values]


def _required_json_str_list(
    payload: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> list[str]:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, list):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 list")
    values = cast(list[object], value)
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 string list")
    return cast(list[str], values)


def _required_mapping(
    payload: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> Mapping[str, object]:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 object")
    return cast(Mapping[str, object], value)


def _required_list(
    payload: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> list[object]:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, list):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 list")
    return cast(list[object], value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_bool(value: object, table_name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{table_name} 字段 is_trade_date 必须是 bool 或 null")
    return value


def _optional_date(value: object, table_name: str, field_name: str) -> date | None:
    if value is None:
        return None
    return _date_value(value, table_name, field_name)


def _optional_decimal_value(value: object, table_name: str, field_name: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal_value(value, table_name, field_name)


def _optional_decimal(value: object, table_name: str) -> str | None:
    if value is None:
        return None
    return _decimal_text(_decimal_value(value, table_name, "decimal"))


def _optional_int(value: object, table_name: str, field_name: str) -> int | None:
    if value is None:
        return None
    return _int_value(value, table_name, field_name)


def _optional_float(value: object, table_name: str, field_name: str) -> float | None:
    if value is None:
        return None
    return float(_decimal_value(value, table_name, field_name))


def _date_value(value: object, table_name: str, field_name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{table_name} 字段 {field_name} 不是有效日期") from exc


def _decimal_value(value: object, table_name: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{table_name} 字段 {field_name} 不是有效数字") from exc


def _int_value(value: object, table_name: str, field_name: str) -> int:
    try:
        return int(str(value))
    except ValueError as exc:
        raise ValueError(f"{table_name} 字段 {field_name} 不是有效整数") from exc


def _float_mapping(
    value: Mapping[str, object],
    table_name: str,
    field_name: str,
) -> dict[str, float]:
    return {
        str(key): float(_decimal_value(item, table_name, field_name))
        for key, item in value.items()
    }


def _decimal_text(value: Decimal) -> str:
    return str(value)


def _strategy_insight_status(status: str) -> str:
    if status not in {"pending_review", "accepted", "rejected"}:
        raise ValueError(f"pipeline_runs 字段 manual_status 未知: {status}")
    return status


def _strategy_insight_hypotheses(
    values: list[object],
) -> list[DashboardStrategyInsightHypothesis]:
    hypotheses: list[DashboardStrategyInsightHypothesis] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("pipeline_runs hypotheses item 必须是 object")
        payload = cast(Mapping[str, object], value)
        hypotheses.append(
            DashboardStrategyInsightHypothesis(
                area=_required_str(payload, "pipeline_runs.hypotheses", "area"),
                direction=_required_str(payload, "pipeline_runs.hypotheses", "direction"),
                reason=_required_str(payload, "pipeline_runs.hypotheses", "reason"),
                risk=_required_str(payload, "pipeline_runs.hypotheses", "risk"),
            )
        )
    return hypotheses


def _strategy_insight_experiments(
    values: list[object],
) -> list[DashboardStrategyInsightExperiment]:
    experiments: list[DashboardStrategyInsightExperiment] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("pipeline_runs experiments item 必须是 object")
        payload = cast(Mapping[str, object], value)
        status = _required_str(payload, "pipeline_runs.experiments", "policy_status")
        if status not in {"approved", "rejected_by_policy"}:
            raise ValueError(f"pipeline_runs experiments policy_status 未知: {status}")
        overrides = _required_mapping(payload, "pipeline_runs.experiments", "overrides")
        experiments.append(
            DashboardStrategyInsightExperiment(
                name=_required_str(payload, "pipeline_runs.experiments", "name"),
                param=_required_str(payload, "pipeline_runs.experiments", "param"),
                candidate_value=_required_str(
                    payload,
                    "pipeline_runs.experiments",
                    "candidate_value",
                ),
                policy_status=status,
                policy_reason=_optional_str(payload.get("policy_reason")),
                variant_id=_optional_str(payload.get("variant_id")),
                overrides=dict(overrides),
            )
        )
    return experiments


def _strategy_insight_windows(
    values: list[object],
) -> list[DashboardStrategyInsightWindow]:
    windows: list[DashboardStrategyInsightWindow] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("pipeline_runs evaluation_windows item 必须是 object")
        payload = cast(Mapping[str, object], value)
        failed_reasons_raw = _required_mapping(
            payload,
            "pipeline_runs.evaluation_windows",
            "failed_variant_reasons",
        )
        failed_reasons: dict[str, list[str]] = {}
        for key, reason_values in failed_reasons_raw.items():
            if not isinstance(reason_values, list):
                raise ValueError(
                    "pipeline_runs.evaluation_windows.failed_variant_reasons "
                    "必须是 string list mapping"
                )
            failed_reasons[str(key)] = _required_string_values(
                cast(list[object], reason_values),
                "pipeline_runs.evaluation_windows.failed_variant_reasons",
            )
        windows.append(
            DashboardStrategyInsightWindow(
                window_trade_days=_required_int(
                    payload,
                    "pipeline_runs.evaluation_windows",
                    "window_trade_days",
                ),
                evaluation_id=_required_str(
                    payload,
                    "pipeline_runs.evaluation_windows",
                    "evaluation_id",
                ),
                report_path=_required_str(
                    payload,
                    "pipeline_runs.evaluation_windows",
                    "report_path",
                ),
                recommended_variant_ids=_required_str_list(
                    payload,
                    "pipeline_runs.evaluation_windows",
                    "recommended_variant_ids",
                ),
                passed_variant_ids=_required_str_list(
                    payload,
                    "pipeline_runs.evaluation_windows",
                    "passed_variant_ids",
                ),
                failed_variant_reasons=failed_reasons,
            )
        )
    return windows


def _required_string_values(values: list[object], table_name: str) -> list[str]:
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"{table_name} 必须是 string list")
    return cast(list[str], values)


def _strategy_evaluation_variants(
    values: list[object],
    evaluation_payload: Mapping[str, object],
) -> list[DashboardStrategyEvaluationVariant]:
    if not values:
        raise ValueError("pipeline_runs 字段 variants 不能为空")
    recommendation_payload = _required_mapping(
        evaluation_payload,
        "pipeline_runs",
        "recommendation",
    )
    recommended_ids = set(
        _required_str_list(
            recommendation_payload,
            "pipeline_runs.recommendation",
            "recommended_variant_ids",
        )
    )
    variants: list[DashboardStrategyEvaluationVariant] = []
    baseline: DashboardStrategyEvaluationVariant | None = None
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("pipeline_runs variants item 必须是 object")
        variant = _strategy_evaluation_variant(
            cast(Mapping[str, object], value),
            recommended_ids,
            baseline,
        )
        if baseline is None:
            baseline = variant
        variants.append(variant)
    return variants


def _strategy_evaluation_variant(
    payload: Mapping[str, object],
    recommended_ids: set[str],
    baseline: DashboardStrategyEvaluationVariant | None,
) -> DashboardStrategyEvaluationVariant:
    variant_id = _required_str(payload, "pipeline_runs.variants", "id")
    failed_days = _required_int(payload, "pipeline_runs.variants", "failed_days")
    source_failure_rate = _required_float(
        payload,
        "pipeline_runs.variants",
        "source_failure_rate",
    )
    signal_hit_rate = _required_float(payload, "pipeline_runs.variants", "signal_hit_rate")
    total_return = _required_float(payload, "pipeline_runs.variants", "total_return")
    max_drawdown = _required_float(payload, "pipeline_runs.variants", "max_drawdown")
    not_recommended_reasons = _strategy_evaluation_reasons(
        baseline=baseline,
        failed_days=failed_days,
        source_failure_rate=source_failure_rate,
        signal_hit_rate=signal_hit_rate,
        total_return=total_return,
        max_drawdown=max_drawdown,
    )
    return DashboardStrategyEvaluationVariant(
        id=variant_id,
        label=_required_str(payload, "pipeline_runs.variants", "label"),
        version=_required_str(payload, "pipeline_runs.variants", "version"),
        backtest_id=_required_str(payload, "pipeline_runs.variants", "backtest_id"),
        success=_required_bool(payload, "pipeline_runs.variants", "success"),
        attempted_days=_required_int(payload, "pipeline_runs.variants", "attempted_days"),
        succeeded_days=_required_int(payload, "pipeline_runs.variants", "succeeded_days"),
        failed_days=failed_days,
        source_failure_rate=source_failure_rate,
        data_quality_failure_rate=_required_float(
            payload,
            "pipeline_runs.variants",
            "data_quality_failure_rate",
        ),
        signal_count=_required_int(payload, "pipeline_runs.variants", "signal_count"),
        risk_approved_count=_required_int(
            payload,
            "pipeline_runs.variants",
            "risk_approved_count",
        ),
        risk_rejected_count=_required_int(
            payload,
            "pipeline_runs.variants",
            "risk_rejected_count",
        ),
        order_count=_required_int(payload, "pipeline_runs.variants", "order_count"),
        execution_failed_count=_required_int(
            payload,
            "pipeline_runs.variants",
            "execution_failed_count",
        ),
        closed_trade_count=_required_int(
            payload,
            "pipeline_runs.variants",
            "closed_trade_count",
        ),
        signal_hit_count=_required_int(payload, "pipeline_runs.variants", "signal_hit_count"),
        signal_hit_rate=signal_hit_rate,
        open_position_count=_required_int(
            payload,
            "pipeline_runs.variants",
            "open_position_count",
        ),
        holding_pnl=_required_str(payload, "pipeline_runs.variants", "holding_pnl"),
        total_return=total_return,
        max_drawdown=max_drawdown,
        is_recommended=variant_id in recommended_ids and not not_recommended_reasons,
        not_recommended_reasons=not_recommended_reasons,
    )


def _strategy_evaluation_reasons(
    *,
    baseline: DashboardStrategyEvaluationVariant | None,
    failed_days: int,
    source_failure_rate: float,
    signal_hit_rate: float,
    total_return: float,
    max_drawdown: float,
) -> list[str]:
    if baseline is None:
        return ["基准参数，不参与推荐比较"]
    reasons: list[str] = []
    if total_return <= baseline.total_return:
        reasons.append("收益未优于基准")
    if signal_hit_rate < baseline.signal_hit_rate:
        reasons.append("命中率低于基准")
    if max_drawdown > baseline.max_drawdown:
        reasons.append("最大回撤高于基准")
    if failed_days > baseline.failed_days:
        reasons.append("失败天数多于基准")
    if source_failure_rate > baseline.source_failure_rate:
        reasons.append("source 失败率高于基准")
    return reasons


def _data_quality_issues(values: list[object]) -> list[DashboardDataQualityIssue]:
    issues: list[DashboardDataQualityIssue] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("data_quality_reports 字段 issues 必须是 object list")
        payload = cast(Mapping[str, object], value)
        severity = _required_str(payload, "data_quality_reports.issues", "severity")
        if severity not in {"warning", "error"}:
            raise ValueError(f"data_quality_reports.issues 字段 severity 未知: {severity}")
        issues.append(
            DashboardDataQualityIssue(
                severity=severity,
                check_name=_required_str(payload, "data_quality_reports.issues", "check_name"),
                source=_optional_str(payload.get("source")),
                symbol=_optional_str(payload.get("symbol")),
                message=_required_str(payload, "data_quality_reports.issues", "message"),
                metadata=dict(
                    _required_mapping(payload, "data_quality_reports.issues", "metadata")
                ),
            )
        )
    return issues


def _data_reliability_issues(values: list[object]) -> list[DashboardDataReliabilityIssue]:
    issues: list[DashboardDataReliabilityIssue] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("data_reliability_reports 字段 issues 必须是 object list")
        payload = cast(Mapping[str, object], value)
        severity = _required_str(payload, "data_reliability_reports.issues", "severity")
        if severity not in {"warning", "error"}:
            raise ValueError(f"data_reliability_reports.issues 字段 severity 未知: {severity}")
        issues.append(
            DashboardDataReliabilityIssue(
                severity=severity,
                check_name=_required_str(
                    payload,
                    "data_reliability_reports.issues",
                    "check_name",
                ),
                source=_optional_str(payload.get("source")),
                symbol=_optional_str(payload.get("symbol")),
                message=_required_str(payload, "data_reliability_reports.issues", "message"),
                metadata=dict(
                    _required_mapping(
                        payload,
                        "data_reliability_reports.issues",
                        "metadata",
                    )
                ),
            )
        )
    return issues


def _data_source_health(values: list[object]) -> list[DashboardDataSourceHealth]:
    rows: list[DashboardDataSourceHealth] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("data_reliability_reports 字段 source_health 必须是 object list")
        payload = cast(Mapping[str, object], value)
        status = _required_str(payload, "data_reliability_reports.source_health", "status")
        if status not in {"success", "failed", "empty", "mixed"}:
            raise ValueError(f"data_reliability_reports.source_health 字段 status 未知: {status}")
        rows.append(
            DashboardDataSourceHealth(
                source=_required_str(payload, "data_reliability_reports.source_health", "source"),
                status=status,
                total_snapshots=_required_int(
                    payload,
                    "data_reliability_reports.source_health",
                    "total_snapshots",
                ),
                failed_snapshots=_required_int(
                    payload,
                    "data_reliability_reports.source_health",
                    "failed_snapshots",
                ),
                empty_snapshots=_required_int(
                    payload,
                    "data_reliability_reports.source_health",
                    "empty_snapshots",
                ),
                row_count=_required_int(
                    payload,
                    "data_reliability_reports.source_health",
                    "row_count",
                ),
                failure_rate=_required_float(
                    payload,
                    "data_reliability_reports.source_health",
                    "failure_rate",
                ),
                last_failure_reason=_optional_str(payload.get("last_failure_reason")),
                required=_required_bool(
                    payload,
                    "data_reliability_reports.source_health",
                    "required",
                ),
            )
        )
    return rows


def _market_bar_gaps(values: list[object]) -> list[DashboardMarketBarGap]:
    gaps: list[DashboardMarketBarGap] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("data_reliability_reports 字段 market_bar_gaps 必须是 object list")
        payload = cast(Mapping[str, object], value)
        gaps.append(
            DashboardMarketBarGap(
                symbol=_required_str(payload, "data_reliability_reports.market_bar_gaps", "symbol"),
                missing_dates=_required_str_list(
                    payload,
                    "data_reliability_reports.market_bar_gaps",
                    "missing_dates",
                ),
                missing_count=_required_int(
                    payload,
                    "data_reliability_reports.market_bar_gaps",
                    "missing_count",
                ),
            )
        )
    return gaps

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from ashare_agent.agents.review_metrics_agent import ReviewMetricsAgent
from ashare_agent.repository import PayloadRecord


class DashboardQueryRepository(Protocol):
    def payload_rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]: ...


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
    created_at: str | None


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


def _empty_positions() -> list[DashboardPosition]:
    return []


def _empty_source_snapshots() -> list[DashboardSourceSnapshot]:
    return []


def _empty_data_quality_reports() -> list[DashboardDataQualityReport]:
    return []


@dataclass(frozen=True)
class DashboardDaySummary:
    trade_date: str
    runs: list[DashboardPipelineRun] = field(default_factory=_empty_runs)
    watchlist: list[DashboardWatchlistItem] = field(default_factory=_empty_watchlist)
    signals: list[DashboardSignalItem] = field(default_factory=_empty_signals)
    risk_decisions: list[DashboardRiskDecision] = field(default_factory=_empty_risk_decisions)
    paper_orders: list[DashboardPaperOrder] = field(default_factory=_empty_paper_orders)
    positions: list[DashboardPosition] = field(default_factory=_empty_positions)
    portfolio_snapshot: DashboardPortfolioSnapshot | None = None
    review_report: DashboardReviewReport | None = None
    source_snapshots: list[DashboardSourceSnapshot] = field(
        default_factory=_empty_source_snapshots
    )
    data_quality_reports: list[DashboardDataQualityReport] = field(
        default_factory=_empty_data_quality_reports
    )


class DashboardQueryAgent:
    def __init__(self, repository: DashboardQueryRepository) -> None:
        self.repository = repository
        self.review_metrics_agent = ReviewMetricsAgent(repository)

    def list_pipeline_runs(self, limit: int = 50) -> list[DashboardPipelineRun]:
        rows = sorted(
            self.repository.payload_rows("pipeline_runs"),
            key=lambda row: _row_id(row, "pipeline_runs"),
            reverse=True,
        )
        return [self._pipeline_run(row) for row in rows[:limit]]

    def day_summary(self, trade_date: date) -> DashboardDaySummary:
        runs = self._pipeline_runs_for_day(trade_date)
        run_stage_by_id = {run.run_id: run.stage for run in runs}
        pre_market_run_id = self._latest_successful_run_id(trade_date, "pre_market")

        return DashboardDaySummary(
            trade_date=trade_date.isoformat(),
            runs=runs,
            watchlist=self.watchlist(trade_date, pre_market_run_id),
            signals=self.signals(trade_date, pre_market_run_id),
            risk_decisions=self.risk_decisions(trade_date, pre_market_run_id),
            paper_orders=self.paper_orders(trade_date),
            positions=self.positions_as_of(trade_date),
            portfolio_snapshot=self.latest_portfolio_snapshot(trade_date),
            review_report=self.latest_review_report(trade_date),
            source_snapshots=self.source_snapshots(trade_date, run_stage_by_id),
            data_quality_reports=self.data_quality_reports(trade_date),
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
        return [
            self._paper_order(row)
            for row in self.repository.payload_rows("paper_orders", trade_date=trade_date)
        ]

    def positions_as_of(self, trade_date: date) -> list[DashboardPosition]:
        latest_by_symbol: dict[str, PayloadRecord] = {}
        for row in self.repository.payload_rows("paper_positions"):
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
            if _row_date(row, "portfolio_snapshots") <= trade_date
        ]
        if not rows:
            return None
        return self._portfolio_snapshot(rows[-1])

    def latest_review_report(self, trade_date: date) -> DashboardReviewReport | None:
        rows = self.repository.payload_rows("review_reports", trade_date=trade_date)
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
        ]

    def data_quality_reports(self, trade_date: date) -> list[DashboardDataQualityReport]:
        return [
            self._data_quality_report(row)
            for row in self.repository.payload_rows("data_quality_reports", trade_date=trade_date)
        ]

    def _pipeline_runs_for_day(self, trade_date: date) -> list[DashboardPipelineRun]:
        rows = sorted(
            self.repository.payload_rows("pipeline_runs", trade_date=trade_date),
            key=lambda row: _row_id(row, "pipeline_runs"),
            reverse=True,
        )
        return [self._pipeline_run(row) for row in rows]

    def _latest_successful_run_id(self, trade_date: date, stage: str) -> str | None:
        rows = self.repository.payload_rows("pipeline_runs", trade_date=trade_date)
        for row in reversed(rows):
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
        ):
            for row in self.repository.payload_rows(table_name):
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
            created_at=_optional_str(payload.get("created_at")),
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


def _payload(row: PayloadRecord, table_name: str) -> Mapping[str, object]:
    raw = row.get("payload")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{table_name} payload 必须是 JSON object")
    return cast(Mapping[str, object], raw)


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

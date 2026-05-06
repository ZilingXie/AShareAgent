from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from ashare_agent.agents.announcement_analyzer import AnnouncementAnalyzer
from ashare_agent.agents.data_collector import DataCollector
from ashare_agent.agents.data_quality_agent import DataQualityAgent
from ashare_agent.agents.data_reliability_agent import DataReliabilityAgent
from ashare_agent.agents.market_regime_analyzer import MarketRegimeAnalyzer
from ashare_agent.agents.paper_trader import PaperTrader
from ashare_agent.agents.review_agent import ReviewAgent
from ashare_agent.agents.review_metrics_agent import ReviewMetricsAgent
from ashare_agent.agents.risk_manager import RiskManager
from ashare_agent.agents.signal_engine import SignalEngine
from ashare_agent.agents.strategy_params_agent import StrategyParams, StrategyParamsAgent
from ashare_agent.domain import (
    AgentResult,
    ExecutionEvent,
    IntradayBar,
    MarketDataset,
    PaperOrder,
    PipelineRunContext,
    PortfolioSnapshot,
    ReviewReport,
    RiskDecision,
    RunMode,
    SignalResult,
)
from ashare_agent.indicators import calculate_indicators
from ashare_agent.llm.base import LLMClient
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.base import DataProvider, DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.reports import MarkdownTable, write_markdown_report
from ashare_agent.repository import InMemoryRepository, PipelineRepository


def _to_dict_list(values: list[Any]) -> list[dict[str, Any]]:
    return [asdict(value) for value in values]


class ASharePipeline:
    def __init__(
        self,
        provider: DataProvider,
        llm_client: LLMClient,
        report_root: Path,
        repository: PipelineRepository | None = None,
        trader: PaperTrader | None = None,
        strategy_params: StrategyParams | None = None,
        required_data_sources: set[str] | None = None,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> None:
        self.strategy_params = strategy_params or StrategyParamsAgent(
            Path("configs/strategy_params.yml")
        ).load()
        self.repository = repository or InMemoryRepository()
        self.required_data_sources = required_data_sources or set()
        self.run_mode: RunMode = run_mode
        self.backtest_id: str | None = backtest_id
        self.collector = DataCollector(provider)
        self.data_quality_agent = DataQualityAgent(
            required_data_sources=self.required_data_sources
        )
        self.data_reliability_agent = DataReliabilityAgent(
            self.repository,
            required_data_sources=self.required_data_sources,
        )
        self.announcement_analyzer = AnnouncementAnalyzer()
        self.market_regime_analyzer = MarketRegimeAnalyzer()
        self.signal_engine = SignalEngine(
            params=self.strategy_params.signal,
            strategy_params_version=self.strategy_params.version,
            strategy_params_snapshot=self.strategy_params.snapshot(),
        )
        self.risk_manager = RiskManager(
            max_positions=self.strategy_params.risk.max_positions,
            target_position_pct=self.strategy_params.risk.target_position_pct,
            blacklist=self.strategy_params.risk.blacklist,
            min_cash=self.strategy_params.risk.min_cash,
            max_daily_loss_pct=self.strategy_params.risk.max_daily_loss_pct,
            stop_loss_pct=self.strategy_params.risk.stop_loss_pct,
            price_limit_pct=self.strategy_params.risk.price_limit_pct,
            min_holding_trade_days=self.strategy_params.risk.min_holding_trade_days,
            max_holding_trade_days=self.strategy_params.risk.max_holding_trade_days,
        )
        self.trader = trader or PaperTrader(
            initial_cash=self.strategy_params.paper_trader.initial_cash,
            position_size_pct=self.strategy_params.paper_trader.position_size_pct,
            slippage_pct=self.strategy_params.paper_trader.slippage_pct,
            price_limit_pct=self.strategy_params.risk.price_limit_pct,
        )
        self.review_agent = ReviewAgent()
        self.llm_client = llm_client
        self.report_root = report_root
        self._last_dataset: MarketDataset | None = None
        self._last_signal_result: SignalResult | None = None
        self._last_risk_decisions: list[RiskDecision] = []

    def _strategy_params_payload(self) -> dict[str, Any]:
        return {
            "strategy_params_version": self.strategy_params.version,
            "strategy_params_snapshot": self.strategy_params.snapshot(),
        }

    def strategy_params_payload(self) -> dict[str, Any]:
        return self._strategy_params_payload()

    def _run_scope_payload(self) -> dict[str, Any]:
        return {
            "run_mode": self.run_mode,
            "backtest_id": self.backtest_id,
        }

    def run_scope_payload(self) -> dict[str, Any]:
        return self._run_scope_payload()

    def _context(self, trade_date: date) -> PipelineRunContext:
        return PipelineRunContext(
            trade_date=trade_date,
            run_mode=self.run_mode,
            backtest_id=self.backtest_id,
        )

    def new_context(self, trade_date: date) -> PipelineRunContext:
        return self._context(trade_date)

    def _restore_trader_state(self) -> None:
        if not self.trader.positions:
            self.trader.positions = self.repository.load_open_positions(
                run_mode=self.run_mode,
                backtest_id=self.backtest_id,
            )
        self.trader.cash = self.repository.load_latest_cash(
            default_cash=self.trader.cash,
            run_mode=self.run_mode,
            backtest_id=self.backtest_id,
        )

    def _current_total_value(self) -> Decimal:
        return self.trader.cash + sum(
            (position.market_value for position in self.trader.open_positions()),
            start=Decimal("0"),
        )

    def _latest_successful_run_id(self, trade_date: date, stage: str) -> str | None:
        rows = self.repository.payload_rows("pipeline_runs", trade_date=trade_date)
        for row in reversed(rows):
            payload = row.get("payload")
            if not isinstance(payload, Mapping):
                raise ValueError("pipeline_runs payload 必须是 JSON object")
            payload_map = cast(Mapping[str, object], payload)
            row_run_mode = payload_map.get("run_mode", "normal")
            row_backtest_id = payload_map.get("backtest_id")
            if row_run_mode != self.run_mode:
                continue
            if self.run_mode == "backtest" and row_backtest_id != self.backtest_id:
                continue
            if self.run_mode == "normal" and row_backtest_id is not None:
                continue
            if payload_map.get("stage") == stage and payload_map.get("status") == "success":
                run_id = row.get("run_id")
                if run_id is None:
                    raise ValueError("pipeline_runs 缺少字段 run_id")
                return str(run_id)
        return None

    def _latest_llm_analysis_payload(self, trade_date: date) -> Mapping[str, object] | None:
        run_id = self._latest_successful_run_id(trade_date, "pre_market")
        if run_id is None:
            return None
        rows = self.repository.payload_rows(
            "llm_analyses",
            trade_date=trade_date,
            run_id=run_id,
        )
        if not rows:
            return None
        payload = rows[-1].get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("llm_analyses payload 必须是 JSON object")
        return cast(Mapping[str, object], payload)

    def _write_strategy_experiment_report(
        self,
        *,
        context: PipelineRunContext,
        decisions: list[RiskDecision],
        orders: list[PaperOrder],
        snapshot: PortfolioSnapshot,
        report: ReviewReport,
    ) -> Path:
        llm_payload = self._latest_llm_analysis_payload(context.trade_date)
        rejected_reasons: Counter[str] = Counter()
        for decision in decisions:
            if not decision.approved:
                rejected_reasons.update(decision.reasons)
        sell_reasons = Counter(order.reason for order in orders if order.side == "sell")
        metrics = ReviewMetricsAgent(self.repository).metrics_as_of(context.trade_date)

        llm_lines = ["无已落库 LLM 盘前分析"]
        if llm_payload is not None:
            model = llm_payload.get("model")
            summary = llm_payload.get("summary")
            key_points = llm_payload.get("key_points", [])
            risk_notes = llm_payload.get("risk_notes", [])
            if not isinstance(model, str) or not isinstance(summary, str):
                raise ValueError("llm_analyses model/summary 必须是 string")
            if not isinstance(key_points, list) or not isinstance(risk_notes, list):
                raise ValueError("llm_analyses key_points/risk_notes 必须是 list")
            key_point_values = cast(list[object], key_points)
            risk_note_values = cast(list[object], risk_notes)
            if not all(isinstance(point, str) for point in key_point_values) or not all(
                isinstance(note, str) for note in risk_note_values
            ):
                raise ValueError("llm_analyses key_points/risk_notes 必须是 string list")
            llm_lines = [
                f"模型: {model}",
                f"摘要: {summary}",
                *[f"重点: {point}" for point in key_point_values],
                *[f"风险: {note}" for note in risk_note_values],
            ]

        return write_markdown_report(
            self.report_root,
            context.trade_date.isoformat(),
            "strategy-experiment.md",
            {
                "实验信息": [
                    f"trade_date: {context.trade_date.isoformat()}",
                    f"run_id: {context.run_id}",
                    f"strategy_params_version: {self.strategy_params.version}",
                ],
                "LLM 盘前分析": llm_lines,
                "风控拒绝原因": [
                    f"{reason}: {count}" for reason, count in sorted(rejected_reasons.items())
                ],
                "模拟订单": MarkdownTable(
                    headers=[
                        "side",
                        "symbol",
                        "quantity",
                        "price",
                        "amount",
                        "reason",
                        "real_trade",
                    ],
                    rows=[
                        [
                            order.side,
                            order.symbol,
                            order.quantity,
                            order.price,
                            order.amount,
                            order.reason,
                            order.is_real_trade,
                        ]
                        for order in orders
                    ],
                ),
                "卖出原因": [
                    f"{reason}: {count}" for reason, count in sorted(sell_reasons.items())
                ],
                "复盘指标": [
                    f"已实现盈亏: {metrics.realized_pnl.quantize(Decimal('0.01'))}",
                    f"胜率: {metrics.win_rate:.2%}",
                    f"平均持仓天数: {metrics.average_holding_days:.2f}",
                    f"最大回撤: {metrics.max_drawdown:.2%}",
                ],
                "复盘摘要": [
                    report.summary,
                    f"total_value: {snapshot.total_value}",
                    f"cash: {snapshot.cash}",
                    f"market_value: {snapshot.market_value}",
                    f"open_positions: {snapshot.open_positions}",
                ],
            },
        )

    def _save_dataset(self, context: PipelineRunContext, dataset: MarketDataset) -> None:
        self.repository.save_universe_assets(context, dataset.assets)
        self.repository.save_raw_source_snapshots(context, dataset.source_snapshots)
        self.repository.save_trading_calendar_days(context, dataset.trade_calendar_days)
        self.repository.save_market_bars(context, dataset.bars)
        self.repository.save_announcements(context, dataset.announcements)
        self.repository.save_news_items(context, dataset.news)
        self.repository.save_policy_items(context, dataset.policy_items)

    def save_dataset(self, context: PipelineRunContext, dataset: MarketDataset) -> None:
        self._save_dataset(context, dataset)

    def _save_reliability_report(self, context: PipelineRunContext) -> None:
        report = self.data_reliability_agent.analyze(context.trade_date)
        self.repository.save_data_reliability_report(context, report)

    def save_reliability_report(self, context: PipelineRunContext) -> None:
        self._save_reliability_report(context)

    def _run_data_quality_gate(
        self,
        context: PipelineRunContext,
        stage: str,
        dataset: MarketDataset,
        failure_payload_extra: Mapping[str, Any] | None = None,
    ) -> None:
        report = self.data_quality_agent.analyze(stage=stage, dataset=dataset)
        self.repository.save_data_quality_report(context, report)
        if report.status != "failed":
            return
        failure_detail = "; ".join(
            issue.message for issue in report.issues if issue.severity == "error"
        )
        payload = {
            "run_id": context.run_id,
            "failure_reason": f"数据质量检查失败: {failure_detail}",
            **(dict(failure_payload_extra) if failure_payload_extra is not None else {}),
            **self._run_scope_payload(),
            **self._strategy_params_payload(),
        }
        self.repository.save_artifact(context.trade_date, f"{stage}_failed", payload)
        self.repository.save_pipeline_run(context, stage, "failed", payload)
        raise DataProviderError(payload["failure_reason"])

    def run_data_quality_gate(
        self,
        context: PipelineRunContext,
        stage: str,
        dataset: MarketDataset,
        failure_payload_extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._run_data_quality_gate(context, stage, dataset, failure_payload_extra)

    def _dataset_for_stage(self, context: PipelineRunContext, stage: str) -> MarketDataset:
        if self._last_dataset is None:
            dataset = self.collector.collect(trade_date=context.trade_date)
            self._save_dataset(context, dataset)
        else:
            dataset = self._last_dataset
        self._run_data_quality_gate(context, stage, dataset)
        return dataset

    def _load_intraday_trade_inputs(
        self,
        context: PipelineRunContext,
    ) -> tuple[list[RiskDecision], list[PaperOrder]]:
        trade_date = context.trade_date
        if self._latest_successful_run_id(trade_date, "pre_market") is not None:
            decisions = self._last_risk_decisions or self.repository.load_latest_risk_decisions(
                trade_date,
                run_mode=self.run_mode,
                backtest_id=self.backtest_id,
            )
            self._restore_trader_state()
            existing_orders = self.repository.load_paper_orders(
                trade_date,
                run_mode=self.run_mode,
                backtest_id=self.backtest_id,
                stage="intraday_watch",
            )
            return decisions, existing_orders

        payload = {
            "run_id": context.run_id,
            "failure_reason": "intraday_watch 缺少同日成功 pre_market 风控决策",
            **self._run_scope_payload(),
            **self._strategy_params_payload(),
        }
        self.repository.save_artifact(trade_date, "intraday_watch_failed", payload)
        self.repository.save_pipeline_run(context, "intraday_watch", "failed", payload)
        raise DataProviderError(payload["failure_reason"])

    def _execute_intraday_paper_trades(
        self,
        *,
        context: PipelineRunContext,
        dataset: MarketDataset,
        decisions: list[RiskDecision],
        existing_orders: list[PaperOrder],
    ) -> tuple[list[PaperOrder], PortfolioSnapshot, list[ExecutionEvent]]:
        trade_date = context.trade_date
        execution_symbols = self._execution_symbols(decisions)
        intraday_bars = self._collect_intraday_bars_for_execution(context, execution_symbols)
        buy_result = self.trader.apply_pre_market_decisions(
            trade_date=trade_date,
            decisions=decisions,
            bars=dataset.bars,
            intraday_bars=intraday_bars,
            existing_orders=existing_orders,
        )
        self.trader.mark_to_market(dataset.bars)
        indicators = calculate_indicators(trade_date=trade_date, bars=dataset.bars)
        exit_decisions = self.risk_manager.evaluate_exits(
            trade_date=trade_date,
            open_positions=self.trader.open_positions(),
            indicators=indicators,
            trade_calendar=dataset.trade_calendar_dates,
        )
        sell_result = self.trader.apply_exit_decisions(
            trade_date=trade_date,
            decisions=exit_decisions,
            bars=dataset.bars,
            intraday_bars=intraday_bars,
            existing_orders=existing_orders + buy_result.orders,
        )
        orders = buy_result.orders + sell_result.orders
        execution_events = buy_result.execution_events + sell_result.execution_events
        snapshot, _ = self.review_agent.review(
            trade_date=trade_date,
            cash=self.trader.cash,
            positions=self.trader.open_positions(),
        )
        self.repository.save_paper_orders(context, orders)
        self.repository.save_paper_positions(context, self.trader.positions)
        self.repository.save_portfolio_snapshot(context, snapshot)
        return orders, snapshot, execution_events

    def _execution_symbols(self, decisions: list[RiskDecision]) -> list[str]:
        symbols = {
            decision.symbol
            for decision in decisions
            if decision.approved and decision.signal_action == "paper_buy"
        }
        symbols.update(position.symbol for position in self.trader.open_positions())
        return sorted(symbols)

    def _collect_intraday_bars_for_execution(
        self,
        context: PipelineRunContext,
        symbols: list[str],
    ) -> list[IntradayBar]:
        if not symbols:
            return []
        collection = self.collector.collect_intraday_bars(context.trade_date, symbols, period="1")
        self.repository.save_raw_source_snapshots(context, [collection.source_snapshot])
        if collection.source_snapshot.status == "failed":
            failure_reason = collection.source_snapshot.failure_reason or "unknown failure"
            payload = {
                "run_id": context.run_id,
                "failure_reason": f"分钟线获取失败: {failure_reason}",
                **self._run_scope_payload(),
                **self._strategy_params_payload(),
            }
            self.repository.save_artifact(context.trade_date, "intraday_watch_failed", payload)
            self.repository.save_pipeline_run(context, "intraday_watch", "failed", payload)
            raise DataProviderError(payload["failure_reason"])
        return collection.bars

    def _write_intraday_report(
        self,
        trade_date: date,
        orders: list[PaperOrder],
        execution_events: list[ExecutionEvent],
    ) -> Path:
        return write_markdown_report(
            self.report_root,
            trade_date.isoformat(),
            "intraday-watch.md",
            {
                "状态": "盘中执行模拟交易，不执行真实交易。",
                "模拟买入": [order.symbol for order in orders if order.side == "buy"],
                "模拟卖出": [order.symbol for order in orders if order.side == "sell"],
                "成交失败": [
                    f"{event.side} {event.symbol}: {event.failure_reason}"
                    for event in execution_events
                    if event.status == "rejected"
                ],
                "安全边界": "本项目 v1 只有 paper trading。",
            },
        )

    def _run_post_market_summary(
        self,
        *,
        context: PipelineRunContext,
        dataset: MarketDataset,
    ) -> tuple[list[PaperOrder], PortfolioSnapshot, ReviewReport, Path, Path]:
        trade_date = context.trade_date
        decisions = self._last_risk_decisions or self.repository.load_latest_risk_decisions(
            trade_date,
            run_mode=self.run_mode,
            backtest_id=self.backtest_id,
        )
        self._restore_trader_state()
        reviewed_orders = self.repository.load_paper_orders(
            trade_date,
            run_mode=self.run_mode,
            backtest_id=self.backtest_id,
            stage="intraday_watch",
        )
        self.trader.mark_to_market(dataset.bars)
        snapshot, report = self.review_agent.review(
            trade_date=trade_date,
            cash=self.trader.cash,
            positions=self.trader.open_positions(),
        )
        report_path = write_markdown_report(
            self.report_root,
            trade_date.isoformat(),
            "post-market-review.md",
            {
                "复盘摘要": report.summary,
                "持仓归因": report.attribution,
                "参数建议": report.parameter_suggestions,
            },
        )
        self.repository.save_paper_positions(context, self.trader.positions)
        self.repository.save_portfolio_snapshot(context, snapshot)
        self.repository.save_review_report(context, report)
        experiment_report_path = self._write_strategy_experiment_report(
            context=context,
            decisions=decisions,
            orders=reviewed_orders,
            snapshot=snapshot,
            report=report,
        )
        return reviewed_orders, snapshot, report, report_path, experiment_report_path

    def run_pre_market(self, trade_date: date) -> AgentResult:
        context = self._context(trade_date)
        dataset = self.collector.collect(trade_date=trade_date)
        self._save_dataset(context, dataset)
        self._run_data_quality_gate(context, "pre_market", dataset)
        events = self.announcement_analyzer.analyze(dataset.announcements)
        regime = self.market_regime_analyzer.analyze(trade_date=trade_date, bars=dataset.bars)
        indicators = calculate_indicators(trade_date=trade_date, bars=dataset.bars)
        self.repository.save_technical_indicators(context, indicators)
        signal_result = self.signal_engine.generate(
            trade_date=trade_date,
            indicators=indicators,
            events=events,
            regime=regime,
        )
        self._restore_trader_state()
        self.trader.mark_to_market(dataset.bars)
        latest_snapshot = self.repository.load_latest_portfolio_snapshot(
            run_mode=self.run_mode,
            backtest_id=self.backtest_id,
        )
        previous_total_value = latest_snapshot.total_value if latest_snapshot is not None else None
        decisions = self.risk_manager.evaluate(
            trade_date=trade_date,
            signals=signal_result.signals,
            open_positions=self.trader.open_positions(),
            cash=self.trader.cash,
            bars=dataset.bars,
            previous_total_value=previous_total_value,
            current_total_value=self._current_total_value(),
        )
        llm_analysis = self.llm_client.analyze_pre_market(
            trade_date=trade_date,
            context={
                "market_regime": regime.status,
                "top_symbols": [candidate.symbol for candidate in signal_result.watchlist[:3]],
            },
        )
        report_path = write_markdown_report(
            self.report_root,
            trade_date.isoformat(),
            "pre-market.md",
            {
                "市场环境": regime.reasons,
                "观察名单": [
                    f"{candidate.symbol}: {candidate.score:.4f}"
                    for candidate in signal_result.watchlist
                ],
                "模拟买入信号": [signal.symbol for signal in signal_result.signals],
                "LLM 分析": llm_analysis.summary,
            },
        )
        payload: dict[str, Any] = {
            "run_id": context.run_id,
            "trade_date": trade_date.isoformat(),
            "market_regime": regime.status,
            "market_reasons": regime.reasons,
            "signals": _to_dict_list(signal_result.signals),
            "watchlist": _to_dict_list(signal_result.watchlist),
            "risk_decisions": _to_dict_list(decisions),
            "report_path": str(report_path),
            **self._run_scope_payload(),
            **self._strategy_params_payload(),
        }
        self.repository.save_watchlist_candidates(context, signal_result.watchlist)
        self.repository.save_signals(context, signal_result.signals)
        self.repository.save_risk_decisions(context, decisions)
        self.repository.save_llm_analysis(context, llm_analysis)
        self.repository.save_artifact(trade_date, "pre_market", payload)
        self.repository.save_pipeline_run(
            context,
            "pre_market",
            "success",
            {
                "report_path": str(report_path),
                "trade_date": trade_date.isoformat(),
                "market_regime": regime.status,
                "market_reasons": regime.reasons,
                "watchlist_count": len(signal_result.watchlist),
                "signal_count": len(signal_result.signals),
                "risk_decision_count": len(decisions),
                **self._strategy_params_payload(),
            },
        )
        self._last_dataset = dataset
        self._last_signal_result = signal_result
        self._last_risk_decisions = decisions
        return AgentResult(name="pre_market", success=True, payload=payload)

    def run_intraday_watch(self, trade_date: date) -> AgentResult:
        context = self._context(trade_date)
        decisions, existing_orders = self._load_intraday_trade_inputs(context)
        dataset = self._dataset_for_stage(context, "intraday_watch")
        orders, snapshot, execution_events = self._execute_intraday_paper_trades(
            context=context,
            dataset=dataset,
            decisions=decisions,
            existing_orders=existing_orders,
        )
        report_path = self._write_intraday_report(trade_date, orders, execution_events)
        payload = {
            "run_id": context.run_id,
            "trade_date": trade_date.isoformat(),
            "orders": _to_dict_list(orders),
            "execution_events": _to_dict_list(execution_events),
            "positions": _to_dict_list(self.trader.positions),
            "portfolio": asdict(snapshot),
            "report_path": str(report_path),
            "real_trading": False,
            "order_count": len(orders),
            "buy_order_count": len([order for order in orders if order.side == "buy"]),
            "sell_order_count": len([order for order in orders if order.side == "sell"]),
            "execution_event_count": len(execution_events),
            "execution_rejected_count": len(
                [event for event in execution_events if event.status == "rejected"]
            ),
            "open_positions": snapshot.open_positions,
            **self._run_scope_payload(),
            **self._strategy_params_payload(),
        }
        self.repository.save_artifact(trade_date, "intraday_watch", payload)
        self.repository.save_pipeline_run(
            context,
            "intraday_watch",
            "success",
            {
                "report_path": str(report_path),
                "trade_date": trade_date.isoformat(),
                "real_trading": False,
                "order_count": len(orders),
                "buy_order_count": len([order for order in orders if order.side == "buy"]),
                "sell_order_count": len([order for order in orders if order.side == "sell"]),
                "execution_events": _to_dict_list(execution_events),
                "execution_event_count": len(execution_events),
                "execution_rejected_count": len(
                    [event for event in execution_events if event.status == "rejected"]
                ),
                "open_positions": snapshot.open_positions,
                **self._strategy_params_payload(),
            },
        )
        return AgentResult(name="intraday_watch", success=True, payload=payload)

    def run_post_market_review(self, trade_date: date) -> AgentResult:
        context = self._context(trade_date)
        dataset = self._dataset_for_stage(context, "post_market_review")
        reviewed_orders, snapshot, report, report_path, experiment_report_path = (
            self._run_post_market_summary(
                context=context,
                dataset=dataset,
            )
        )
        payload: dict[str, Any] = {
            "run_id": context.run_id,
            "trade_date": trade_date.isoformat(),
            "reviewed_orders": _to_dict_list(reviewed_orders),
            "positions": _to_dict_list(self.trader.positions),
            "portfolio": asdict(snapshot),
            "review": asdict(report),
            "report_path": f"paper:{report_path}",
            "experiment_report_path": str(experiment_report_path),
            "new_order_count": 0,
            "reviewed_order_count": len(reviewed_orders),
            **self._run_scope_payload(),
            **self._strategy_params_payload(),
        }
        self.repository.save_artifact(trade_date, "post_market_review", payload)
        self.repository.save_pipeline_run(
            context,
            "post_market_review",
            "success",
            {
                "report_path": str(report_path),
                "trade_date": trade_date.isoformat(),
                "experiment_report_path": str(experiment_report_path),
                "new_order_count": 0,
                "reviewed_order_count": len(reviewed_orders),
                "open_positions": snapshot.open_positions,
                **self._strategy_params_payload(),
            },
        )
        return AgentResult(name="post_market_review", success=True, payload=payload)

    def run_daily(self, trade_date: date) -> AgentResult:
        context = self._context(trade_date)
        calendar = self.collector.collect_trade_calendar(trade_date)
        self.repository.save_raw_source_snapshots(context, [calendar.source_snapshot])
        self.repository.save_trading_calendar_days(context, calendar.days)

        if calendar.source_snapshot.status == "failed" and "trade_calendar" in (
            self.required_data_sources
        ):
            failure_reason = (
                "必需数据源失败: "
                f"trade_calendar: {calendar.source_snapshot.failure_reason or 'unknown failure'}"
            )
            self._save_reliability_report(context)
            payload = {
                "run_id": context.run_id,
                "failure_reason": failure_reason,
                **self._run_scope_payload(),
                **self._strategy_params_payload(),
            }
            self.repository.save_artifact(trade_date, "daily_run_failed", payload)
            self.repository.save_pipeline_run(context, "daily_run", "failed", payload)
            raise DataProviderError(failure_reason)

        if calendar.snapshot is not None and calendar.snapshot.is_trade_date is False:
            self._save_reliability_report(context)
            payload = {
                "run_id": context.run_id,
                "skipped_reason": f"{trade_date.isoformat()} 非交易日，跳过策略阶段",
                **self._run_scope_payload(),
                **self._strategy_params_payload(),
            }
            self.repository.save_artifact(trade_date, "daily_run_skipped", payload)
            self.repository.save_pipeline_run(context, "daily_run", "skipped", payload)
            return AgentResult(name="daily_run", success=True, payload=payload)

        try:
            pre_market = self.run_pre_market(trade_date)
            intraday = self.run_intraday_watch(trade_date)
            review = self.run_post_market_review(trade_date)
        except DataProviderError as exc:
            self._save_reliability_report(context)
            payload = {
                "run_id": context.run_id,
                "failure_reason": str(exc),
                **self._run_scope_payload(),
                **self._strategy_params_payload(),
            }
            self.repository.save_artifact(trade_date, "daily_run_failed", payload)
            self.repository.save_pipeline_run(context, "daily_run", "failed", payload)
            raise

        self._save_reliability_report(context)
        payload = {
            "run_id": context.run_id,
            "stages": [pre_market.name, intraday.name, review.name],
            **self._run_scope_payload(),
            **self._strategy_params_payload(),
        }
        self.repository.save_artifact(trade_date, "daily_run", payload)
        self.repository.save_pipeline_run(context, "daily_run", "success", payload)
        return AgentResult(name="daily_run", success=True, payload=payload)


def build_mock_pipeline(report_root: Path) -> ASharePipeline:
    return ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=report_root,
    )

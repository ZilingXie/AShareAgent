from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

from ashare_agent.domain import AgentResult, PipelineRunContext
from ashare_agent.pipeline import ASharePipeline
from ashare_agent.providers.base import DataProviderError
from ashare_agent.reports import write_markdown_report

ScheduledRunSlot = Literal[
    "morning_collect",
    "pre_market_brief",
    "call_auction",
    "intraday_decision",
    "close_collect",
    "post_market_brief",
]

SCHEDULED_RUN_SLOTS: tuple[ScheduledRunSlot, ...] = (
    "morning_collect",
    "pre_market_brief",
    "call_auction",
    "intraday_decision",
    "close_collect",
    "post_market_brief",
)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class ScheduledRunAgent:
    def __init__(
        self,
        *,
        pipeline: ASharePipeline,
        provider_name: str,
        llm_provider: str,
    ) -> None:
        self.pipeline = pipeline
        self.provider_name = provider_name
        self.llm_provider = llm_provider

    def run(self, *, slot: str, trade_date: date) -> AgentResult:
        resolved_slot = self._validate_slot(slot)
        context = self.pipeline.new_context(trade_date)
        skipped = self._trade_calendar_skip(context, resolved_slot)
        if skipped is not None:
            return skipped
        if resolved_slot == "call_auction":
            return self._save_slot_result(
                context,
                resolved_slot,
                "skipped",
                {
                    "disabled": True,
                    "skipped_reason": "集合竞价采集第一版暂未启用，等待可靠数据源接入",
                },
            )
        if resolved_slot == "morning_collect":
            return self._run_collect_slot(
                context=context,
                slot=resolved_slot,
                report_filename="morning-collect.md",
                report_title="A 股 ETF 早间采集报告",
            )
        if resolved_slot == "close_collect":
            return self._run_collect_slot(
                context=context,
                slot=resolved_slot,
                report_filename="close-collect.md",
                report_title="A 股 ETF 收盘行情采集报告",
            )
        if resolved_slot == "pre_market_brief":
            return self._run_delegated_slot(
                context=context,
                slot=resolved_slot,
                underlying_stage="pre_market",
                runner=self.pipeline.run_pre_market,
                report_writer=self._write_pre_market_brief,
            )
        if resolved_slot == "intraday_decision":
            return self._run_delegated_slot(
                context=context,
                slot=resolved_slot,
                underlying_stage="intraday_watch",
                runner=self.pipeline.run_intraday_watch,
                report_writer=self._write_intraday_decision_report,
            )
        return self._run_delegated_slot(
            context=context,
            slot=resolved_slot,
            underlying_stage="post_market_review",
            runner=self.pipeline.run_post_market_review,
            report_writer=self._write_post_market_brief,
        )

    def _validate_slot(self, slot: str) -> ScheduledRunSlot:
        if slot not in SCHEDULED_RUN_SLOTS:
            valid = ", ".join(SCHEDULED_RUN_SLOTS)
            raise ValueError(f"未知 scheduled-run slot: {slot}; 可选值: {valid}")
        return slot

    def _trade_calendar_skip(
        self,
        context: PipelineRunContext,
        slot: ScheduledRunSlot,
    ) -> AgentResult | None:
        calendar = self.pipeline.collector.collect_trade_calendar(context.trade_date)
        self.pipeline.repository.save_raw_source_snapshots(context, [calendar.source_snapshot])
        self.pipeline.repository.save_trading_calendar_days(context, calendar.days)
        if (
            calendar.source_snapshot.status == "failed"
            and "trade_calendar" in self.pipeline.required_data_sources
        ):
            failure_reason = (
                "必需数据源失败: "
                f"trade_calendar: {calendar.source_snapshot.failure_reason or 'unknown failure'}"
            )
            self.pipeline.save_reliability_report(context)
            self._save_slot_failure(context, slot, failure_reason)
            raise DataProviderError(failure_reason)
        if calendar.snapshot is not None and calendar.snapshot.is_trade_date is False:
            self.pipeline.save_reliability_report(context)
            return self._save_slot_result(
                context,
                slot,
                "skipped",
                {
                    "skipped_reason": f"{context.trade_date.isoformat()} 非交易日，跳过定时任务",
                },
            )
        return None

    def _run_collect_slot(
        self,
        *,
        context: PipelineRunContext,
        slot: ScheduledRunSlot,
        report_filename: str,
        report_title: str,
    ) -> AgentResult:
        dataset = self.pipeline.collector.collect(trade_date=context.trade_date)
        self.pipeline.save_dataset(context, dataset)
        self.pipeline.run_data_quality_gate(
            context,
            slot,
            dataset,
            failure_payload_extra=self._slot_audit_payload(context, slot),
        )
        self.pipeline.save_reliability_report(context)
        quality_payload = self._latest_payload("data_quality_reports", context.run_id)
        report_path = write_markdown_report(
            self.pipeline.report_root,
            context.trade_date.isoformat(),
            report_filename,
            {
                "采集范围": [
                    f"universe: {len(dataset.assets)}",
                    f"market_bars: {len(dataset.bars)}",
                    f"announcements: {len(dataset.announcements)}",
                    f"news: {len(dataset.news)}",
                    f"policy: {len(dataset.policy_items)}",
                    f"industry: {len(dataset.industry_snapshots)}",
                ],
                "数据质量摘要": self._quality_lines(quality_payload),
                "安全边界": "只采集和审计数据，不生成真实交易或模拟交易订单。",
            },
            title=report_title,
        )
        return self._save_slot_result(
            context,
            slot,
            "success",
            {
                "report_path": str(report_path),
                "source_count": len(dataset.source_snapshots),
                "market_bar_count": len(dataset.bars),
                "announcement_count": len(dataset.announcements),
                "news_count": len(dataset.news),
                "policy_count": len(dataset.policy_items),
                "data_quality_status": str(quality_payload.get("status", "unknown")),
            },
        )

    def _run_delegated_slot(
        self,
        *,
        context: PipelineRunContext,
        slot: ScheduledRunSlot,
        underlying_stage: str,
        runner: Callable[[date], AgentResult],
        report_writer: Callable[[AgentResult], Path],
    ) -> AgentResult:
        try:
            result = runner(context.trade_date)
            report_path = report_writer(result)
        except Exception as exc:
            self._save_slot_failure(context, slot, str(exc), underlying_stage=underlying_stage)
            raise
        payload: dict[str, Any] = {
            "underlying_stage": underlying_stage,
            "underlying_run_id": result.payload.get("run_id"),
            "report_path": str(report_path),
        }
        if slot == "intraday_decision":
            payload.update(
                {
                    "order_count": int(result.payload.get("order_count", 0)),
                    "buy_order_count": int(result.payload.get("buy_order_count", 0)),
                    "sell_order_count": int(result.payload.get("sell_order_count", 0)),
                    "execution_event_count": int(result.payload.get("execution_event_count", 0)),
                    "execution_rejected_count": int(
                        result.payload.get("execution_rejected_count", 0)
                    ),
                }
            )
        if slot == "post_market_brief":
            payload.update(
                {
                    "new_order_count": int(result.payload.get("new_order_count", 0)),
                    "reviewed_order_count": int(result.payload.get("reviewed_order_count", 0)),
                }
            )
        return self._save_slot_result(context, slot, "success", payload)

    def _write_pre_market_brief(self, result: AgentResult) -> Path:
        run_id = str(result.payload["run_id"])
        trade_date_text = str(result.payload["trade_date"])
        watchlist = _mapping_list(result.payload.get("watchlist", []))
        signals = _mapping_list(result.payload.get("signals", []))
        decisions = _mapping_list(result.payload.get("risk_decisions", []))
        approved_symbols = {
            str(decision.get("symbol"))
            for decision in decisions
            if decision.get("approved") is True
        }
        rejected_reasons = [
            reason
            for decision in decisions
            if decision.get("approved") is not True
            for reason in _str_list(decision.get("reasons", []))
        ]
        market_status = str(result.payload.get("market_regime", "unknown"))
        market_reasons = _str_list(result.payload.get("market_reasons", []))
        quality_payload = self._latest_payload("data_quality_reports", run_id)

        if approved_symbols:
            conclusion = [
                "今日有模拟买入计划，等待 10:00 盘中阶段按分钟线和风控执行。",
                f"计划标的: {', '.join(sorted(approved_symbols))}",
            ]
        elif signals:
            conclusion = [
                "今日不模拟买入。",
                *[f"原因: {reason}" for reason in rejected_reasons],
            ]
        else:
            conclusion = ["今日不模拟买入。", "原因: 没有 ETF 同时满足趋势、成交额和风险条件。"]

        return write_markdown_report(
            self.pipeline.report_root,
            trade_date_text,
            "pre-market-brief.md",
            {
                "日期": trade_date_text,
                "1. 市场状态": [
                    f"市场状态：{market_status}",
                    *[f"理由：{reason}" for reason in market_reasons],
                ],
                "2. 今日观察 ETF": self._watchlist_lines(watchlist, approved_symbols),
                "3. 今日模拟交易结论": conclusion,
                "4. 数据质量摘要": self._quality_lines(quality_payload),
                "安全边界": "LLM 只做解释辅助，买入信号由规则和风控决定；本项目不真实下单。",
            },
            title="A 股 ETF 盘前简报",
        )

    def _write_intraday_decision_report(self, result: AgentResult) -> Path:
        orders = _mapping_list(result.payload.get("orders", []))
        events = _mapping_list(result.payload.get("execution_events", []))
        return write_markdown_report(
            self.pipeline.report_root,
            str(result.payload.get("trade_date", "")),
            "intraday-decision.md",
            {
                "盘中模拟订单": [
                    f"{order.get('side')} {order.get('symbol')} "
                    f"qty={order.get('quantity')} price={order.get('price')}"
                    for order in orders
                ],
                "成交失败": [
                    f"{event.get('side')} {event.get('symbol')}: {event.get('failure_reason')}"
                    for event in events
                    if event.get("status") == "rejected"
                ],
                "安全边界": "10:00 只执行模拟交易，不连接真实券商。",
            },
            title="A 股 ETF 盘中模拟决策",
        )

    def _write_post_market_brief(self, result: AgentResult) -> Path:
        run_id = str(result.payload["run_id"])
        portfolio = _mapping(result.payload.get("portfolio", {}))
        orders = _mapping_list(result.payload.get("reviewed_orders", []))
        positions = _mapping_list(result.payload.get("positions", []))
        review = _mapping(result.payload.get("review", {}))
        quality_payload = self._latest_payload("data_quality_reports", run_id)
        risk_lines = self._risk_review_lines(result.payload.get("trade_date", ""))
        return write_markdown_report(
            self.pipeline.report_root,
            str(result.payload.get("trade_date", "")),
            "post-market-brief.md",
            {
                "1. 账户变化": [
                    f"total_value: {portfolio.get('total_value', '-')}",
                    f"cash: {portfolio.get('cash', '-')}",
                    f"market_value: {portfolio.get('market_value', '-')}",
                    f"open_positions: {portfolio.get('open_positions', '-')}",
                ],
                "2. 今日模拟订单": [
                    f"{order.get('side')} {order.get('symbol')} "
                    f"qty={order.get('quantity')} price={order.get('price')} "
                    f"reason={order.get('reason')}"
                    for order in orders
                ],
                "3. 当前持仓": [
                    f"{position.get('symbol')} status={position.get('status')} "
                    f"qty={position.get('quantity')} current={position.get('current_price')}"
                    for position in positions
                ],
                "4. 信号与风控回顾": risk_lines,
                "5. 数据质量摘要": self._quality_lines(quality_payload),
                "6. 次日观察点": [
                    str(review.get("summary", "无复盘摘要")),
                    *_str_list(review.get("parameter_suggestions", [])),
                ],
                "安全边界": "收盘复盘只汇总盘中模拟订单和持仓，不新增订单、不真实下单。",
            },
            title="A 股 ETF 收盘复盘简报",
        )

    def _watchlist_lines(
        self,
        watchlist: list[Mapping[str, object]],
        approved_symbols: set[str],
    ) -> list[str]:
        lines: list[str] = []
        for candidate in watchlist[:5]:
            symbol = str(candidate.get("symbol", "-"))
            score = candidate.get("score", "-")
            action = "paper_buy_plan" if symbol in approved_symbols else "watch"
            reasons = "; ".join(_str_list(candidate.get("reasons", []))) or "-"
            lines.append(f"{symbol}: score={score}, 动作={action}, 理由={reasons}")
        return lines or ["无观察 ETF"]

    def _risk_review_lines(self, trade_date_value: object) -> list[str]:
        trade_date = date.fromisoformat(str(trade_date_value))
        decisions = self.pipeline.repository.load_latest_risk_decisions(
            trade_date,
            run_mode=self.pipeline.run_mode,
            backtest_id=self.pipeline.backtest_id,
        )
        if not decisions:
            return ["无盘前风控决策"]
        return [
            f"{decision.symbol}: {'通过' if decision.approved else '拒绝'}，"
            f"{'; '.join(decision.reasons) or '-'}"
            for decision in decisions
        ]

    def _latest_payload(self, table_name: str, run_id: str) -> Mapping[str, object]:
        rows = self.pipeline.repository.payload_rows(table_name, run_id=run_id)
        if not rows:
            return {}
        payload = rows[-1].get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError(f"{table_name} payload 必须是 JSON object")
        return cast(Mapping[str, object], payload)

    def _quality_lines(self, payload: Mapping[str, object]) -> list[str]:
        if not payload:
            return ["无数据质量报告"]
        lines = [
            f"status: {payload.get('status', '-')}",
            f"source_failure_rate: {payload.get('source_failure_rate', '-')}",
            f"missing_market_bar_count: {payload.get('missing_market_bar_count', '-')}",
            f"abnormal_price_count: {payload.get('abnormal_price_count', '-')}",
        ]
        issues = _mapping_list(payload.get("issues", []))
        lines.extend(
            f"{issue.get('severity')}: {issue.get('check_name')} - {issue.get('message')}"
            for issue in issues
        )
        return lines

    def _save_slot_result(
        self,
        context: PipelineRunContext,
        slot: ScheduledRunSlot,
        status: str,
        payload: dict[str, Any],
    ) -> AgentResult:
        full_payload: dict[str, Any] = {
            **self._slot_audit_payload(context, slot),
            "status": status,
            **payload,
            **self.pipeline.run_scope_payload(),
            **self.pipeline.strategy_params_payload(),
        }
        self.pipeline.repository.save_artifact(context.trade_date, slot, full_payload)
        self.pipeline.repository.save_pipeline_run(context, slot, status, full_payload)
        return AgentResult(name=slot, success=status != "failed", payload=full_payload)

    def _save_slot_failure(
        self,
        context: PipelineRunContext,
        slot: ScheduledRunSlot,
        failure_reason: str,
        *,
        underlying_stage: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"failure_reason": failure_reason}
        if underlying_stage is not None:
            payload["underlying_stage"] = underlying_stage
        self._save_slot_result(context, slot, "failed", payload)

    def _slot_audit_payload(
        self,
        context: PipelineRunContext,
        slot: ScheduledRunSlot,
    ) -> dict[str, Any]:
        return {
            "run_id": context.run_id,
            "trade_date": context.trade_date.isoformat(),
            "slot": slot,
            "stage": slot,
            "provider": self.provider_name,
            "llm_provider": self.llm_provider,
            "scheduled_at": datetime.now(BEIJING_TZ).isoformat(),
            "timezone": "Asia/Shanghai",
            "real_trading": False,
        }


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return cast(Mapping[str, object], value)


def _mapping_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    raw_items = cast(list[object], value)
    return [cast(Mapping[str, object], item) for item in raw_items if isinstance(item, Mapping)]


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    raw_items = cast(list[object], value)
    return [str(item) for item in raw_items]

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from ashare_agent.agents.strategy_params_agent import StrategyParams
from ashare_agent.domain import AgentResult, PipelineRunContext
from ashare_agent.llm.base import LLMClient
from ashare_agent.pipeline import ASharePipeline
from ashare_agent.providers.base import DataProvider, DataProviderError
from ashare_agent.repository import PipelineRepository


class BacktestRunner:
    def __init__(
        self,
        *,
        provider: DataProvider,
        llm_client: LLMClient,
        report_root: Path,
        repository: PipelineRepository,
        strategy_params: StrategyParams,
        provider_name: str,
        required_data_sources: set[str],
    ) -> None:
        self.provider = provider
        self.llm_client = llm_client
        self.report_root = report_root
        self.repository = repository
        self.strategy_params = strategy_params
        self.provider_name = provider_name
        self.required_data_sources = required_data_sources

    def run(self, *, start_date: date, end_date: date, backtest_id: str) -> AgentResult:
        if start_date > end_date:
            raise ValueError("start_date 不能晚于 end_date")
        trade_days = [
            trade_day
            for trade_day in sorted(self.provider.get_trade_calendar())
            if start_date <= trade_day <= end_date
        ]
        if not trade_days:
            raise DataProviderError("回放日期范围内没有交易日")

        succeeded_days = 0
        failures: list[dict[str, str]] = []
        for trade_day in trade_days:
            pipeline = ASharePipeline(
                provider=self.provider,
                llm_client=self.llm_client,
                report_root=self.report_root,
                repository=self.repository,
                strategy_params=self.strategy_params,
                required_data_sources=self.required_data_sources,
                run_mode="backtest",
                backtest_id=backtest_id,
            )
            try:
                pipeline.run_pre_market(trade_day)
                pipeline.run_post_market_review(trade_day)
            except DataProviderError as exc:
                failures.append({"trade_date": trade_day.isoformat(), "reason": str(exc)})
                continue
            succeeded_days += 1

        payload: dict[str, Any] = {
            "provider": self.provider_name,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "attempted_days": len(trade_days),
            "succeeded_days": succeeded_days,
            "failed_days": len(failures),
            "failures": failures,
            "strategy_params_version": self.strategy_params.version,
            "strategy_params_snapshot": self.strategy_params.snapshot(),
        }
        context = PipelineRunContext(
            trade_date=trade_days[-1],
            run_mode="backtest",
            backtest_id=backtest_id,
        )
        status = "success" if not failures else "failed"
        self.repository.save_pipeline_run(context, "backtest", status, payload)
        return AgentResult(name="backtest", success=not failures, payload=payload)

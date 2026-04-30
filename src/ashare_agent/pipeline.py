from __future__ import annotations

from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from ashare_agent.agents.announcement_analyzer import AnnouncementAnalyzer
from ashare_agent.agents.data_collector import DataCollector
from ashare_agent.agents.market_regime_analyzer import MarketRegimeAnalyzer
from ashare_agent.agents.paper_trader import PaperTrader
from ashare_agent.agents.review_agent import ReviewAgent
from ashare_agent.agents.risk_manager import RiskManager
from ashare_agent.agents.signal_engine import SignalEngine
from ashare_agent.domain import (
    AgentResult,
    MarketDataset,
    PipelineRunContext,
    RiskDecision,
    SignalResult,
)
from ashare_agent.indicators import calculate_indicators
from ashare_agent.llm.base import LLMClient
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.base import DataProvider, DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.reports import write_markdown_report
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
        required_data_sources: set[str] | None = None,
    ) -> None:
        self.collector = DataCollector(provider)
        self.announcement_analyzer = AnnouncementAnalyzer()
        self.market_regime_analyzer = MarketRegimeAnalyzer()
        self.signal_engine = SignalEngine()
        self.risk_manager = RiskManager()
        self.trader = trader or PaperTrader()
        self.review_agent = ReviewAgent()
        self.llm_client = llm_client
        self.report_root = report_root
        self.repository = repository or InMemoryRepository()
        self.required_data_sources = required_data_sources or set()
        self._last_dataset: MarketDataset | None = None
        self._last_signal_result: SignalResult | None = None
        self._last_risk_decisions: list[RiskDecision] = []

    def _save_dataset(self, context: PipelineRunContext, dataset: MarketDataset) -> None:
        self.repository.save_universe_assets(context, dataset.assets)
        self.repository.save_raw_source_snapshots(context, dataset.source_snapshots)
        self.repository.save_market_bars(context, dataset.bars)
        self.repository.save_announcements(context, dataset.announcements)
        self.repository.save_news_items(context, dataset.news)
        self.repository.save_policy_items(context, dataset.policy_items)

    def _required_source_failure_reason(self, dataset: MarketDataset) -> str | None:
        failures = [
            snapshot
            for snapshot in dataset.source_snapshots
            if snapshot.source in self.required_data_sources and snapshot.status == "failed"
        ]
        if not failures:
            return None
        return "; ".join(
            f"{snapshot.source}: {snapshot.failure_reason or 'unknown failure'}"
            for snapshot in failures
        )

    def _fail_if_required_sources_failed(
        self,
        context: PipelineRunContext,
        stage: str,
        dataset: MarketDataset,
    ) -> None:
        required_failure = self._required_source_failure_reason(dataset)
        if required_failure is None:
            return
        payload = {
            "run_id": context.run_id,
            "failure_reason": f"必需数据源失败: {required_failure}",
        }
        self.repository.save_artifact(context.trade_date, f"{stage}_failed", payload)
        self.repository.save_pipeline_run(
            context,
            stage,
            "failed",
            payload,
        )
        raise DataProviderError(payload["failure_reason"])

    def run_pre_market(self, trade_date: date) -> AgentResult:
        context = PipelineRunContext(trade_date=trade_date)
        dataset = self.collector.collect(trade_date=trade_date)
        self._save_dataset(context, dataset)
        self._fail_if_required_sources_failed(context, "pre_market", dataset)
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
        decisions = self.risk_manager.evaluate(
            trade_date=trade_date,
            signals=signal_result.signals,
            open_positions=self.trader.open_positions(),
            cash=self.trader.cash,
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
            "signals": _to_dict_list(signal_result.signals),
            "watchlist": _to_dict_list(signal_result.watchlist),
            "risk_decisions": _to_dict_list(decisions),
            "report_path": str(report_path),
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
                "watchlist_count": len(signal_result.watchlist),
                "signal_count": len(signal_result.signals),
                "risk_decision_count": len(decisions),
            },
        )
        self._last_dataset = dataset
        self._last_signal_result = signal_result
        self._last_risk_decisions = decisions
        return AgentResult(name="pre_market", success=True, payload=payload)

    def run_intraday_watch(self, trade_date: date) -> AgentResult:
        context = PipelineRunContext(trade_date=trade_date)
        report_path = write_markdown_report(
            self.report_root,
            trade_date.isoformat(),
            "intraday-watch.md",
            {
                "状态": "盘中只监控，不执行真实交易。",
                "安全边界": "本项目 v1 只有 paper trading。",
            },
        )
        payload = {"run_id": context.run_id, "report_path": str(report_path), "real_trading": False}
        self.repository.save_artifact(trade_date, "intraday_watch", payload)
        self.repository.save_pipeline_run(
            context,
            "intraday_watch",
            "success",
            {"report_path": str(report_path), "real_trading": False},
        )
        return AgentResult(name="intraday_watch", success=True, payload=payload)

    def run_post_market_review(self, trade_date: date) -> AgentResult:
        context = PipelineRunContext(trade_date=trade_date)
        if self._last_dataset is None:
            dataset = self.collector.collect(trade_date=trade_date)
            self._save_dataset(context, dataset)
            self._fail_if_required_sources_failed(context, "post_market_review", dataset)
        else:
            dataset = self._last_dataset
        decisions = self._last_risk_decisions or self.repository.load_latest_risk_decisions(
            trade_date
        )
        if not self.trader.positions:
            self.trader.positions = self.repository.load_open_positions()
        self.trader.cash = self.repository.load_latest_cash(default_cash=self.trader.cash)
        trade_result = self.trader.apply_pre_market_decisions(
            trade_date=trade_date,
            decisions=decisions,
            bars=dataset.bars,
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
        payload: dict[str, Any] = {
            "run_id": context.run_id,
            "orders": _to_dict_list(trade_result.orders),
            "positions": _to_dict_list(self.trader.open_positions()),
            "portfolio": asdict(snapshot),
            "review": asdict(report),
            "report_path": f"paper:{report_path}",
        }
        self.repository.save_paper_orders(context, trade_result.orders)
        self.repository.save_paper_positions(context, self.trader.open_positions())
        self.repository.save_portfolio_snapshot(context, snapshot)
        self.repository.save_review_report(context, report)
        self.repository.save_artifact(trade_date, "post_market_review", payload)
        self.repository.save_pipeline_run(
            context,
            "post_market_review",
            "success",
            {
                "report_path": str(report_path),
                "order_count": len(trade_result.orders),
                "open_positions": snapshot.open_positions,
            },
        )
        return AgentResult(name="post_market_review", success=True, payload=payload)


def build_mock_pipeline(report_root: Path) -> ASharePipeline:
    return ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=report_root,
    )

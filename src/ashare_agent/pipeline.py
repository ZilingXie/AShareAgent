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
from ashare_agent.domain import AgentResult, MarketDataset, RiskDecision, SignalResult
from ashare_agent.indicators import calculate_indicators
from ashare_agent.llm.base import LLMClient
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.base import DataProvider
from ashare_agent.providers.mock import MockProvider
from ashare_agent.reports import write_markdown_report
from ashare_agent.repository import InMemoryRepository


def _to_dict_list(values: list[Any]) -> list[dict[str, Any]]:
    return [asdict(value) for value in values]


class ASharePipeline:
    def __init__(
        self,
        provider: DataProvider,
        llm_client: LLMClient,
        report_root: Path,
        repository: InMemoryRepository | None = None,
        trader: PaperTrader | None = None,
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
        self._last_dataset: MarketDataset | None = None
        self._last_signal_result: SignalResult | None = None
        self._last_risk_decisions: list[RiskDecision] = []

    def run_pre_market(self, trade_date: date) -> AgentResult:
        dataset = self.collector.collect(trade_date=trade_date)
        events = self.announcement_analyzer.analyze(dataset.announcements)
        regime = self.market_regime_analyzer.analyze(trade_date=trade_date, bars=dataset.bars)
        indicators = calculate_indicators(trade_date=trade_date, bars=dataset.bars)
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
            "signals": _to_dict_list(signal_result.signals),
            "watchlist": _to_dict_list(signal_result.watchlist),
            "risk_decisions": _to_dict_list(decisions),
            "report_path": str(report_path),
        }
        self.repository.save_artifact(trade_date, "pre_market", payload)
        self._last_dataset = dataset
        self._last_signal_result = signal_result
        self._last_risk_decisions = decisions
        return AgentResult(name="pre_market", success=True, payload=payload)

    def run_intraday_watch(self, trade_date: date) -> AgentResult:
        report_path = write_markdown_report(
            self.report_root,
            trade_date.isoformat(),
            "intraday-watch.md",
            {
                "状态": "盘中只监控，不执行真实交易。",
                "安全边界": "本项目 v1 只有 paper trading。",
            },
        )
        payload = {"report_path": str(report_path), "real_trading": False}
        self.repository.save_artifact(trade_date, "intraday_watch", payload)
        return AgentResult(name="intraday_watch", success=True, payload=payload)

    def run_post_market_review(self, trade_date: date) -> AgentResult:
        dataset = self._last_dataset or self.collector.collect(trade_date=trade_date)
        self.trader.apply_pre_market_decisions(
            trade_date=trade_date,
            decisions=self._last_risk_decisions,
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
            "portfolio": asdict(snapshot),
            "review": asdict(report),
            "report_path": f"paper:{report_path}",
        }
        self.repository.save_artifact(trade_date, "post_market_review", payload)
        return AgentResult(name="post_market_review", success=True, payload=payload)


def build_mock_pipeline(report_root: Path) -> ASharePipeline:
    return ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=report_root,
    )


from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from ashare_agent.agents.strategy_params_agent import StrategyParams, StrategyParamsAgent
from ashare_agent.domain import (
    Asset,
    MarketBar,
    PaperPosition,
    PipelineRunContext,
    PortfolioSnapshot,
)
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.pipeline import ASharePipeline, build_mock_pipeline
from ashare_agent.providers.base import DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository


class ExitScenarioProvider(MockProvider):
    def __init__(
        self,
        *,
        close: Decimal,
        calendar_start: date,
        calendar_days: int,
    ) -> None:
        super().__init__([Asset(symbol="510300", name="沪深300ETF", asset_type="ETF")])
        self._close = close
        self._calendar = [calendar_start + timedelta(days=idx) for idx in range(calendar_days)]

    def get_market_bars(self, trade_date: date, lookback_days: int = 30) -> list[MarketBar]:
        return [
            MarketBar(
                symbol="510300",
                trade_date=trade_date - timedelta(days=lookback_days - 1 - idx),
                open=self._close,
                high=self._close,
                low=self._close,
                close=self._close,
                volume=1_000_000,
                amount=self._close * Decimal("1000000"),
                source="test",
            )
            for idx in range(lookback_days)
        ]

    def get_trade_calendar(self) -> list[date]:
        return list(self._calendar)


def _write_strategy_params(
    path: Path,
    *,
    version: str = "pipeline-test-params",
    stop_loss_pct: str = "0.05",
    max_daily_loss_pct: str = "0.02",
    price_limit_pct: str = "0.098",
    min_holding_trade_days: int = 2,
    max_holding_trade_days: int = 10,
) -> None:
    path.write_text(
        f"""
version: "{version}"
risk:
  max_positions: 5
  target_position_pct: "0.10"
  min_cash: "100"
  max_daily_loss_pct: "{max_daily_loss_pct}"
  stop_loss_pct: "{stop_loss_pct}"
  price_limit_pct: "{price_limit_pct}"
  min_holding_trade_days: {min_holding_trade_days}
  max_holding_trade_days: {max_holding_trade_days}
  blacklist: []
paper_trader:
  initial_cash: "100000"
  position_size_pct: "0.10"
  slippage_pct: "0.001"
""",
        encoding="utf-8",
    )


def _strategy_params(tmp_path: Path, **overrides: Any) -> StrategyParams:
    config_path = tmp_path / "strategy_params.yml"
    _write_strategy_params(config_path, **overrides)
    return StrategyParamsAgent(config_path).load()


def _seed_open_position(
    repository: InMemoryRepository,
    *,
    opened_at: date,
    trade_date: date,
    current_price: Decimal,
    entry_price: Decimal = Decimal("100"),
) -> None:
    context = PipelineRunContext(trade_date=opened_at, run_id=f"seed-{opened_at.isoformat()}")
    repository.save_paper_positions(
        context,
        [
            PaperPosition(
                symbol="510300",
                opened_at=opened_at,
                quantity=100,
                entry_price=entry_price,
                current_price=current_price,
                status="open",
            )
        ],
    )
    repository.save_portfolio_snapshot(
        PipelineRunContext(trade_date=trade_date, run_id=f"snapshot-{trade_date.isoformat()}"),
        PortfolioSnapshot(
            trade_date=trade_date,
            cash=Decimal("90000"),
            market_value=current_price * Decimal("100"),
            total_value=Decimal("90000") + current_price * Decimal("100"),
            open_positions=1,
        ),
    )


def test_mock_pipeline_runs_pre_market_and_post_market_with_audit_outputs(tmp_path: Path) -> None:
    pipeline = build_mock_pipeline(report_root=tmp_path)
    trade_date = date(2026, 4, 29)

    pre_market = pipeline.run_pre_market(trade_date)
    intraday = pipeline.run_intraday_watch(trade_date)
    review = pipeline.run_post_market_review(trade_date)

    assert pre_market.success is True
    assert intraday.success is True
    assert review.success is True
    assert len(pre_market.payload["signals"]) <= 1
    assert "paper" in review.payload["report_path"]
    assert (tmp_path / "2026-04-29" / "pre-market.md").exists()
    assert (tmp_path / "2026-04-29" / "post-market-review.md").exists()

    repository = pipeline.repository
    assert isinstance(repository, InMemoryRepository)
    pipeline_runs = repository.records_for("pipeline_runs")
    assert [row["payload"]["strategy_params_version"] for row in pipeline_runs] == [
        "strategy-params-v1",
        "strategy-params-v1",
        "strategy-params-v1",
    ]
    assert (
        pipeline_runs[0]["payload"]["strategy_params_snapshot"]["risk"]["stop_loss_pct"] == "0.05"
    )


def test_pipeline_persists_state_for_later_post_market_review(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    first_pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pre_market = first_pipeline.run_pre_market(trade_date)

    assert pre_market.payload["run_id"]
    assert repository.records_for("universe_assets")
    assert repository.records_for("raw_source_snapshots")
    assert repository.records_for("market_bars")
    assert repository.records_for("announcements")
    assert repository.records_for("news_items")
    assert repository.records_for("policy_items")
    assert repository.records_for("data_quality_reports")
    assert repository.records_for("technical_indicators")
    assert repository.records_for("pipeline_runs")
    assert repository.records_for("watchlist_candidates")
    assert repository.records_for("signals")
    assert repository.records_for("risk_decisions")

    later_pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )
    review = later_pipeline.run_post_market_review(trade_date)

    assert review.success is True
    first_orders = repository.records_for("paper_orders")
    assert first_orders
    assert all(order["payload"]["is_real_trade"] is False for order in first_orders)
    assert repository.records_for("paper_positions")
    assert repository.records_for("portfolio_snapshots")
    assert repository.records_for("review_reports")
    assert repository.records_for("data_quality_reports")[-1]["payload"]["stage"] == (
        "post_market_review"
    )

    repeat_pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )
    repeat_pipeline.run_post_market_review(trade_date)

    assert len(repository.records_for("paper_orders")) == len(first_orders)


def test_pipeline_closes_position_on_stop_loss(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 30)
    repository = InMemoryRepository()
    _seed_open_position(
        repository,
        opened_at=date(2026, 4, 29),
        trade_date=trade_date,
        current_price=Decimal("100"),
    )
    pipeline = ASharePipeline(
        provider=ExitScenarioProvider(
            close=Decimal("94"),
            calendar_start=date(2026, 4, 29),
            calendar_days=2,
        ),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_post_market_review(trade_date)

    sell_orders = [
        row["payload"]
        for row in repository.records_for("paper_orders")
        if row["payload"]["side"] == "sell"
    ]
    positions = repository.records_for("paper_positions")
    assert sell_orders
    assert sell_orders[0]["is_real_trade"] is False
    assert positions[-1]["payload"]["status"] == "closed"
    assert positions[-1]["payload"]["closed_at"] == trade_date.isoformat()


def test_pipeline_uses_configured_strategy_params_for_stop_loss(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 30)
    repository = InMemoryRepository()
    _seed_open_position(
        repository,
        opened_at=date(2026, 4, 29),
        trade_date=trade_date,
        current_price=Decimal("100"),
    )
    pipeline = ASharePipeline(
        provider=ExitScenarioProvider(
            close=Decimal("94"),
            calendar_start=date(2026, 4, 29),
            calendar_days=2,
        ),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
        strategy_params=_strategy_params(tmp_path, stop_loss_pct="0.10"),
    )

    pipeline.run_post_market_review(trade_date)

    assert repository.records_for("paper_orders") == []
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["strategy_params_snapshot"]["risk"]["stop_loss_pct"] == "0.10"


def test_pipeline_rejects_t_plus_one_stop_loss_sell(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    _seed_open_position(
        repository,
        opened_at=trade_date,
        trade_date=trade_date,
        current_price=Decimal("100"),
    )
    pipeline = ASharePipeline(
        provider=ExitScenarioProvider(
            close=Decimal("94"),
            calendar_start=trade_date,
            calendar_days=1,
        ),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_post_market_review(trade_date)

    assert repository.records_for("paper_orders") == []
    assert repository.records_for("paper_positions")[-1]["payload"]["status"] == "open"


def test_pipeline_closes_position_after_max_holding_days(tmp_path: Path) -> None:
    opened_at = date(2026, 4, 1)
    trade_date = date(2026, 4, 11)
    repository = InMemoryRepository()
    _seed_open_position(
        repository,
        opened_at=opened_at,
        trade_date=trade_date,
        current_price=Decimal("100"),
    )
    pipeline = ASharePipeline(
        provider=ExitScenarioProvider(
            close=Decimal("101"),
            calendar_start=opened_at,
            calendar_days=11,
        ),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_post_market_review(trade_date)

    sell_orders = [
        row["payload"]
        for row in repository.records_for("paper_orders")
        if row["payload"]["side"] == "sell"
    ]
    assert sell_orders
    assert "到期" in sell_orders[0]["reason"]
    assert repository.records_for("paper_positions")[-1]["payload"]["status"] == "closed"


def test_pipeline_records_required_source_failure_before_raising(tmp_path: Path) -> None:
    class BrokenMarketProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30):  # type: ignore[no-untyped-def]
            raise DataProviderError("行情接口失败")

    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=BrokenMarketProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
        required_data_sources={"market_bars"},
    )

    try:
        pipeline.run_pre_market(trade_date)
    except DataProviderError as exc:
        assert "market_bars" in str(exc)
    else:
        raise AssertionError("必需数据源失败时 pre-market 必须失败")

    snapshots = repository.records_for("raw_source_snapshots")
    quality_reports = repository.records_for("data_quality_reports")
    assert any(
        row["payload"]["source"] == "market_bars" and row["payload"]["status"] == "failed"
        for row in snapshots
    )
    assert quality_reports[-1]["payload"]["status"] == "failed"
    assert quality_reports[-1]["payload"]["stage"] == "pre_market"
    assert repository.records_for("pipeline_runs")[-1]["payload"]["status"] == "failed"
    failed_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert failed_run["strategy_params_version"] == "strategy-params-v1"
    assert failed_run["strategy_params_snapshot"]["risk"]["stop_loss_pct"] == "0.05"


def test_pipeline_records_data_quality_failure_before_raising(tmp_path: Path) -> None:
    class MissingLatestBarProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30) -> list[MarketBar]:
            return [
                bar
                for bar in super().get_market_bars(trade_date, lookback_days)
                if not (bar.symbol == "510300" and bar.trade_date == trade_date)
            ]

    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=MissingLatestBarProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
        required_data_sources={"market_bars", "trade_calendar"},
    )

    try:
        pipeline.run_pre_market(trade_date)
    except DataProviderError as exc:
        assert "数据质量检查失败" in str(exc)
    else:
        raise AssertionError("缺失交易日行情时 pre-market 必须失败")

    latest_quality = repository.records_for("data_quality_reports")[-1]["payload"]
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_quality["status"] == "failed"
    assert latest_quality["missing_market_bar_count"] == 1
    assert latest_run["status"] == "failed"
    assert "数据质量检查失败" in latest_run["failure_reason"]


def test_post_market_records_required_source_failure_before_raising(tmp_path: Path) -> None:
    class BrokenMarketProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30):  # type: ignore[no-untyped-def]
            raise DataProviderError("行情接口失败")

    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=BrokenMarketProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
        required_data_sources={"market_bars"},
    )

    try:
        pipeline.run_post_market_review(trade_date)
    except DataProviderError as exc:
        assert "market_bars" in str(exc)
    else:
        raise AssertionError("必需数据源失败时 post-market-review 必须失败")

    assert any(
        row["payload"]["source"] == "market_bars" and row["payload"]["status"] == "failed"
        for row in repository.records_for("raw_source_snapshots")
    )
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "post_market_review"
    assert latest_run["status"] == "failed"
    assert latest_run["strategy_params_version"] == "strategy-params-v1"
    assert latest_run["strategy_params_snapshot"]["risk"]["max_daily_loss_pct"] == "0.02"

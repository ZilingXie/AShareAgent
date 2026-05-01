from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from ashare_agent.agents.strategy_params_agent import StrategyParams, StrategyParamsAgent
from ashare_agent.domain import (
    Asset,
    IntradayBar,
    MarketBar,
    PaperOrder,
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

    def get_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> list[IntradayBar]:
        return [
            IntradayBar(
                symbol=symbol,
                trade_date=trade_date,
                timestamp=datetime(trade_date.year, trade_date.month, trade_date.day, 9, 31),
                open=self._close,
                high=self._close,
                low=self._close,
                close=self._close,
                volume=1_000_000,
                amount=self._close * Decimal("1000000"),
                source="test_intraday",
            )
            for symbol in symbols
        ]


class NoIntradayBarsProvider(MockProvider):
    def get_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> list[IntradayBar]:
        return []


class BrokenIntradayProvider(MockProvider):
    intraday_source = "akshare_em"
    intraday_timeout_seconds = 2.0
    intraday_retry_attempts = 3

    def get_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> list[IntradayBar]:
        raise DataProviderError(
            "akshare_em 分钟线源不可用: symbol=510300 attempts=3 timeout=2.0",
            metadata={
                "intraday_source": "akshare_em",
                "failed_symbol": "510300",
                "timeout_seconds": 2.0,
                "retry_attempts": 3,
            },
        )


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
signal:
  min_score: "0.55"
  max_daily_signals: 1
  weights:
    technical: "0.45"
    market: "0.25"
    event: "0.20"
    risk_penalty: "0.10"
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
    symbol: str = "510300",
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
                symbol=symbol,
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
    repository = pipeline.repository
    assert isinstance(repository, InMemoryRepository)
    pre_market_run_id = pre_market.payload["run_id"]
    assert [
        row
        for row in repository.records_for("paper_orders")
        if row["run_id"] == pre_market_run_id
    ] == []
    assert "paper" in review.payload["report_path"]
    assert (tmp_path / "2026-04-29" / "pre-market.md").exists()
    assert (tmp_path / "2026-04-29" / "post-market-review.md").exists()

    pipeline_runs = repository.records_for("pipeline_runs")
    assert [row["payload"]["strategy_params_version"] for row in pipeline_runs] == [
        "strategy-params-v1",
        "strategy-params-v1",
        "strategy-params-v1",
    ]
    assert (
        pipeline_runs[0]["payload"]["strategy_params_snapshot"]["risk"]["stop_loss_pct"] == "0.05"
    )
    assert pipeline_runs[0]["payload"]["run_mode"] == "normal"
    assert pipeline_runs[0]["payload"]["backtest_id"] is None
    signals = repository.records_for("signals")
    assert signals[0]["payload"]["strategy_params_version"] == "strategy-params-v1"
    assert signals[0]["payload"]["strategy_params_snapshot"]["signal"]["max_daily_signals"] == 1


def test_intraday_watch_executes_buy_sell_and_updates_positions(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    _seed_open_position(
        repository,
        symbol="159915",
        opened_at=date(2026, 4, 28),
        trade_date=date(2026, 4, 28),
        current_price=Decimal("3.80"),
        entry_price=Decimal("100"),
    )
    pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_pre_market(trade_date)
    intraday = pipeline.run_intraday_watch(trade_date)

    assert intraday.success is True
    intraday_orders = [
        row["payload"]
        for row in repository.records_for("paper_orders")
        if row["run_id"] == intraday.payload["run_id"]
    ]
    assert [order["side"] for order in intraday_orders] == ["buy", "sell"]
    assert {order["symbol"] for order in intraday_orders} == {"510300", "159915"}
    assert all(order["is_real_trade"] is False for order in intraday_orders)
    assert all(order["execution_method"] == "first_valid_1m_bar" for order in intraday_orders)
    assert all(order["used_daily_fallback"] is False for order in intraday_orders)
    assert all(order["execution_source"] == "mock_intraday" for order in intraday_orders)
    assert intraday.payload["execution_events"]
    assert all(event["status"] == "filled" for event in intraday.payload["execution_events"])
    intraday_run_payload = repository.records_for("pipeline_runs")[-1]["payload"]
    assert len(intraday_run_payload["execution_events"]) == len(
        intraday.payload["execution_events"]
    )
    assert intraday_run_payload["execution_events"][0]["status"] == "filled"
    assert intraday_run_payload["execution_events"][0]["used_daily_fallback"] is False
    assert any(
        row["payload"]["source"] == "intraday_bars"
        for row in repository.records_for("raw_source_snapshots")
    )
    latest_positions = [row["payload"] for row in repository.records_for("paper_positions")]
    assert any(
        position["symbol"] == "510300" and position["status"] == "open"
        for position in latest_positions
    )
    assert any(
        position["symbol"] == "159915" and position["status"] == "closed"
        for position in latest_positions
    )
    assert repository.records_for("portfolio_snapshots")[-1]["run_id"] == intraday.payload["run_id"]


def test_intraday_watch_is_idempotent_for_same_trade_date(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)
    first_order_count = len(repository.records_for("paper_orders"))
    pipeline.run_intraday_watch(trade_date)

    assert first_order_count > 0
    assert len(repository.records_for("paper_orders")) == first_order_count


def test_intraday_watch_records_rejected_execution_event_without_minute_bars(
    tmp_path: Path,
) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=NoIntradayBarsProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_pre_market(trade_date)
    intraday = pipeline.run_intraday_watch(trade_date)

    assert intraday.success is True
    assert intraday.payload["orders"] == []
    assert intraday.payload["execution_events"][0]["status"] == "rejected"
    assert intraday.payload["execution_events"][0]["failure_reason"] == "无分钟线，无法成交"
    assert intraday.payload["execution_events"][0]["used_daily_fallback"] is False
    intraday_snapshot = repository.records_for("raw_source_snapshots")[-1]["payload"]
    assert intraday_snapshot["source"] == "intraday_bars"
    assert intraday_snapshot["status"] == "success"
    assert intraday_snapshot["metadata"]["missing_symbols"] == ["510300"]
    intraday_run_payload = repository.records_for("pipeline_runs")[-1]["payload"]
    assert intraday_run_payload["execution_events"][0]["status"] == "rejected"
    assert (
        intraday_run_payload["execution_events"][0]["failure_reason"]
        == "无分钟线，无法成交"
    )
    assert repository.records_for("paper_orders") == []


def test_intraday_watch_fails_when_intraday_provider_fails(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=BrokenIntradayProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_pre_market(trade_date)

    try:
        pipeline.run_intraday_watch(trade_date)
    except DataProviderError as exc:
        assert "akshare_em" in str(exc)
        assert "510300" in str(exc)
    else:
        raise AssertionError("分钟线 provider 整体失败时 intraday_watch 必须失败")

    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "intraday_watch"
    assert latest_run["status"] == "failed"
    intraday_snapshot = next(
        row["payload"]
        for row in repository.records_for("raw_source_snapshots")
        if row["payload"]["source"] == "intraday_bars"
    )
    assert intraday_snapshot["status"] == "failed"
    assert intraday_snapshot["metadata"]["intraday_source"] == "akshare_em"
    assert intraday_snapshot["metadata"]["failed_symbol"] == "510300"


def test_intraday_watch_fails_without_successful_pre_market_decisions(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    try:
        pipeline.run_intraday_watch(trade_date)
    except DataProviderError as exc:
        assert "pre_market" in str(exc)
    else:
        raise AssertionError("intraday_watch 缺少同日 pre_market 决策时必须失败")

    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "intraday_watch"
    assert latest_run["status"] == "failed"


def test_post_market_review_writes_strategy_experiment_report(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    _seed_open_position(
        repository,
        opened_at=date(2026, 4, 28),
        trade_date=date(2026, 4, 28),
        current_price=Decimal("100"),
    )
    pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)
    review = pipeline.run_post_market_review(trade_date)

    report_path = tmp_path / "2026-04-29" / "strategy-experiment.md"
    content = report_path.read_text(encoding="utf-8")

    assert review.payload["experiment_report_path"] == str(report_path)
    assert "## LLM 盘前分析" in content
    assert "Mock 盘前分析" in content
    assert "## 风控拒绝原因" in content
    assert "已有持仓，避免重复买入" in content
    assert "## 模拟订单" in content
    assert "| side | symbol | quantity | price | amount | reason | real_trade |" in content
    assert "| sell | 510300" in content
    assert "触发止损" in content
    assert "## 卖出原因" in content
    assert "触发止损: 1" in content


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
    intraday = later_pipeline.run_intraday_watch(trade_date)

    assert intraday.success is True
    first_orders = repository.records_for("paper_orders")
    assert first_orders
    assert all(order["payload"]["is_real_trade"] is False for order in first_orders)
    assert repository.records_for("paper_positions")
    assert repository.records_for("portfolio_snapshots")
    assert repository.records_for("data_quality_reports")[-1]["payload"]["stage"] == (
        "intraday_watch"
    )

    repeat_pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )
    repeat_pipeline.run_intraday_watch(trade_date)

    assert len(repository.records_for("paper_orders")) == len(first_orders)
    review_order_count = len(repository.records_for("paper_orders"))
    review = repeat_pipeline.run_post_market_review(trade_date)

    assert review.success is True
    assert len(repository.records_for("paper_orders")) == review_order_count
    assert repository.records_for("review_reports")
    assert repository.records_for("data_quality_reports")[-1]["payload"]["stage"] == (
        "post_market_review"
    )


def test_post_market_review_does_not_create_orders(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    repository = InMemoryRepository()
    pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)
    order_count_after_intraday = len(repository.records_for("paper_orders"))
    legacy_context = PipelineRunContext(trade_date=trade_date, run_id="legacy-post-order-run")
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
                symbol="159915",
                trade_date=trade_date,
                side="buy",
                quantity=100,
                price=Decimal("3.0000"),
                amount=Decimal("300.00"),
                slippage=Decimal("0.001"),
                reason="旧流程盘后买单，不应进入新复盘统计",
            )
        ],
    )
    order_count_with_legacy = len(repository.records_for("paper_orders"))
    review = pipeline.run_post_market_review(trade_date)

    assert order_count_after_intraday > 0
    assert len(repository.records_for("paper_orders")) == order_count_with_legacy
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "post_market_review"
    assert latest_run["new_order_count"] == 0
    assert latest_run["reviewed_order_count"] == order_count_after_intraday
    assert "legacy-post-market-buy" not in {
        order["order_id"] for order in review.payload["reviewed_orders"]
    }
    assert repository.records_for("review_reports")[-1]["run_id"] == review.payload["run_id"]


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

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)

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

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)

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

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)

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

    pipeline.run_pre_market(trade_date)
    pipeline.run_intraday_watch(trade_date)

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


def test_daily_run_records_reliability_report_after_success(tmp_path: Path) -> None:
    trade_date = date(2026, 4, 29)
    pipeline = build_mock_pipeline(report_root=tmp_path)

    result = pipeline.run_daily(trade_date)

    assert result.success is True
    repository = pipeline.repository
    assert isinstance(repository, InMemoryRepository)
    assert repository.records_for("data_reliability_reports")
    business_stages = [
        row["payload"]["stage"]
        for row in repository.records_for("pipeline_runs")
        if row["payload"]["stage"] != "daily_run"
    ]
    assert business_stages == ["pre_market", "intraday_watch", "post_market_review"]
    stage_by_run_id = {
        row["run_id"]: row["payload"]["stage"] for row in repository.records_for("pipeline_runs")
    }
    assert {
        stage_by_run_id[row["run_id"]] for row in repository.records_for("paper_orders")
    } == {"intraday_watch"}
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "daily_run"
    assert latest_run["status"] == "success"


def test_daily_run_records_failed_reliability_report_before_raising(tmp_path: Path) -> None:
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
        pipeline.run_daily(trade_date)
    except DataProviderError as exc:
        assert "market_bars" in str(exc) or "数据质量检查失败" in str(exc)
    else:
        raise AssertionError("daily-run 遇到质量失败必须抛错")

    assert repository.records_for("data_reliability_reports")
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "daily_run"
    assert latest_run["status"] == "failed"


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

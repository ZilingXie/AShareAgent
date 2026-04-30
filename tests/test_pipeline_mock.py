from __future__ import annotations

from datetime import date
from pathlib import Path

from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.pipeline import ASharePipeline, build_mock_pipeline
from ashare_agent.providers.base import DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository


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

    repeat_pipeline = ASharePipeline(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
    )
    repeat_pipeline.run_post_market_review(trade_date)

    assert len(repository.records_for("paper_orders")) == len(first_orders)


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
    assert any(
        row["payload"]["source"] == "market_bars" and row["payload"]["status"] == "failed"
        for row in snapshots
    )
    assert repository.records_for("pipeline_runs")[-1]["payload"]["status"] == "failed"


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

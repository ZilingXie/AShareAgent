from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.base import DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository
from ashare_agent.strategy_evaluation import (
    CachingDataProvider,
    StrategyEvaluationRunner,
    load_strategy_evaluation_config,
)


def _write_base_params(path: Path) -> None:
    path.write_text(
        """
version: "strategy-params-v1"
risk:
  max_positions: 5
  target_position_pct: "0.10"
  min_cash: "100"
  max_daily_loss_pct: "0.02"
  stop_loss_pct: "0.05"
  price_limit_pct: "0.098"
  min_holding_trade_days: 2
  max_holding_trade_days: 10
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


def _write_eval_config(path: Path, base_config: Path, variants: str) -> None:
    path.write_text(
        f"""
base_config: {base_config.as_posix()}
variants:
{variants}
""",
        encoding="utf-8",
    )


def test_strategy_evaluation_config_loads_base_overrides(tmp_path: Path) -> None:
    base_config = tmp_path / "strategy_params.yml"
    eval_config = tmp_path / "strategy_evaluation.yml"
    _write_base_params(base_config)
    _write_eval_config(
        eval_config,
        base_config,
        """
  - id: baseline
    version: strategy-params-v1-baseline
    label: 当前参数
    overrides: {}
  - id: tech050
    version: strategy-params-v1-tech050
    label: 提高技术权重
    overrides:
      signal:
        weights:
          technical: "0.50"
          market: "0.20"
  - id: stop070
    version: strategy-params-v1-stop070
    label: 放宽止损
    overrides:
      risk:
        stop_loss_pct: "0.07"
""",
    )

    config = load_strategy_evaluation_config(eval_config)

    assert [variant.id for variant in config.variants] == ["baseline", "tech050", "stop070"]
    assert config.variants[0].params.version == "strategy-params-v1-baseline"
    assert config.variants[1].params.signal.weights.technical == 0.50
    assert config.variants[1].params.signal.weights.market == 0.20
    assert config.variants[1].params.signal.weights.event == 0.20
    assert str(config.variants[2].params.risk.stop_loss_pct) == "0.07"


def test_strategy_evaluation_config_rejects_duplicates_and_unknown_fields(
    tmp_path: Path,
) -> None:
    base_config = tmp_path / "strategy_params.yml"
    _write_base_params(base_config)
    duplicate_config = tmp_path / "duplicate.yml"
    _write_eval_config(
        duplicate_config,
        base_config,
        """
  - id: baseline
    version: strategy-params-v1-baseline
    label: 当前参数
    overrides: {}
  - id: baseline
    version: strategy-params-v1-other
    label: 重复 ID
    overrides: {}
""",
    )

    with pytest.raises(ValueError, match="variant id 重复"):
        load_strategy_evaluation_config(duplicate_config)

    unknown_config = tmp_path / "unknown.yml"
    _write_eval_config(
        unknown_config,
        base_config,
        """
  - id: bad
    version: strategy-params-v1-bad
    label: 非法字段
    overrides:
      signal:
        weights:
          momentum: "0.40"
""",
    )

    with pytest.raises(ValueError, match="未知策略参数字段"):
        load_strategy_evaluation_config(unknown_config)


def test_caching_data_provider_reuses_values_and_failures() -> None:
    class CountingProvider(MockProvider):
        def __init__(self) -> None:
            super().__init__()
            self.calls: dict[str, int] = {"market": 0, "intraday": 0, "news": 0}

        def get_market_bars(self, trade_date: date, lookback_days: int = 30):  # type: ignore[no-untyped-def]
            self.calls["market"] += 1
            return super().get_market_bars(trade_date, lookback_days)

        def get_intraday_bars(self, trade_date: date, symbols: list[str], period: str = "1"):  # type: ignore[no-untyped-def]
            self.calls["intraday"] += 1
            return super().get_intraday_bars(trade_date, symbols, period)

        def get_news(self, trade_date: date):  # type: ignore[no-untyped-def]
            self.calls["news"] += 1
            raise DataProviderError("news source failed")

    provider = CountingProvider()
    cached = CachingDataProvider(provider)
    trade_date = date(2026, 4, 29)

    assert cached.get_market_bars(trade_date, 30)
    assert cached.get_market_bars(trade_date, 30)
    assert cached.get_intraday_bars(trade_date, ["510300"], "1")
    assert cached.get_intraday_bars(trade_date, ["510300"], "1")
    for _ in range(2):
        with pytest.raises(DataProviderError, match="news source failed"):
            cached.get_news(trade_date)

    assert provider.calls == {"market": 1, "intraday": 1, "news": 1}


def test_strategy_evaluation_runner_runs_variants_and_writes_summary(
    tmp_path: Path,
) -> None:
    base_config = tmp_path / "strategy_params.yml"
    eval_config = tmp_path / "strategy_evaluation.yml"
    _write_base_params(base_config)
    _write_eval_config(
        eval_config,
        base_config,
        """
  - id: baseline
    version: strategy-params-v1-baseline
    label: 当前参数
    overrides: {}
  - id: fast-exit
    version: strategy-params-v1-fast-exit
    label: 快速退出
    overrides:
      risk:
        min_holding_trade_days: 1
        max_holding_trade_days: 2
""",
    )
    config = load_strategy_evaluation_config(eval_config)
    repository = InMemoryRepository()
    runner = StrategyEvaluationRunner(
        provider=CachingDataProvider(MockProvider()),
        llm_client=MockLLMClient(),
        report_root=tmp_path / "reports",
        repository=repository,
        strategy_config=config,
        provider_name="mock",
        required_data_sources=set(),
        today=date(2026, 5, 1),
    )

    result = runner.run(
        evaluation_id="eval-smoke",
        start_date=date(2026, 4, 27),
        end_date=date(2026, 5, 1),
    )

    assert result.success is True
    assert result.payload["evaluation_id"] == "eval-smoke"
    assert result.payload["start_date"] == "2026-04-27"
    assert result.payload["end_date"] == "2026-05-01"
    assert [item["backtest_id"] for item in result.payload["variants"]] == [
        "eval-smoke-baseline",
        "eval-smoke-fast-exit",
    ]
    fast_exit = result.payload["variants"][1]
    assert fast_exit["attempted_days"] == 5
    assert fast_exit["signal_count"] > 0
    assert fast_exit["order_count"] > 0
    assert fast_exit["closed_trade_count"] >= 1
    assert fast_exit["open_position_count"] >= 0
    assert fast_exit["max_drawdown"] >= 0
    assert fast_exit["signal_hit_rate"] == 0
    assert (tmp_path / "reports" / "eval-smoke" / "strategy-evaluation.md").exists()

    pipeline_runs = repository.records_for("pipeline_runs")
    assert {
        row["payload"]["backtest_id"]
        for row in pipeline_runs
        if row["payload"]["stage"] == "backtest"
    } == {"eval-smoke-baseline", "eval-smoke-fast-exit"}
    assert pipeline_runs[-1]["payload"]["stage"] == "strategy_evaluation"
    assert pipeline_runs[-1]["payload"]["status"] == "success"
    assert repository.records[-1]["artifact_type"] == "strategy_evaluation"


def test_strategy_evaluation_runner_uses_latest_10_trade_days_by_default(
    tmp_path: Path,
) -> None:
    base_config = tmp_path / "strategy_params.yml"
    eval_config = tmp_path / "strategy_evaluation.yml"
    _write_base_params(base_config)
    _write_eval_config(
        eval_config,
        base_config,
        """
  - id: baseline
    version: strategy-params-v1-baseline
    label: 当前参数
    overrides: {}
""",
    )
    repository = InMemoryRepository()
    runner = StrategyEvaluationRunner(
        provider=CachingDataProvider(MockProvider()),
        llm_client=MockLLMClient(),
        report_root=tmp_path / "reports",
        repository=repository,
        strategy_config=load_strategy_evaluation_config(eval_config),
        provider_name="mock",
        required_data_sources=set(),
        today=date(2026, 1, 15),
    )

    result = runner.run(evaluation_id="eval-default-window")

    assert result.payload["start_date"] == "2026-01-06"
    assert result.payload["end_date"] == "2026-01-15"
    assert result.payload["variants"][0]["attempted_days"] == 10


def test_strategy_evaluation_runner_counts_failed_days(tmp_path: Path) -> None:
    class OneDayBrokenProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30):  # type: ignore[no-untyped-def]
            if trade_date == date(2026, 4, 28):
                raise DataProviderError("行情接口失败")
            return super().get_market_bars(trade_date, lookback_days)

    base_config = tmp_path / "strategy_params.yml"
    eval_config = tmp_path / "strategy_evaluation.yml"
    _write_base_params(base_config)
    _write_eval_config(
        eval_config,
        base_config,
        """
  - id: baseline
    version: strategy-params-v1-baseline
    label: 当前参数
    overrides: {}
""",
    )
    repository = InMemoryRepository()
    runner = StrategyEvaluationRunner(
        provider=CachingDataProvider(OneDayBrokenProvider()),
        llm_client=MockLLMClient(),
        report_root=tmp_path / "reports",
        repository=repository,
        strategy_config=load_strategy_evaluation_config(eval_config),
        provider_name="mock",
        required_data_sources={"market_bars"},
        today=date(2026, 5, 1),
    )

    result = runner.run(
        evaluation_id="eval-failure",
        start_date=date(2026, 4, 27),
        end_date=date(2026, 4, 29),
    )

    variant = result.payload["variants"][0]
    assert variant["attempted_days"] == 3
    assert variant["failed_days"] == 1
    assert variant["data_quality_failure_rate"] == 1 / 3
    assert variant["source_failure_rate"] > 0

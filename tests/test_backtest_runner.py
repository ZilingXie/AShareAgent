from __future__ import annotations

from datetime import date
from pathlib import Path

from ashare_agent.agents.strategy_params_agent import StrategyParamsAgent
from ashare_agent.backtest import BacktestRunner
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.base import DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository


def _strategy_params(tmp_path: Path):
    config_path = tmp_path / "strategy_params.yml"
    config_path.write_text(
        """
version: "backtest-signal-v1"
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
  max_daily_signals: 2
  weights:
    technical: "0.45"
    market: "0.25"
    event: "0.20"
    risk_penalty: "0.10"
""",
        encoding="utf-8",
    )
    return StrategyParamsAgent(config_path).load()


def test_backtest_runner_replays_trade_days_with_backtest_scope(tmp_path: Path) -> None:
    repository = InMemoryRepository()
    runner = BacktestRunner(
        provider=MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
        strategy_params=_strategy_params(tmp_path),
        provider_name="mock",
        required_data_sources=set(),
    )

    result = runner.run(
        start_date=date(2026, 4, 27),
        end_date=date(2026, 4, 28),
        backtest_id="bt-signal-v1",
    )

    assert result.success is True
    assert result.payload["attempted_days"] == 2
    assert result.payload["succeeded_days"] == 2
    assert result.payload["failed_days"] == 0
    pipeline_runs = repository.records_for("pipeline_runs")
    assert [row["payload"]["stage"] for row in pipeline_runs] == [
        "pre_market",
        "post_market_review",
        "pre_market",
        "post_market_review",
        "backtest",
    ]
    assert {row["payload"]["backtest_id"] for row in pipeline_runs} == {"bt-signal-v1"}
    assert {row["payload"]["run_mode"] for row in pipeline_runs} == {"backtest"}
    assert pipeline_runs[-1]["payload"]["strategy_params_version"] == "backtest-signal-v1"


def test_backtest_runner_records_failed_day_and_continues(tmp_path: Path) -> None:
    class OneDayBrokenProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30):  # type: ignore[no-untyped-def]
            if trade_date == date(2026, 4, 27):
                raise DataProviderError("行情接口失败")
            return super().get_market_bars(trade_date, lookback_days)

    repository = InMemoryRepository()
    runner = BacktestRunner(
        provider=OneDayBrokenProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repository,
        strategy_params=_strategy_params(tmp_path),
        provider_name="mock",
        required_data_sources={"market_bars"},
    )

    result = runner.run(
        start_date=date(2026, 4, 27),
        end_date=date(2026, 4, 28),
        backtest_id="bt-with-failure",
    )

    assert result.success is False
    assert result.payload["attempted_days"] == 2
    assert result.payload["succeeded_days"] == 1
    assert result.payload["failed_days"] == 1
    assert result.payload["failures"][0]["trade_date"] == "2026-04-27"
    assert "行情接口失败" in result.payload["failures"][0]["reason"]
    pipeline_runs = repository.records_for("pipeline_runs")
    assert any(
        row["payload"]["stage"] == "pre_market" and row["payload"]["status"] == "failed"
        for row in pipeline_runs
    )
    assert pipeline_runs[-1]["payload"]["stage"] == "backtest"
    assert pipeline_runs[-1]["payload"]["status"] == "failed"

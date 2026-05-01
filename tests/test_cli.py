from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ashare_agent.cli import app
from ashare_agent.domain import Asset
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository


def _write_strategy_params(path: Path, *, stop_loss_pct: str = "0.05") -> None:
    path.write_text(
        f"""
version: "cli-test-params"
risk:
  max_positions: 5
  target_position_pct: "0.10"
  min_cash: "100"
  max_daily_loss_pct: "0.02"
  stop_loss_pct: "{stop_loss_pct}"
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


def test_cli_pre_market_writes_markdown_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_database_urls: list[str] = []
    strategy_config = tmp_path / "strategy_params.yml"
    _write_strategy_params(strategy_config)

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()
            created_database_urls.append(database_url)

    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ASHARE_STRATEGY_PARAMS_CONFIG", str(strategy_config))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    monkeypatch.setattr("ashare_agent.cli.PostgresRepository", FakePostgresRepository)
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code == 0
    assert "盘前流程完成" in result.output
    assert created_database_urls == ["postgresql+psycopg://test:test@localhost:5432/ashare"]
    assert (tmp_path / "2026-04-29" / "pre-market.md").exists()


def test_cli_pre_market_requires_database_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code != 0
    assert "DATABASE_URL" in result.output
    assert "持久化 CLI" in result.output


def test_cli_pre_market_supports_akshare_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write_strategy_params(config_dir / "strategy_params.yml")
    (config_dir / "universe.yml").write_text(
        """
assets:
  - symbol: "510300"
    name: "沪深300ETF"
    asset_type: "ETF"
  - symbol: "600000"
    name: "浦发银行"
    asset_type: "STOCK"
    enabled: false
""",
        encoding="utf-8",
    )
    created_symbols: list[str] = []
    created_intraday_configs: list[dict[str, object]] = []

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()

    class FakeAKShareProvider(MockProvider):
        def __init__(
            self,
            assets: list[Asset],
            *,
            intraday_source: str,
            intraday_timeout_seconds: float,
            intraday_retry_attempts: int,
            intraday_retry_backoff_seconds: float,
        ) -> None:
            super().__init__(assets)
            created_symbols.extend(asset.symbol for asset in assets)
            created_intraday_configs.append(
                {
                    "intraday_source": intraday_source,
                    "intraday_timeout_seconds": intraday_timeout_seconds,
                    "intraday_retry_attempts": intraday_retry_attempts,
                    "intraday_retry_backoff_seconds": intraday_retry_backoff_seconds,
                }
            )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASHARE_PROVIDER", "akshare")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ASHARE_INTRADAY_SOURCE", "akshare_em,akshare_sina")
    monkeypatch.setenv("ASHARE_INTRADAY_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("ASHARE_INTRADAY_RETRY_ATTEMPTS", "5")
    monkeypatch.setenv("ASHARE_INTRADAY_RETRY_BACKOFF_SECONDS", "0.2")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    monkeypatch.setattr("ashare_agent.cli.PostgresRepository", FakePostgresRepository)
    monkeypatch.setattr("ashare_agent.cli.AKShareProvider", FakeAKShareProvider, raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code == 0
    assert created_symbols == ["510300"]
    assert created_intraday_configs == [
        {
            "intraday_source": "akshare_em,akshare_sina",
            "intraday_timeout_seconds": 4.0,
            "intraday_retry_attempts": 5,
            "intraday_retry_backoff_seconds": 0.2,
        }
    ]


def test_cli_rejects_unknown_intraday_source_for_akshare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    _write_strategy_params(config_dir / "strategy_params.yml")
    (config_dir / "universe.yml").write_text(
        """
assets:
  - symbol: "510300"
    name: "沪深300ETF"
    asset_type: "ETF"
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASHARE_PROVIDER", "akshare")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_INTRADAY_SOURCE", "unknown")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code != 0
    assert "未知 ASHARE_INTRADAY_SOURCE" in result.output


def test_cli_strategy_params_config_env_controls_pipeline_params(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_repositories: list[InMemoryRepository] = []
    strategy_config = tmp_path / "custom_strategy_params.yml"
    _write_strategy_params(strategy_config, stop_loss_pct="0.11")

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()
            created_repositories.append(self)

    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ASHARE_STRATEGY_PARAMS_CONFIG", str(strategy_config))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    monkeypatch.setattr("ashare_agent.cli.PostgresRepository", FakePostgresRepository)
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code == 0
    run_payload = created_repositories[0].records_for("pipeline_runs")[-1]["payload"]
    assert run_payload["strategy_params_version"] == "cli-test-params"
    assert run_payload["strategy_params_snapshot"]["risk"]["stop_loss_pct"] == "0.11"


def test_cli_daily_run_skips_strategy_stages_on_non_trade_date(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_repositories: list[InMemoryRepository] = []
    strategy_config = tmp_path / "strategy_params.yml"
    _write_strategy_params(strategy_config)

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()
            created_repositories.append(self)

    class NonTradeProvider(MockProvider):
        def get_trade_calendar(self) -> list[date]:
            return [date(2026, 4, 27), date(2026, 4, 29)]

    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ASHARE_STRATEGY_PARAMS_CONFIG", str(strategy_config))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    monkeypatch.setattr("ashare_agent.cli.PostgresRepository", FakePostgresRepository)
    monkeypatch.setattr("ashare_agent.cli.MockProvider", NonTradeProvider)
    runner = CliRunner()

    result = runner.invoke(app, ["daily-run", "--trade-date", "2026-04-28"])

    assert result.exit_code == 0
    assert "非交易日" in result.output
    repository = created_repositories[0]
    assert repository.records_for("paper_orders") == []
    assert repository.records_for("data_reliability_reports")[-1]["payload"]["status"] == "skipped"
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "daily_run"
    assert latest_run["status"] == "skipped"


def test_cli_backtest_runs_with_mock_llm_and_backtest_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_repositories: list[InMemoryRepository] = []
    strategy_config = tmp_path / "strategy_params.yml"
    _write_strategy_params(strategy_config)

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()
            created_repositories.append(self)

    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "openai")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("ASHARE_STRATEGY_PARAMS_CONFIG", str(strategy_config))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    monkeypatch.setattr("ashare_agent.cli.PostgresRepository", FakePostgresRepository)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "backtest",
            "--start-date",
            "2026-04-27",
            "--end-date",
            "2026-04-28",
            "--backtest-id",
            "cli-bt-v1",
        ],
    )

    assert result.exit_code == 0
    assert "回放完成" in result.output
    pipeline_runs = created_repositories[0].records_for("pipeline_runs")
    assert pipeline_runs[-1]["payload"]["stage"] == "backtest"
    assert {row["payload"]["backtest_id"] for row in pipeline_runs} == {"cli-bt-v1"}
    assert {row["payload"]["run_mode"] for row in pipeline_runs} == {"backtest"}


def test_cli_strategy_evaluate_runs_variants_with_mock_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_repositories: list[InMemoryRepository] = []
    strategy_config = tmp_path / "strategy_params.yml"
    evaluation_config = tmp_path / "strategy_evaluation.yml"
    _write_strategy_params(strategy_config)
    evaluation_config.write_text(
        f"""
base_config: {strategy_config.as_posix()}
variants:
  - id: baseline
    version: cli-test-baseline
    label: 当前参数
    overrides: {{}}
""",
        encoding="utf-8",
    )

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()
            created_repositories.append(self)

    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "openai")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path / "reports"))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    monkeypatch.setattr("ashare_agent.cli.PostgresRepository", FakePostgresRepository)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "strategy-evaluate",
            "--config",
            str(evaluation_config),
            "--evaluation-id",
            "cli-eval",
            "--start-date",
            "2026-04-27",
            "--end-date",
            "2026-04-28",
        ],
    )

    assert result.exit_code == 0
    assert "策略评估完成" in result.output
    repository = created_repositories[0]
    assert repository.records_for("pipeline_runs")[-1]["payload"]["stage"] == (
        "strategy_evaluation"
    )
    assert repository.records_for("pipeline_runs")[-1]["payload"]["evaluation_id"] == "cli-eval"
    assert (tmp_path / "reports" / "cli-eval" / "strategy-evaluation.md").exists()


def test_cli_strategy_evaluate_requires_sina_fallback_for_akshare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    strategy_config = config_dir / "strategy_params.yml"
    evaluation_config = config_dir / "strategy_evaluation.yml"
    _write_strategy_params(strategy_config)
    evaluation_config.write_text(
        f"""
base_config: {strategy_config.as_posix()}
variants:
  - id: baseline
    version: cli-test-baseline
    label: 当前参数
    overrides: {{}}
""",
        encoding="utf-8",
    )
    (config_dir / "universe.yml").write_text(
        """
assets:
  - symbol: "510300"
    name: "沪深300ETF"
    asset_type: "ETF"
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASHARE_PROVIDER", "akshare")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_INTRADAY_SOURCE", "akshare_em")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "strategy-evaluate",
            "--config",
            str(evaluation_config),
            "--evaluation-id",
            "cli-eval",
        ],
    )

    assert result.exit_code != 0
    assert "akshare_sina" in result.output


def test_cli_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASHARE_PROVIDER", "unknown")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/ashare")
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code != 0
    assert "未知 ASHARE_PROVIDER" in result.output


def test_cli_rejects_invalid_trade_date() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "bad-date"])

    assert result.exit_code != 0
    assert "日期格式必须是 YYYY-MM-DD" in result.output

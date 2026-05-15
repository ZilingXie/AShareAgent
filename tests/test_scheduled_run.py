from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ashare_agent.cli import app, resolve_scheduled_trade_date
from ashare_agent.domain import MarketBar
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.pipeline import ASharePipeline
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository
from ashare_agent.scheduled import ScheduledRunAgent


class NonTradeProvider(MockProvider):
    def get_trade_calendar(self) -> list[date]:
        return [date(2026, 4, 27), date(2026, 4, 29)]


def _scheduled_agent(
    tmp_path: Path,
    *,
    provider: MockProvider | None = None,
    repository: InMemoryRepository | None = None,
) -> tuple[ScheduledRunAgent, InMemoryRepository]:
    repo = repository or InMemoryRepository()
    pipeline = ASharePipeline(
        provider=provider or MockProvider(),
        llm_client=MockLLMClient(),
        report_root=tmp_path,
        repository=repo,
    )
    return ScheduledRunAgent(
        pipeline=pipeline,
        provider_name="mock",
        llm_provider="mock",
    ), repo


def test_morning_collect_persists_sources_without_signals_or_orders(tmp_path: Path) -> None:
    agent, repository = _scheduled_agent(tmp_path)

    result = agent.run(slot="morning_collect", trade_date=date(2026, 4, 29))

    assert result.success is True
    assert result.payload["slot"] == "morning_collect"
    assert result.payload["status"] == "success"
    assert result.payload["real_trading"] is False
    assert (tmp_path / "2026-04-29" / "morning-collect.md").exists()
    assert repository.records_for("raw_source_snapshots")
    assert repository.records_for("market_bars")
    assert repository.records_for("signals") == []
    assert repository.records_for("paper_orders") == []
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "morning_collect"
    assert latest_run["status"] == "success"


def test_scheduled_slot_skips_non_trade_date_without_strategy_side_effects(
    tmp_path: Path,
) -> None:
    agent, repository = _scheduled_agent(tmp_path, provider=NonTradeProvider())

    result = agent.run(slot="intraday_decision", trade_date=date(2026, 4, 28))

    assert result.success is True
    assert result.payload["status"] == "skipped"
    assert "非交易日" in result.payload["skipped_reason"]
    assert repository.records_for("signals") == []
    assert repository.records_for("paper_orders") == []
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "intraday_decision"
    assert latest_run["status"] == "skipped"


def test_call_auction_slot_is_disabled_stub(tmp_path: Path) -> None:
    agent, repository = _scheduled_agent(tmp_path)

    result = agent.run(slot="call_auction", trade_date=date(2026, 4, 29))

    assert result.success is True
    assert result.payload["status"] == "skipped"
    assert result.payload["disabled"] is True
    assert "集合竞价" in result.payload["skipped_reason"]
    assert repository.records_for("paper_orders") == []
    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "call_auction"
    assert latest_run["status"] == "skipped"
    assert latest_run["disabled"] is True


def test_pre_market_brief_runs_pre_market_and_writes_structured_brief(
    tmp_path: Path,
) -> None:
    agent, repository = _scheduled_agent(tmp_path)

    result = agent.run(slot="pre_market_brief", trade_date=date(2026, 4, 29))

    assert result.success is True
    assert result.payload["slot"] == "pre_market_brief"
    assert result.payload["underlying_stage"] == "pre_market"
    assert result.payload["underlying_run_id"]
    brief_path = tmp_path / "2026-04-29" / "pre-market-brief.md"
    assert result.payload["report_path"] == str(brief_path)
    content = brief_path.read_text(encoding="utf-8")
    assert "# A 股 ETF 盘前简报" in content
    assert "## 1. 市场状态" in content
    assert "## 2. 今日观察 ETF" in content
    assert "## 3. 今日模拟交易结论" in content
    assert "## 4. 数据质量摘要" in content
    assert repository.records_for("paper_orders") == []
    stages = [row["payload"]["stage"] for row in repository.records_for("pipeline_runs")]
    assert "pre_market" in stages
    assert stages[-1] == "pre_market_brief"


def test_intraday_decision_executes_after_pre_market_and_is_idempotent(
    tmp_path: Path,
) -> None:
    agent, repository = _scheduled_agent(tmp_path)
    trade_date = date(2026, 4, 29)

    agent.run(slot="pre_market_brief", trade_date=trade_date)
    first = agent.run(slot="intraday_decision", trade_date=trade_date)
    first_order_count = len(repository.records_for("paper_orders"))
    second = agent.run(slot="intraday_decision", trade_date=trade_date)

    assert first.success is True
    assert second.success is True
    assert first_order_count > 0
    assert len(repository.records_for("paper_orders")) == first_order_count
    assert first.payload["underlying_stage"] == "intraday_watch"
    assert first.payload["order_count"] == first_order_count
    assert second.payload["order_count"] == 0
    assert (tmp_path / "2026-04-29" / "intraday-decision.md").exists()
    assert repository.records_for("paper_orders")[-1]["payload"]["is_real_trade"] is False


def test_post_market_brief_does_not_create_new_orders(tmp_path: Path) -> None:
    agent, repository = _scheduled_agent(tmp_path)
    trade_date = date(2026, 4, 29)

    agent.run(slot="pre_market_brief", trade_date=trade_date)
    agent.run(slot="intraday_decision", trade_date=trade_date)
    order_count_before_review = len(repository.records_for("paper_orders"))
    result = agent.run(slot="post_market_brief", trade_date=trade_date)

    assert result.success is True
    assert result.payload["underlying_stage"] == "post_market_review"
    assert result.payload["new_order_count"] == 0
    assert len(repository.records_for("paper_orders")) == order_count_before_review
    content = (tmp_path / "2026-04-29" / "post-market-brief.md").read_text(encoding="utf-8")
    assert "# A 股 ETF 收盘复盘简报" in content
    assert "## 1. 账户变化" in content
    assert "## 2. 今日模拟订单" in content
    assert "## 3. 当前持仓" in content
    assert "## 4. 信号与风控回顾" in content
    assert "## 5. 数据质量摘要" in content
    assert "## 6. 次日观察点" in content


def test_close_collect_requires_current_day_market_quality(tmp_path: Path) -> None:
    class MissingCurrentDailyBarProvider(MockProvider):
        def get_market_bars(self, trade_date: date, lookback_days: int = 30) -> list[MarketBar]:
            return [
                bar
                for bar in super().get_market_bars(trade_date, lookback_days)
                if bar.trade_date <= trade_date - timedelta(days=1)
            ]

    agent, repository = _scheduled_agent(tmp_path, provider=MissingCurrentDailyBarProvider())

    try:
        agent.run(slot="close_collect", trade_date=date(2026, 5, 6))
    except Exception as exc:
        assert "数据质量检查失败" in str(exc)
    else:
        raise AssertionError("close_collect 缺少当日完整日线时必须失败")

    latest_run = repository.records_for("pipeline_runs")[-1]["payload"]
    assert latest_run["stage"] == "close_collect"
    assert latest_run["status"] == "failed"
    assert latest_run["slot"] == "close_collect"
    assert latest_run["provider"] == "mock"
    assert latest_run["llm_provider"] == "mock"
    assert latest_run["real_trading"] is False


def test_cli_scheduled_run_invokes_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_repositories: list[InMemoryRepository] = []
    strategy_config = tmp_path / "strategy_params.yml"
    strategy_config.write_text(
        """
version: "scheduled-cli-test"
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

    result = CliRunner().invoke(
        app,
        [
            "scheduled-run",
            "--slot",
            "morning_collect",
            "--trade-date",
            "2026-04-29",
        ],
    )

    assert result.exit_code == 0
    assert "定时任务完成: morning_collect" in result.output
    assert created_repositories[0].records_for("pipeline_runs")[-1]["payload"]["stage"] == (
        "morning_collect"
    )


def test_cli_scheduled_run_resolves_previous_trade_date_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_repositories: list[InMemoryRepository] = []
    strategy_config = tmp_path / "strategy_params.yml"
    strategy_config.write_text(
        """
version: "scheduled-cli-test"
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
    monkeypatch.setattr("ashare_agent.cli._beijing_today", lambda: date(2026, 5, 15))

    result = CliRunner().invoke(
        app,
        [
            "scheduled-run",
            "--slot",
            "close_collect",
            "--trade-date",
            "previous-trade-date",
        ],
    )

    assert result.exit_code == 0
    latest_run = created_repositories[0].records_for("pipeline_runs")[-1]
    assert latest_run["trade_date"] == date(2026, 5, 14)
    assert latest_run["payload"]["stage"] == "close_collect"


def test_previous_trade_date_token_returns_today_when_today_is_not_trade_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HolidayProvider(MockProvider):
        def get_trade_calendar(self) -> list[date]:
            return [date(2026, 5, 14)]

    monkeypatch.setattr("ashare_agent.cli._beijing_today", lambda: date(2026, 5, 15))

    assert resolve_scheduled_trade_date("previous-trade-date", HolidayProvider()) == date(
        2026,
        5,
        15,
    )

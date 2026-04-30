from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ashare_agent.cli import app
from ashare_agent.repository import InMemoryRepository


def test_cli_pre_market_writes_markdown_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_database_urls: list[str] = []

    class FakePostgresRepository(InMemoryRepository):
        def __init__(self, database_url: str) -> None:
            super().__init__()
            created_database_urls.append(database_url)

    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path))
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


def test_cli_rejects_invalid_trade_date() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "bad-date"])

    assert result.exit_code != 0
    assert "日期格式必须是 YYYY-MM-DD" in result.output

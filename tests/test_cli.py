from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ashare_agent.cli import app


def test_cli_pre_market_writes_markdown_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASHARE_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASHARE_REPORT_ROOT", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "2026-04-29"])

    assert result.exit_code == 0
    assert "盘前流程完成" in result.output
    assert (tmp_path / "2026-04-29" / "pre-market.md").exists()


def test_cli_rejects_invalid_trade_date() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["pre-market", "--trade-date", "bad-date"])

    assert result.exit_code != 0
    assert "日期格式必须是 YYYY-MM-DD" in result.output

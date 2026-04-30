from __future__ import annotations

from pathlib import Path

from ashare_agent.reports import MarkdownTable, write_markdown_report


def test_write_markdown_report_renders_markdown_tables(tmp_path: Path) -> None:
    path = write_markdown_report(
        tmp_path,
        "2026-04-29",
        "strategy-experiment.md",
        {
            "模拟订单": MarkdownTable(
                headers=["side", "symbol", "reason"],
                rows=[
                    ["sell", "510300", "趋势|走弱卖出"],
                    ["buy", "159915", ""],
                ],
            )
        },
    )

    content = path.read_text(encoding="utf-8")

    assert "| side | symbol | reason |" in content
    assert "| --- | --- | --- |" in content
    assert "| sell | 510300 | 趋势\\|走弱卖出 |" in content
    assert "| buy | 159915 | - |" in content

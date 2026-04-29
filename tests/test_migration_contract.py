from __future__ import annotations

from pathlib import Path


def test_initial_migration_creates_schema_without_destructive_operations() -> None:
    migration = Path("migrations/versions/0001_initial_schema.py")

    text = migration.read_text(encoding="utf-8")

    assert "ashare_agent" in text
    assert "create_table" in text
    assert "drop_table" not in text
    assert "drop_schema" not in text


def test_initial_migration_defines_core_table_groups() -> None:
    text = Path("migrations/versions/0001_initial_schema.py").read_text(encoding="utf-8")
    expected_tables = {
        "pipeline_runs",
        "universe_assets",
        "raw_source_snapshots",
        "market_bars",
        "announcements",
        "news_items",
        "policy_items",
        "industry_snapshots",
        "technical_indicators",
        "llm_analyses",
        "watchlist_candidates",
        "signals",
        "risk_decisions",
        "paper_orders",
        "paper_positions",
        "portfolio_snapshots",
        "review_reports",
    }

    for table in expected_tables:
        assert f'"{table}"' in text

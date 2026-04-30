from __future__ import annotations

import re
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


def test_data_quality_migration_adds_payload_table_without_destructive_operations() -> None:
    migration = Path("migrations/versions/0002_data_quality_reports.py")

    text = migration.read_text(encoding="utf-8")

    assert 'revision = "0002_data_quality_reports"' in text
    assert 'down_revision = "0001_initial_schema"' in text
    assert '"data_quality_reports"' in text
    assert "create_table" in text
    assert "drop_table" not in text
    assert "drop_schema" not in text


def test_initial_migration_does_not_create_trading_calendar_table() -> None:
    text = Path("migrations/versions/0001_initial_schema.py").read_text(encoding="utf-8")

    assert '"trading_calendar"' not in text


def test_alembic_version_table_is_isolated_in_project_schema() -> None:
    text = Path("migrations/env.py").read_text(encoding="utf-8")

    assert 'PROJECT_SCHEMA = "ashare_agent"' in text
    assert "version_table_schema=PROJECT_SCHEMA" in text


def test_alembic_env_creates_project_schema_before_version_table() -> None:
    text = Path("migrations/env.py").read_text(encoding="utf-8")

    assert "CreateSchema" in text
    assert 'if_not_exists=True' in text
    assert "_ensure_project_schema(connection)" in text


def test_alembic_env_stops_on_unknown_existing_project_schema() -> None:
    text = Path("migrations/env.py").read_text(encoding="utf-8")

    assert "information_schema.schemata" in text
    assert "information_schema.tables" in text
    assert "迁移状态不明" in text


def test_alembic_env_ends_schema_check_transaction_before_migrations() -> None:
    text = Path("migrations/env.py").read_text(encoding="utf-8")

    assert re.search(
        r"_ensure_project_schema\(connection\).*?connection\.commit\(\).*?context\.configure",
        text,
        flags=re.DOTALL,
    )

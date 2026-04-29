from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "ashare_agent"
CORE_TABLES = (
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
)


def _create_payload_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA, if_not_exists=True))
    for table_name in CORE_TABLES:
        _create_payload_table(table_name)
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("failure_reason", sa.Text()),
        schema=SCHEMA,
    )


def downgrade() -> None:
    # No destructive downgrade in v1. Keep project data intact unless a human runs manual cleanup.
    return None

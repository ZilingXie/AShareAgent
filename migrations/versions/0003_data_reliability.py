from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_data_reliability"
down_revision = "0002_data_quality_reports"
branch_labels = None
depends_on = None

SCHEMA = "ashare_agent"


def upgrade() -> None:
    op.create_table(
        "trading_calendar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column("is_trade_date", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("calendar_date", "source", name="uq_trading_calendar_date_source"),
        schema=SCHEMA,
    )
    op.create_table(
        "data_reliability_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )


def downgrade() -> None:
    # No destructive downgrade in v1. Keep project data intact unless a human runs manual cleanup.
    return None

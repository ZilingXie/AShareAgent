from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_data_quality_reports"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

SCHEMA = "ashare_agent"


def upgrade() -> None:
    op.create_table(
        "data_quality_reports",
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

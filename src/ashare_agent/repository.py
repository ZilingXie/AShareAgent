from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
)
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _jsonable(item) for key, item in mapping.items()}
    if isinstance(value, list):
        values = cast(list[object], value)
        return [_jsonable(item) for item in values]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


class InMemoryRepository:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def save_artifact(self, trade_date: date, artifact_type: str, payload: dict[str, Any]) -> None:
        self.records.append(
            {
                "trade_date": trade_date,
                "artifact_type": artifact_type,
                "payload": _jsonable(payload),
            }
        )


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url)
        self.metadata = MetaData(schema="ashare_agent")
        self.artifacts = Table(
            "artifacts",
            self.metadata,
            # Schema is created by Alembic; repository does not auto-migrate.
            autoload_with=self.engine,
        )

    @classmethod
    def from_engine(cls, engine: Engine) -> PostgresRepository:
        instance = cls.__new__(cls)
        instance.engine = engine
        instance.metadata = MetaData(schema="ashare_agent")
        instance.artifacts = Table(
            "artifacts",
            instance.metadata,
            autoload_with=engine,
        )
        return instance

    def save_artifact(self, trade_date: date, artifact_type: str, payload: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.artifacts).values(
                    trade_date=trade_date,
                    artifact_type=artifact_type,
                    payload=_jsonable(payload),
                )
            )


metadata = MetaData(schema="ashare_agent")
artifacts_table = Table(
    "artifacts",
    metadata,
    # Definitions here mirror migration for metadata consumers.
    Column("id", Integer, primary_key=True),
    Column("trade_date", Date, nullable=False),
    Column("artifact_type", String(80), nullable=False),
    Column("payload", JSON, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
    Column("failure_reason", Text),
)

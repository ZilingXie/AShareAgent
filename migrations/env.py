from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, schema, text
from sqlalchemy.engine import Connection

from ashare_agent.repository import metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata
PROJECT_SCHEMA = "ashare_agent"


def _schema_exists(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text(
                """
                select exists (
                    select 1
                    from information_schema.schemata
                    where schema_name = :schema_name
                )
                """
            ),
            {"schema_name": PROJECT_SCHEMA},
        ).scalar_one()
    )


def _version_table_exists(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text(
                """
                select exists (
                    select 1
                    from information_schema.tables
                    where table_schema = :schema_name
                    and table_name = 'alembic_version'
                )
                """
            ),
            {"schema_name": PROJECT_SCHEMA},
        ).scalar_one()
    )


def _ensure_project_schema(connection: Connection) -> None:
    if _schema_exists(connection):
        if not _version_table_exists(connection):
            raise RuntimeError(
                "ashare_agent schema 已存在但缺少 ashare_agent.alembic_version，"
                "迁移状态不明；请先人工确认后再运行迁移"
            )
        return

    connection.execute(schema.CreateSchema(PROJECT_SCHEMA, if_not_exists=True))
    connection.commit()


def run_migrations_offline() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 未设置")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=PROJECT_SCHEMA,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 未设置")
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _ensure_project_schema(connection)
        # SQLAlchemy 2 starts an implicit transaction for the schema/version
        # checks above. End it before Alembic opens the migration transaction,
        # otherwise the migration can be rolled back when the connection closes.
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=PROJECT_SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

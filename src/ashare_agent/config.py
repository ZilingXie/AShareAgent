from __future__ import annotations

import os
from pathlib import Path
from typing import cast

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from yaml import safe_load  # type: ignore[import-untyped]

from ashare_agent.domain import Asset, AssetType


class Settings(BaseSettings):
    provider: str = Field(default="mock", alias="ASHARE_PROVIDER")
    llm_provider: str = Field(default="mock", alias="ASHARE_LLM_PROVIDER")
    report_root: Path = Field(default=Path("reports"), alias="ASHARE_REPORT_ROOT")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    enable_deepseek: bool = Field(default=False, alias="ASHARE_ENABLE_DEEPSEEK")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-v4-pro", alias="DEEPSEEK_MODEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


def load_settings() -> Settings:
    return Settings()


def load_universe(path: Path) -> list[Asset]:
    raw_data = cast(object, safe_load(path.read_text(encoding="utf-8")))
    if not isinstance(raw_data, dict):
        raise ValueError("universe 配置必须是 YAML object")
    raw = cast(dict[str, object], raw_data)
    rows_data = raw.get("assets")
    if not isinstance(rows_data, list):
        raise ValueError("universe 配置必须包含 assets 列表")
    rows = cast(list[object], rows_data)

    assets: list[Asset] = []
    for row_data in rows:
        if not isinstance(row_data, dict):
            raise ValueError("assets 中每一项必须是 object")
        row = cast(dict[str, object], row_data)
        raw_asset_type = str(row.get("asset_type", "ETF"))
        if raw_asset_type not in {"ETF", "STOCK"}:
            raise ValueError(f"未知 asset_type: {raw_asset_type}")
        assets.append(
            Asset(
                symbol=str(row["symbol"]),
                name=str(row["name"]),
                asset_type=cast(AssetType, raw_asset_type),
                market=str(row.get("market", "A_SHARE")),
                enabled=bool(row.get("enabled", True)),
            )
        )
    return assets


def running_with_mock_provider() -> bool:
    return os.getenv("ASHARE_PROVIDER", "mock") == "mock"

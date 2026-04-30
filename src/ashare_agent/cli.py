from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from ashare_agent.agents.strategy_params_agent import StrategyParamsAgent
from ashare_agent.config import load_settings, load_universe
from ashare_agent.llm.factory import create_llm_client
from ashare_agent.pipeline import ASharePipeline
from ashare_agent.providers.akshare_provider import AKShareProvider
from ashare_agent.providers.base import DataProvider, DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import PostgresRepository

app = typer.Typer(no_args_is_help=True)


def _parse_trade_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("日期格式必须是 YYYY-MM-DD") from exc


def _build_provider(provider_name: str) -> tuple[DataProvider, set[str]]:
    normalized = provider_name.lower()
    if normalized == "mock":
        return MockProvider(), set()
    if normalized == "akshare":
        try:
            assets = load_universe(Path("configs/universe.yml"), enabled_only=True)
        except (FileNotFoundError, ValueError) as exc:
            raise typer.BadParameter(f"无法加载 akshare universe: {exc}") from exc
        return AKShareProvider(assets), {"universe", "market_bars", "trade_calendar"}
    raise typer.BadParameter(f"未知 ASHARE_PROVIDER: {provider_name}")


def _build_pipeline() -> ASharePipeline:
    settings = load_settings()
    if not settings.database_url:
        raise typer.BadParameter("持久化 CLI 需要 DATABASE_URL；请先配置 PostgreSQL 连接")
    provider, required_data_sources = _build_provider(settings.provider)
    try:
        strategy_params = StrategyParamsAgent(Path(settings.strategy_params_config)).load()
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(f"无法加载策略参数配置: {exc}") from exc
    return ASharePipeline(
        provider=provider,
        llm_client=create_llm_client(
            provider=settings.llm_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            deepseek_api_key=settings.deepseek_api_key,
            deepseek_model=settings.deepseek_model,
        ),
        report_root=Path(settings.report_root),
        repository=PostgresRepository(settings.database_url),
        strategy_params=strategy_params,
        required_data_sources=required_data_sources,
    )


@app.command()
def pre_market(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    try:
        result = _build_pipeline().run_pre_market(parsed_date)
    except DataProviderError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"盘前流程完成: {result.payload['report_path']}")


@app.command()
def intraday_watch(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    result = _build_pipeline().run_intraday_watch(parsed_date)
    typer.echo(f"盘中监控完成: {result.payload['report_path']}")


@app.command()
def post_market_review(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    try:
        result = _build_pipeline().run_post_market_review(parsed_date)
    except DataProviderError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"收盘复盘完成: {result.payload['report_path']}")


@app.command()
def daily_run(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    try:
        result = _build_pipeline().run_daily(parsed_date)
    except DataProviderError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.payload.get("skipped_reason"):
        typer.echo(f"每日流程跳过: {result.payload['skipped_reason']}")
        return
    typer.echo(f"每日流程完成: {parsed_date.isoformat()}")

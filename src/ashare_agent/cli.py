from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from ashare_agent.agents.strategy_params_agent import StrategyParams, StrategyParamsAgent
from ashare_agent.backtest import BacktestRunner
from ashare_agent.config import Settings, load_settings, load_universe
from ashare_agent.domain import now_utc
from ashare_agent.llm.factory import create_llm_client
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.pipeline import ASharePipeline
from ashare_agent.providers.akshare_provider import AKShareProvider
from ashare_agent.providers.base import DataProvider, DataProviderError
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import PostgresRepository
from ashare_agent.scheduled import SCHEDULED_RUN_SLOTS, ScheduledRunAgent
from ashare_agent.strategy_evaluation import (
    StrategyEvaluationRunner,
    load_strategy_evaluation_config,
)
from ashare_agent.strategy_insights import StrategyInsightRunner

app = typer.Typer(no_args_is_help=True)


def _parse_trade_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("日期格式必须是 YYYY-MM-DD") from exc


def _parse_optional_trade_date(value: str | None) -> date | None:
    if value is None:
        return None
    return _parse_trade_date(value)


def _build_provider(settings: Settings) -> tuple[DataProvider, set[str]]:
    provider_name = settings.provider
    normalized = provider_name.lower()
    if normalized == "mock":
        return MockProvider(), set()
    if normalized == "akshare":
        try:
            assets = load_universe(Path("configs/universe.yml"), enabled_only=True)
        except (FileNotFoundError, ValueError) as exc:
            raise typer.BadParameter(f"无法加载 akshare universe: {exc}") from exc
        try:
            provider = AKShareProvider(
                assets,
                intraday_source=settings.intraday_source,
                intraday_timeout_seconds=settings.intraday_timeout_seconds,
                intraday_retry_attempts=settings.intraday_retry_attempts,
                intraday_retry_backoff_seconds=settings.intraday_retry_backoff_seconds,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        return provider, {"universe", "market_bars", "trade_calendar"}
    raise typer.BadParameter(f"未知 ASHARE_PROVIDER: {provider_name}")


def _build_pipeline(settings: Settings | None = None) -> ASharePipeline:
    settings = settings or load_settings()
    if not settings.database_url:
        raise typer.BadParameter("持久化 CLI 需要 DATABASE_URL；请先配置 PostgreSQL 连接")
    provider, required_data_sources = _build_provider(settings)
    strategy_params = _load_strategy_params(settings.strategy_params_config)
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


def _load_strategy_params(settings_strategy_config: Path) -> StrategyParams:
    try:
        return StrategyParamsAgent(settings_strategy_config).load()
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(f"无法加载策略参数配置: {exc}") from exc


def _default_backtest_id(provider_name: str, start_date: date, end_date: date) -> str:
    timestamp = now_utc().strftime("%Y%m%d%H%M%S")
    return f"{provider_name.lower()}-{start_date.isoformat()}-{end_date.isoformat()}-{timestamp}"


def _require_sina_fallback_for_strategy_evaluation(settings: Settings) -> None:
    if settings.provider.lower() != "akshare":
        return
    sources = {item.strip() for item in settings.intraday_source.split(",") if item.strip()}
    if "akshare_sina" not in sources:
        raise typer.BadParameter(
            "strategy-evaluate 使用 akshare 时 "
            "ASHARE_INTRADAY_SOURCE 必须包含 akshare_sina"
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
    typer.echo(f"盘中模拟交易完成: {result.payload['report_path']}")


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


@app.command()
def scheduled_run(
    slot: Annotated[str, typer.Option(..., "--slot")],
    trade_date: str = typer.Option(..., "--trade-date"),
) -> None:
    parsed_date = _parse_trade_date(trade_date)
    if slot not in SCHEDULED_RUN_SLOTS:
        raise typer.BadParameter(
            f"未知 scheduled-run slot: {slot}; 可选值: {', '.join(SCHEDULED_RUN_SLOTS)}"
        )
    settings = load_settings()
    try:
        result = ScheduledRunAgent(
            pipeline=_build_pipeline(settings),
            provider_name=settings.provider.lower(),
            llm_provider=settings.llm_provider.lower(),
        ).run(slot=slot, trade_date=parsed_date)
    except (DataProviderError, RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if result.payload.get("status") == "skipped":
        typer.echo(f"定时任务跳过: {slot}, {result.payload.get('skipped_reason')}")
        return
    typer.echo(f"定时任务完成: {slot}, 报告 {result.payload.get('report_path', '-')}")


@app.command()
def backtest(
    start_date: str = typer.Option(..., "--start-date"),
    end_date: str = typer.Option(..., "--end-date"),
    backtest_id: str | None = typer.Option(None, "--backtest-id"),
) -> None:
    parsed_start = _parse_trade_date(start_date)
    parsed_end = _parse_trade_date(end_date)
    settings = load_settings()
    if not settings.database_url:
        raise typer.BadParameter("持久化 CLI 需要 DATABASE_URL；请先配置 PostgreSQL 连接")
    provider, required_data_sources = _build_provider(settings)
    strategy_params = _load_strategy_params(settings.strategy_params_config)
    resolved_backtest_id = backtest_id or _default_backtest_id(
        settings.provider,
        parsed_start,
        parsed_end,
    )
    runner = BacktestRunner(
        provider=provider,
        llm_client=MockLLMClient(),
        report_root=Path(settings.report_root),
        repository=PostgresRepository(settings.database_url),
        strategy_params=strategy_params,
        provider_name=settings.provider.lower(),
        required_data_sources=required_data_sources,
    )
    try:
        result = runner.run(
            start_date=parsed_start,
            end_date=parsed_end,
            backtest_id=resolved_backtest_id,
        )
    except (DataProviderError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        "回放完成: "
        f"{resolved_backtest_id}, "
        f"成功 {result.payload['succeeded_days']}/"
        f"{result.payload['attempted_days']}, "
        f"失败 {result.payload['failed_days']}"
    )


@app.command()
def strategy_evaluate(
    config: Annotated[Path, typer.Option(..., "--config")],
    evaluation_id: Annotated[str | None, typer.Option("--evaluation-id")] = None,
    start_date: Annotated[str | None, typer.Option("--start-date")] = None,
    end_date: Annotated[str | None, typer.Option("--end-date")] = None,
) -> None:
    settings = load_settings()
    if not settings.database_url:
        raise typer.BadParameter("持久化 CLI 需要 DATABASE_URL；请先配置 PostgreSQL 连接")
    _require_sina_fallback_for_strategy_evaluation(settings)
    try:
        strategy_config = load_strategy_evaluation_config(config)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(f"无法加载策略评估配置: {exc}") from exc
    provider, required_data_sources = _build_provider(settings)
    runner = StrategyEvaluationRunner(
        provider=provider,
        llm_client=MockLLMClient(),
        report_root=Path(settings.report_root),
        repository=PostgresRepository(settings.database_url),
        strategy_config=strategy_config,
        provider_name=settings.provider.lower(),
        required_data_sources=required_data_sources,
    )
    try:
        result = runner.run(
            evaluation_id=evaluation_id,
            start_date=_parse_optional_trade_date(start_date),
            end_date=_parse_optional_trade_date(end_date),
        )
    except (DataProviderError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        "策略评估完成: "
        f"{result.payload['evaluation_id']}, "
        f"报告 {result.payload['report_path']}"
    )


@app.command()
def strategy_insight(
    trade_date: Annotated[str, typer.Option(..., "--trade-date")],
    insight_id: Annotated[str | None, typer.Option("--insight-id")] = None,
) -> None:
    parsed_date = _parse_trade_date(trade_date)
    settings = load_settings()
    if not settings.database_url:
        raise typer.BadParameter("持久化 CLI 需要 DATABASE_URL；请先配置 PostgreSQL 连接")
    _require_sina_fallback_for_strategy_evaluation(settings)
    provider, required_data_sources = _build_provider(settings)
    strategy_params = _load_strategy_params(settings.strategy_params_config)
    runner = StrategyInsightRunner(
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
        provider_name=settings.provider.lower(),
        required_data_sources=required_data_sources,
    )
    try:
        result = runner.run(trade_date=parsed_date, insight_id=insight_id)
    except (DataProviderError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        "策略优化复盘完成: "
        f"{result.payload['insight_id']}, "
        f"报告 {result.payload['report_path']}"
    )

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from ashare_agent.config import load_settings
from ashare_agent.llm.factory import create_llm_client
from ashare_agent.pipeline import ASharePipeline
from ashare_agent.providers.mock import MockProvider

app = typer.Typer(no_args_is_help=True)


def _parse_trade_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("日期格式必须是 YYYY-MM-DD") from exc


def _build_pipeline() -> ASharePipeline:
    settings = load_settings()
    if settings.provider != "mock":
        raise typer.BadParameter(
            "第一版 CLI 默认只启用 mock provider；真实 AKShare 入口后续单独加外部标记"
        )
    return ASharePipeline(
        provider=MockProvider(),
        llm_client=create_llm_client(
            provider=settings.llm_provider,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            deepseek_api_key=settings.deepseek_api_key,
            deepseek_model=settings.deepseek_model,
        ),
        report_root=Path(settings.report_root),
    )


@app.command()
def pre_market(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    result = _build_pipeline().run_pre_market(parsed_date)
    typer.echo(f"盘前流程完成: {result.payload['report_path']}")


@app.command()
def intraday_watch(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    result = _build_pipeline().run_intraday_watch(parsed_date)
    typer.echo(f"盘中监控完成: {result.payload['report_path']}")


@app.command()
def post_market_review(trade_date: str = typer.Option(..., "--trade-date")) -> None:
    parsed_date = _parse_trade_date(trade_date)
    result = _build_pipeline().run_post_market_review(parsed_date)
    typer.echo(f"收盘复盘完成: {result.payload['report_path']}")

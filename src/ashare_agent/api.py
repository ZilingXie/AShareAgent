from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any, Protocol, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ashare_agent.config import load_settings
from ashare_agent.dashboard import (
    DashboardBacktest,
    DashboardDay,
    DashboardQueryService,
    DashboardRun,
    DashboardStrategyComparison,
    DashboardStrategyEvaluation,
    DashboardStrategyInsight,
    DashboardTrends,
)
from ashare_agent.repository import PostgresRepository


class DashboardService(Protocol):
    def list_runs(self, limit: int = 50) -> list[DashboardRun]: ...

    def day_summary(self, trade_date: date) -> DashboardDay: ...

    def trends(self, start_date: date, end_date: date) -> DashboardTrends: ...

    def list_backtests(self, limit: int = 50) -> list[DashboardBacktest]: ...

    def strategy_comparison(self, backtest_ids: list[str]) -> DashboardStrategyComparison: ...

    def list_strategy_evaluations(
        self,
        limit: int = 50,
    ) -> list[DashboardStrategyEvaluation]: ...

    def strategy_evaluation(
        self,
        evaluation_id: str,
    ) -> DashboardStrategyEvaluation | None: ...

    def list_strategy_insights(self, limit: int = 50) -> list[DashboardStrategyInsight]: ...

    def strategy_insight(self, insight_id: str) -> DashboardStrategyInsight | None: ...


DashboardServiceFactory = Callable[[], DashboardService]
JsonObject = dict[str, object]


def create_app(service_factory: DashboardServiceFactory | None = None) -> FastAPI:
    api = FastAPI(title="AShareAgent Dashboard API")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    factory = service_factory or _create_dashboard_service

    def service() -> DashboardService:
        try:
            return factory()
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @api.get("/api/health")
    def health() -> dict[str, str]:
        service()
        return {"status": "ok"}

    @api.get("/api/dashboard/runs")
    def dashboard_runs(limit: int = 50) -> dict[str, list[JsonObject]]:
        safe_limit = min(max(limit, 1), 200)
        return {"runs": [_dto(run) for run in service().list_runs(limit=safe_limit)]}

    @api.get("/api/dashboard/days/{trade_date}")
    def dashboard_day(trade_date: date) -> JsonObject:
        return _dto(service().day_summary(trade_date))

    @api.get("/api/dashboard/trends")
    def dashboard_trends(start_date: date, end_date: date) -> JsonObject:
        try:
            return _dto(service().trends(start_date, end_date))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/api/dashboard/backtests")
    def dashboard_backtests(limit: int = 50) -> dict[str, list[JsonObject]]:
        safe_limit = min(max(limit, 1), 200)
        return {"backtests": [_dto(item) for item in service().list_backtests(limit=safe_limit)]}

    @api.get("/api/dashboard/strategy-comparison")
    def dashboard_strategy_comparison(backtest_ids: str) -> JsonObject:
        ids = [item.strip() for item in backtest_ids.split(",") if item.strip()]
        return _dto(service().strategy_comparison(ids))

    @api.get("/api/dashboard/strategy-evaluations")
    def dashboard_strategy_evaluations(limit: int = 50) -> dict[str, list[JsonObject]]:
        safe_limit = min(max(limit, 1), 200)
        return {
            "strategy_evaluations": [
                _dto(item) for item in service().list_strategy_evaluations(limit=safe_limit)
            ]
        }

    @api.get("/api/dashboard/strategy-evaluations/{evaluation_id}")
    def dashboard_strategy_evaluation(evaluation_id: str) -> JsonObject:
        evaluation = service().strategy_evaluation(evaluation_id)
        if evaluation is None:
            raise HTTPException(
                status_code=404,
                detail=f"strategy evaluation 不存在: {evaluation_id}",
            )
        return _dto(evaluation)

    @api.get("/api/dashboard/strategy-insights")
    def dashboard_strategy_insights(limit: int = 50) -> dict[str, list[JsonObject]]:
        safe_limit = min(max(limit, 1), 200)
        return {
            "strategy_insights": [
                _dto(item) for item in service().list_strategy_insights(limit=safe_limit)
            ]
        }

    @api.get("/api/dashboard/strategy-insights/{insight_id}")
    def dashboard_strategy_insight(insight_id: str) -> JsonObject:
        insight = service().strategy_insight(insight_id)
        if insight is None:
            raise HTTPException(
                status_code=404,
                detail=f"strategy insight 不存在: {insight_id}",
            )
        return _dto(insight)

    _registered_routes = (
        health,
        dashboard_runs,
        dashboard_day,
        dashboard_trends,
        dashboard_backtests,
        dashboard_strategy_comparison,
        dashboard_strategy_evaluations,
        dashboard_strategy_evaluation,
        dashboard_strategy_insights,
        dashboard_strategy_insight,
    )
    return api


def _create_dashboard_service() -> DashboardQueryService:
    settings = load_settings()
    if not settings.database_url:
        raise RuntimeError("只读 dashboard API 需要 DATABASE_URL，不能使用内存兜底")
    return DashboardQueryService(PostgresRepository(settings.database_url))


def _dto(value: object) -> JsonObject:
    if not is_dataclass(value) or isinstance(value, type):
        raise TypeError("dashboard API 只能返回 dataclass DTO")
    return cast(JsonObject, asdict(cast(Any, value)))


app = create_app()

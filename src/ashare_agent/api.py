from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any, Protocol, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ashare_agent.config import load_settings
from ashare_agent.dashboard import DashboardDay, DashboardQueryService, DashboardRun
from ashare_agent.repository import PostgresRepository


class DashboardService(Protocol):
    def list_runs(self, limit: int = 50) -> list[DashboardRun]: ...

    def day_summary(self, trade_date: date) -> DashboardDay: ...


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

    _registered_routes = (health, dashboard_runs, dashboard_day)
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

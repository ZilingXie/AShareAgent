from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ashare_agent.api import create_app
from ashare_agent.dashboard import (
    DashboardBacktest,
    DashboardDay,
    DashboardQueryService,
    DashboardRun,
    DashboardStrategyComparison,
    DashboardStrategyComparisonItem,
    DashboardTrends,
)
from ashare_agent.domain import PipelineRunContext
from ashare_agent.repository import InMemoryRepository


class FakeDashboardService:
    def list_runs(self, limit: int = 50) -> list[DashboardRun]:
        return [
            DashboardRun(
                run_id="run-1",
                trade_date="2026-04-29",
                stage="pre_market",
                status="success",
                report_path="reports/2026-04-29/pre-market.md",
                failure_reason=None,
                created_at="2026-04-29T00:00:00+00:00",
            )
        ][:limit]

    def day_summary(self, trade_date: date) -> DashboardDay:
        return DashboardDay(trade_date=trade_date.isoformat(), runs=self.list_runs())

    def trends(self, start_date: date, end_date: date) -> DashboardTrends:
        return DashboardTrends(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            points=[],
            risk_reject_reasons={"接近涨停，不买入": 2},
        )

    def list_backtests(self, limit: int = 50) -> list[DashboardBacktest]:
        return [
            DashboardBacktest(
                backtest_id="bt-1",
                strategy_params_version="signal-v1",
                provider="mock",
                start_date="2026-04-27",
                end_date="2026-04-28",
                status="success",
                attempted_days=2,
                succeeded_days=2,
                failed_days=0,
                created_at="2026-04-28T00:00:00+00:00",
            )
        ][:limit]

    def strategy_comparison(self, backtest_ids: list[str]) -> DashboardStrategyComparison:
        return DashboardStrategyComparison(
            backtest_ids=backtest_ids,
            items=[
                DashboardStrategyComparisonItem(
                    backtest_id="bt-1",
                    strategy_params_version="signal-v1",
                    provider="mock",
                    start_date="2026-04-27",
                    end_date="2026-04-28",
                    attempted_days=2,
                    succeeded_days=2,
                    failed_days=0,
                    win_rate=1.0,
                    max_drawdown=0.05,
                    total_return=0.01,
                    risk_reject_rate=0.5,
                    data_quality_failure_rate=0.0,
                )
            ],
        )


def test_dashboard_api_returns_runs_and_day_summary() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    runs_response = client.get("/api/dashboard/runs?limit=5")
    day_response = client.get("/api/dashboard/days/2026-04-29")

    assert runs_response.status_code == 200
    assert runs_response.json()["runs"][0]["stage"] == "pre_market"
    assert day_response.status_code == 200
    assert day_response.json()["trade_date"] == "2026-04-29"
    assert day_response.json()["data_quality_reports"] == []
    assert day_response.json()["data_reliability_reports"] == []
    assert day_response.json()["trading_calendar"] is None


def test_dashboard_api_returns_range_trends() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    response = client.get("/api/dashboard/trends?start_date=2026-04-28&end_date=2026-04-30")

    assert response.status_code == 200
    assert response.json()["start_date"] == "2026-04-28"
    assert response.json()["end_date"] == "2026-04-30"
    assert response.json()["risk_reject_reasons"] == {"接近涨停，不买入": 2}


def test_dashboard_api_returns_backtests_and_strategy_comparison() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    backtests_response = client.get("/api/dashboard/backtests?limit=5")
    comparison_response = client.get("/api/dashboard/strategy-comparison?backtest_ids=bt-1,bt-2")

    assert backtests_response.status_code == 200
    assert backtests_response.json()["backtests"][0]["backtest_id"] == "bt-1"
    assert comparison_response.status_code == 200
    assert comparison_response.json()["backtest_ids"] == ["bt-1", "bt-2"]
    assert comparison_response.json()["items"][0]["strategy_params_version"] == "signal-v1"


def test_dashboard_api_returns_deduplicated_backtests_and_strategy_comparison() -> None:
    repository = InMemoryRepository()
    trade_date = date(2026, 4, 30)
    for run_id, version in [
        ("old-summary", "signal-old"),
        ("latest-summary", "signal-latest"),
    ]:
        repository.save_pipeline_run(
            PipelineRunContext(
                trade_date=trade_date,
                run_id=run_id,
                run_mode="backtest",
                backtest_id="bt-repeat",
            ),
            "backtest",
            "success",
            {
                "strategy_params_version": version,
                "provider": "mock",
                "start_date": "2026-04-27",
                "end_date": "2026-04-30",
                "attempted_days": 4,
                "succeeded_days": 4,
                "failed_days": 0,
            },
        )
    client = TestClient(create_app(service_factory=lambda: DashboardQueryService(repository)))

    backtests_response = client.get("/api/dashboard/backtests?limit=5")
    comparison_response = client.get(
        "/api/dashboard/strategy-comparison?backtest_ids=bt-repeat,bt-repeat"
    )

    assert backtests_response.status_code == 200
    backtests = backtests_response.json()["backtests"]
    assert [item["backtest_id"] for item in backtests] == ["bt-repeat"]
    assert backtests[0]["strategy_params_version"] == "signal-latest"
    assert comparison_response.status_code == 200
    assert comparison_response.json()["backtest_ids"] == ["bt-repeat"]
    assert [item["backtest_id"] for item in comparison_response.json()["items"]] == ["bt-repeat"]


def test_dashboard_api_fails_clearly_without_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    client = TestClient(create_app())

    response = client.get("/api/dashboard/runs")

    assert response.status_code == 500
    assert "DATABASE_URL" in response.json()["detail"]

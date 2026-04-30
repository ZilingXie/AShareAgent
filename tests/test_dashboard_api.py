from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ashare_agent.api import create_app
from ashare_agent.dashboard import DashboardDay, DashboardRun, DashboardTrends


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


def test_dashboard_api_returns_runs_and_day_summary() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    runs_response = client.get("/api/dashboard/runs?limit=5")
    day_response = client.get("/api/dashboard/days/2026-04-29")

    assert runs_response.status_code == 200
    assert runs_response.json()["runs"][0]["stage"] == "pre_market"
    assert day_response.status_code == 200
    assert day_response.json()["trade_date"] == "2026-04-29"
    assert day_response.json()["data_quality_reports"] == []


def test_dashboard_api_returns_range_trends() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    response = client.get("/api/dashboard/trends?start_date=2026-04-28&end_date=2026-04-30")

    assert response.status_code == 200
    assert response.json()["start_date"] == "2026-04-28"
    assert response.json()["end_date"] == "2026-04-30"
    assert response.json()["risk_reject_reasons"] == {"接近涨停，不买入": 2}


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

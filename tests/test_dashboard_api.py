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
    DashboardStrategyEvaluation,
    DashboardStrategyEvaluationRecommendation,
    DashboardStrategyEvaluationVariant,
    DashboardStrategyInsight,
    DashboardStrategyInsightExperiment,
    DashboardStrategyInsightHypothesis,
    DashboardStrategyInsightWindow,
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

    def list_strategy_evaluations(self, limit: int = 50) -> list[DashboardStrategyEvaluation]:
        return [self._strategy_evaluation()][:limit]

    def strategy_evaluation(self, evaluation_id: str) -> DashboardStrategyEvaluation | None:
        if evaluation_id != "eval-1":
            return None
        return self._strategy_evaluation()

    def list_strategy_insights(self, limit: int = 50) -> list[DashboardStrategyInsight]:
        return [self._strategy_insight()][:limit]

    def strategy_insight(self, insight_id: str) -> DashboardStrategyInsight | None:
        if insight_id != "insight-1":
            return None
        return self._strategy_insight()

    def _strategy_insight(self) -> DashboardStrategyInsight:
        return DashboardStrategyInsight(
            insight_id="insight-1",
            trade_date="2026-04-30",
            provider="mock",
            summary="近期信号偏少。",
            attribution=["风控拒绝较多"],
            manual_status="pending_review",
            report_path="reports/insight-1/strategy-insights.md",
            hypotheses=[
                DashboardStrategyInsightHypothesis(
                    area="signal.min_score",
                    direction="lower",
                    reason="近期信号偏少",
                    risk="可能增加低质量交易",
                )
            ],
            experiments=[
                DashboardStrategyInsightExperiment(
                    name="降低最低评分阈值",
                    param="signal.min_score",
                    candidate_value="0.50",
                    policy_status="approved",
                    policy_reason=None,
                    variant_id="llm-signal-min-score-050",
                    overrides={"signal": {"min_score": "0.50"}},
                )
            ],
            evaluation_windows=[
                DashboardStrategyInsightWindow(
                    window_trade_days=20,
                    evaluation_id="insight-1-20d",
                    report_path="reports/insight-1-20d/strategy-evaluation.md",
                    recommended_variant_ids=["llm-signal-min-score-050"],
                    passed_variant_ids=["llm-signal-min-score-050"],
                    failed_variant_reasons={},
                )
            ],
            recommended_variant_ids=["llm-signal-min-score-050"],
        )

    def _strategy_evaluation(self) -> DashboardStrategyEvaluation:
        return DashboardStrategyEvaluation(
            evaluation_id="eval-1",
            provider="mock",
            start_date="2026-04-27",
            end_date="2026-04-29",
            report_path="reports/eval-1/strategy-evaluation.md",
            variant_count=2,
            recommendation=DashboardStrategyEvaluationRecommendation(
                summary="未发现同时改善收益/命中率且不恶化回撤和失败率的参数组合",
                recommended_variant_ids=[],
            ),
            variants=[
                DashboardStrategyEvaluationVariant(
                    id="baseline",
                    label="当前参数",
                    version="params-baseline",
                    backtest_id="eval-1-baseline",
                    success=True,
                    attempted_days=3,
                    succeeded_days=3,
                    failed_days=0,
                    source_failure_rate=0.0,
                    data_quality_failure_rate=0.0,
                    signal_count=1,
                    risk_approved_count=1,
                    risk_rejected_count=0,
                    order_count=1,
                    execution_failed_count=0,
                    closed_trade_count=0,
                    signal_hit_count=0,
                    signal_hit_rate=0.0,
                    open_position_count=1,
                    holding_pnl="106.80",
                    total_return=0.0011,
                    max_drawdown=0.0,
                    is_recommended=False,
                    not_recommended_reasons=["基准参数，不参与推荐比较"],
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


def test_dashboard_api_returns_strategy_evaluations() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    list_response = client.get("/api/dashboard/strategy-evaluations?limit=5")
    detail_response = client.get("/api/dashboard/strategy-evaluations/eval-1")

    assert list_response.status_code == 200
    assert list_response.json()["strategy_evaluations"][0]["evaluation_id"] == "eval-1"
    assert detail_response.status_code == 200
    assert detail_response.json()["evaluation_id"] == "eval-1"
    assert detail_response.json()["variants"][0]["not_recommended_reasons"] == [
        "基准参数，不参与推荐比较"
    ]


def test_dashboard_api_returns_strategy_insights() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    list_response = client.get("/api/dashboard/strategy-insights?limit=5")
    detail_response = client.get("/api/dashboard/strategy-insights/insight-1")

    assert list_response.status_code == 200
    assert list_response.json()["strategy_insights"][0]["insight_id"] == "insight-1"
    assert detail_response.status_code == 200
    assert detail_response.json()["manual_status"] == "pending_review"
    assert detail_response.json()["experiments"][0]["policy_status"] == "approved"


def test_dashboard_api_returns_404_for_missing_strategy_insight() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    response = client.get("/api/dashboard/strategy-insights/missing")

    assert response.status_code == 404
    assert "strategy insight 不存在" in response.json()["detail"]


def test_dashboard_api_returns_404_for_missing_strategy_evaluation() -> None:
    client = TestClient(create_app(service_factory=lambda: FakeDashboardService()))

    response = client.get("/api/dashboard/strategy-evaluations/missing")

    assert response.status_code == 404
    assert "strategy evaluation 不存在" in response.json()["detail"]


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

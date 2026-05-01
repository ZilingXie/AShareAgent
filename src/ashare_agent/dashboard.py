from __future__ import annotations

from ashare_agent.agents.dashboard_query_agent import (
    DashboardBacktest,
    DashboardDaySummary,
    DashboardPipelineRun,
    DashboardQueryAgent,
    DashboardStrategyComparison,
    DashboardStrategyComparisonItem,
    DashboardStrategyEvaluation,
    DashboardStrategyEvaluationRecommendation,
    DashboardStrategyEvaluationVariant,
    DashboardTrendSummary,
)

DashboardDay = DashboardDaySummary
DashboardRun = DashboardPipelineRun
DashboardTrends = DashboardTrendSummary
DashboardBacktestRun = DashboardBacktest
DashboardStrategyComparisonResult = DashboardStrategyComparison
DashboardStrategyComparisonRow = DashboardStrategyComparisonItem
DashboardStrategyEvaluationResult = DashboardStrategyEvaluation
DashboardStrategyEvaluationRecommendationResult = DashboardStrategyEvaluationRecommendation
DashboardStrategyEvaluationVariantResult = DashboardStrategyEvaluationVariant


class DashboardQueryService(DashboardQueryAgent):
    def list_runs(self, limit: int = 50) -> list[DashboardRun]:
        return self.list_pipeline_runs(limit)

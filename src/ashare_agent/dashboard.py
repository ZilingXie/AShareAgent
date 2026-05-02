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
    DashboardStrategyInsight,
    DashboardStrategyInsightExperiment,
    DashboardStrategyInsightHypothesis,
    DashboardStrategyInsightWindow,
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
DashboardStrategyInsightResult = DashboardStrategyInsight
DashboardStrategyInsightHypothesisResult = DashboardStrategyInsightHypothesis
DashboardStrategyInsightExperimentResult = DashboardStrategyInsightExperiment
DashboardStrategyInsightWindowResult = DashboardStrategyInsightWindow


class DashboardQueryService(DashboardQueryAgent):
    def list_runs(self, limit: int = 50) -> list[DashboardRun]:
        return self.list_pipeline_runs(limit)

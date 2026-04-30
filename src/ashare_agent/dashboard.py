from __future__ import annotations

from ashare_agent.agents.dashboard_query_agent import (
    DashboardDaySummary,
    DashboardPipelineRun,
    DashboardQueryAgent,
)

DashboardDay = DashboardDaySummary
DashboardRun = DashboardPipelineRun


class DashboardQueryService(DashboardQueryAgent):
    def list_runs(self, limit: int = 50) -> list[DashboardRun]:
        return self.list_pipeline_runs(limit)

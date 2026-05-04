import type {
  DashboardBacktest,
  DashboardDay,
  DashboardRun,
  DashboardStageRunGroup,
  DashboardStageRunGroupDetail,
  DashboardStrategyComparison,
  DashboardStrategyEvaluation,
  DashboardStrategyInsight,
  DashboardTrends,
} from "./types";

async function readJson<T>(response: Response): Promise<T> {
  if (response.ok) {
    return (await response.json()) as T;
  }
  let detail = response.statusText;
  try {
    const body = (await response.json()) as { detail?: string };
    detail = body.detail ?? detail;
  } catch {
    detail = await response.text();
  }
  throw new Error(detail);
}

export async function fetchRuns(limit = 50): Promise<DashboardRun[]> {
  const response = await fetch(`/api/dashboard/runs?limit=${limit}`);
  const body = await readJson<{ runs: DashboardRun[] }>(response);
  return body.runs;
}

export async function fetchDashboardDay(tradeDate: string): Promise<DashboardDay> {
  const response = await fetch(`/api/dashboard/days/${tradeDate}`);
  return readJson<DashboardDay>(response);
}

export async function fetchStageRunGroups(limit = 200): Promise<DashboardStageRunGroup[]> {
  const response = await fetch(`/api/dashboard/stage-run-groups?limit=${limit}`);
  const body = await readJson<{ stage_run_groups: DashboardStageRunGroup[] }>(response);
  return body.stage_run_groups;
}

export async function fetchStageRunGroupDetail(
  tradeDate: string,
  stage: string
): Promise<DashboardStageRunGroupDetail> {
  const response = await fetch(
    `/api/dashboard/days/${tradeDate}/stage-groups/${encodeURIComponent(stage)}`
  );
  return readJson<DashboardStageRunGroupDetail>(response);
}

export async function fetchDashboardTrends(
  startDate: string,
  endDate: string
): Promise<DashboardTrends> {
  const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
  const response = await fetch(`/api/dashboard/trends?${params.toString()}`);
  return readJson<DashboardTrends>(response);
}

export async function fetchBacktests(limit = 50): Promise<DashboardBacktest[]> {
  const response = await fetch(`/api/dashboard/backtests?limit=${limit}`);
  const body = await readJson<{ backtests: DashboardBacktest[] }>(response);
  return body.backtests;
}

export async function fetchStrategyComparison(
  backtestIds: string[]
): Promise<DashboardStrategyComparison> {
  const params = new URLSearchParams({ backtest_ids: backtestIds.join(",") });
  const response = await fetch(`/api/dashboard/strategy-comparison?${params.toString()}`);
  return readJson<DashboardStrategyComparison>(response);
}

export async function fetchStrategyEvaluations(
  limit = 50
): Promise<DashboardStrategyEvaluation[]> {
  const response = await fetch(`/api/dashboard/strategy-evaluations?limit=${limit}`);
  const body = await readJson<{ strategy_evaluations: DashboardStrategyEvaluation[] }>(response);
  return body.strategy_evaluations;
}

export async function fetchStrategyEvaluation(
  evaluationId: string
): Promise<DashboardStrategyEvaluation> {
  const response = await fetch(
    `/api/dashboard/strategy-evaluations/${encodeURIComponent(evaluationId)}`
  );
  return readJson<DashboardStrategyEvaluation>(response);
}

export async function fetchStrategyInsights(limit = 50): Promise<DashboardStrategyInsight[]> {
  const response = await fetch(`/api/dashboard/strategy-insights?limit=${limit}`);
  const body = await readJson<{ strategy_insights: DashboardStrategyInsight[] }>(response);
  return body.strategy_insights;
}

export async function fetchStrategyInsight(
  insightId: string
): Promise<DashboardStrategyInsight> {
  const response = await fetch(
    `/api/dashboard/strategy-insights/${encodeURIComponent(insightId)}`
  );
  return readJson<DashboardStrategyInsight>(response);
}

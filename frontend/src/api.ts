import type { DashboardDay, DashboardRun } from "./types";

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

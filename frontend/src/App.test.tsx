import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { DashboardDay, DashboardRun } from "./types";

const runsFixture: DashboardRun[] = [
  {
    run_id: "run-review",
    trade_date: "2026-04-29",
    stage: "post_market_review",
    status: "success",
    report_path: "reports/2026-04-29/post-market-review.md",
    failure_reason: null,
    created_at: "2026-04-29T08:00:00+00:00",
  },
  {
    run_id: "run-failed",
    trade_date: "2026-04-29",
    stage: "pre_market",
    status: "failed",
    report_path: null,
    failure_reason: "必需数据源失败: market_bars",
    created_at: "2026-04-29T07:00:00+00:00",
  },
];

const dayFixture: DashboardDay = {
  trade_date: "2026-04-29",
  runs: runsFixture,
  watchlist: [
    {
      run_id: "run-pre",
      symbol: "510300",
      score: 0.82,
      score_breakdown: { technical: 0.45, market: 0.2 },
      reasons: ["趋势改善"],
    },
  ],
  risk_decisions: [
    {
      run_id: "run-pre",
      symbol: "510300",
      signal_action: "paper_buy",
      approved: false,
      reasons: ["接近涨停，不买入"],
      target_position_pct: "0",
    },
  ],
  paper_orders: [
    {
      run_id: "run-review",
      order_id: "paper-2026-04-29-510300-buy",
      symbol: "510300",
      trade_date: "2026-04-29",
      side: "buy",
      quantity: 100,
      price: "4.1041",
      amount: "410.41",
      slippage: "0.001",
      reason: "通过",
      is_real_trade: false,
      created_at: "2026-04-29T08:00:00+00:00",
    },
  ],
  positions: [
    {
      run_id: "run-review",
      symbol: "510300",
      opened_at: "2026-04-27",
      quantity: 100,
      entry_price: "4.00",
      current_price: "4.20",
      status: "open",
      closed_at: null,
      exit_price: null,
      pnl_amount: "20.00",
      pnl_pct: 0.05,
      holding_days: 2,
    },
  ],
  portfolio_snapshot: {
    run_id: "run-review",
    trade_date: "2026-04-29",
    cash: "99589.59",
    market_value: "420.00",
    total_value: "100009.59",
    open_positions: 1,
  },
  review_report: {
    run_id: "run-review",
    trade_date: "2026-04-29",
    summary: "模拟账户总资产 100009.59。",
    stats: { total_value: 100009.59 },
    attribution: ["510300: 当前价 4.20, 成本 4.00"],
    parameter_suggestions: ["继续观察。"],
    metrics: {
      realized_pnl: "500.00",
      win_rate: 0.5,
      average_holding_days: 2,
      sell_reason_distribution: { 趋势走弱卖出: 1 },
      max_drawdown: 0.06862745098,
    },
  },
  source_snapshots: [
    {
      run_id: "run-failed",
      stage: "pre_market",
      source: "market_bars",
      trade_date: "2026-04-29",
      status: "failed",
      failure_reason: "EastMoney endpoint disconnected",
      row_count: 0,
      metadata: {},
      collected_at: "2026-04-29T07:00:00+00:00",
    },
  ],
};

describe("dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders runs, watchlist, orders and positions", async () => {
    mockFetch(dayFixture);

    render(<App />);

    expect(await screen.findByText("只读观察台")).toBeInTheDocument();
    expect(await screen.findAllByText("510300")).toHaveLength(4);
    expect(screen.getByText("趋势改善")).toBeInTheDocument();
    expect(screen.getByText("20.00 / 5.00%")).toBeInTheDocument();
    expect(screen.getByText("已实现盈亏")).toBeInTheDocument();
    expect(screen.getByText("500.00")).toBeInTheDocument();
    expect(screen.getByText("胜率")).toBeInTheDocument();
    expect(screen.getByText("50.00%")).toBeInTheDocument();
    expect(screen.getByText("2.00 天")).toBeInTheDocument();
    expect(screen.getByText(/趋势走弱卖出: 1/)).toBeInTheDocument();
    expect(screen.getByText("6.86%")).toBeInTheDocument();
  });

  it("shows failure reasons and the real-trade false flag", async () => {
    mockFetch(dayFixture);

    render(<App />);

    expect(await screen.findByText("必需数据源失败: market_bars")).toBeInTheDocument();
    expect(await screen.findByText("EastMoney endpoint disconnected")).toBeInTheDocument();
    expect(screen.getByText("False")).toBeInTheDocument();
  });

  it("renders empty states for a quiet trading day", async () => {
    mockFetch({
      ...dayFixture,
      watchlist: [],
      risk_decisions: [],
      paper_orders: [],
      positions: [],
      source_snapshots: [],
      review_report: null,
      portfolio_snapshot: null,
    });

    render(<App />);

    await waitFor(() => expect(screen.getByText("暂无观察名单")).toBeInTheDocument());
    expect(screen.getByText("暂无模拟订单")).toBeInTheDocument();
    expect(screen.getByText("暂无持仓")).toBeInTheDocument();
    expect(screen.getByText("暂无 source snapshot")).toBeInTheDocument();
  });
});

function mockFetch(day: DashboardDay): void {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/api/dashboard/runs") ? { runs: runsFixture } : day;
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
  });
}

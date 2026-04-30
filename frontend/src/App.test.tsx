import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { DashboardDay, DashboardRun, DashboardTrends } from "./types";

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
  {
    run_id: "run-previous",
    trade_date: "2026-04-28",
    stage: "post_market_review",
    status: "success",
    report_path: "reports/2026-04-28/post-market-review.md",
    failure_reason: null,
    created_at: "2026-04-28T08:00:00+00:00",
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
  llm_analysis: {
    run_id: "run-pre",
    trade_date: "2026-04-29",
    model: "mock-llm",
    summary: "盘前关注指数趋势和量能。",
    key_points: ["观察名单由规则信号生成"],
    risk_notes: ["仅用于模拟研究，不构成投资建议。"],
    created_at: "2026-04-29T07:30:00+00:00",
  },
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
      reason: "风控通过后买入",
      is_real_trade: false,
      created_at: "2026-04-29T08:00:00+00:00",
    },
    {
      run_id: "run-review",
      order_id: "paper-2026-04-29-159915-sell",
      symbol: "159915",
      trade_date: "2026-04-29",
      side: "sell",
      quantity: 50,
      price: "110",
      amount: "5500",
      slippage: "0.001",
      reason: "触发止损",
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
  data_quality_reports: [
    {
      run_id: "run-failed",
      stage: "pre_market",
      trade_date: "2026-04-29",
      status: "failed",
      source_failure_rate: 0.2,
      total_sources: 5,
      failed_source_count: 1,
      empty_source_count: 0,
      missing_market_bar_count: 1,
      abnormal_price_count: 0,
      is_trade_date: true,
      created_at: "2026-04-29T07:00:00+00:00",
      issues: [
        {
          severity: "error",
          check_name: "missing_market_bar",
          source: "market_bars",
          symbol: "510300",
          message: "510300 缺少 2026-04-29 当日行情",
          metadata: { trade_date: "2026-04-29" },
        },
      ],
    },
  ],
};

const trendsFixture: DashboardTrends = {
  start_date: "2026-04-28",
  end_date: "2026-04-29",
  points: [
    {
      trade_date: "2026-04-28",
      total_value: "100000",
      signal_count: 1,
      approved_count: 1,
      rejected_count: 0,
      max_signal_score: 0.72,
      source_failure_rate: 0,
      blocked_count: 0,
      warning_count: 0,
    },
    {
      trade_date: "2026-04-29",
      total_value: "100500",
      signal_count: 2,
      approved_count: 1,
      rejected_count: 1,
      max_signal_score: 0.91,
      source_failure_rate: 0.2,
      blocked_count: 1,
      warning_count: 2,
    },
  ],
  risk_reject_reasons: {
    "接近涨停，不买入": 2,
  },
};

const strategyComparisonFixture = {
  backtest_ids: ["bt-signal-v1", "bt-signal-v2"],
  items: [
    {
      backtest_id: "bt-signal-v1",
      strategy_params_version: "signal-v1",
      provider: "mock",
      start_date: "2026-04-27",
      end_date: "2026-04-29",
      attempted_days: 3,
      succeeded_days: 3,
      failed_days: 0,
      win_rate: 0.5,
      max_drawdown: 0.06862745098,
      total_return: 0.0125,
      risk_reject_rate: 0.25,
      data_quality_failure_rate: 0.3333333333,
    },
  ],
};

const backtestsFixture = {
  backtests: [
    {
      backtest_id: "bt-signal-v1",
      strategy_params_version: "signal-v1",
      provider: "mock",
      start_date: "2026-04-27",
      end_date: "2026-04-29",
      status: "success",
      attempted_days: 3,
      succeeded_days: 3,
      failed_days: 0,
      created_at: "2026-04-29T09:00:00+00:00",
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
    expect((await screen.findAllByText("510300")).length).toBeGreaterThanOrEqual(5);
    expect(screen.getByText("趋势改善")).toBeInTheDocument();
    expect(screen.getByText("LLM 盘前分析")).toBeInTheDocument();
    expect(screen.getByText("盘前关注指数趋势和量能。")).toBeInTheDocument();
    expect(screen.getByText("观察名单由规则信号生成")).toBeInTheDocument();
    expect(screen.getByText("仅用于模拟研究，不构成投资建议。")).toBeInTheDocument();
    expect(screen.getByText("风控通过后买入")).toBeInTheDocument();
    expect(screen.getByText("触发止损")).toBeInTheDocument();
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
    expect(await screen.findByText("数据质量失败")).toBeInTheDocument();
    expect(screen.getByText("510300 缺少 2026-04-29 当日行情")).toBeInTheDocument();
    expect(screen.getAllByText("False")).toHaveLength(2);
  });

  it("renders date range filters and trend panels", async () => {
    mockFetch(dayFixture, trendsFixture);

    render(<App />);

    expect(await screen.findByLabelText("开始日期")).toHaveValue("2026-04-28");
    expect(screen.getByLabelText("结束日期")).toHaveValue("2026-04-29");
    expect(await screen.findByText("权益曲线")).toBeInTheDocument();
    expect(screen.getAllByText("100,500.00").length).toBeGreaterThan(0);
    expect(screen.getByText("信号趋势")).toBeInTheDocument();
    expect(screen.getByText("最高评分 0.91")).toBeInTheDocument();
    expect(screen.getByText("风控拒绝原因")).toBeInTheDocument();
    expect(screen.getByText(/接近涨停，不买入: 2/)).toBeInTheDocument();
    expect(screen.getByText("数据质量趋势")).toBeInTheDocument();
    expect(screen.getByText("阻断 1")).toBeInTheDocument();
    expect(screen.getByText("warning 2")).toBeInTheDocument();
  });

  it("renders strategy version comparison for backtests", async () => {
    mockFetch(dayFixture, trendsFixture, strategyComparisonFixture);

    render(<App />);

    expect(await screen.findByText("策略版本对比")).toBeInTheDocument();
    expect(screen.getByText("bt-signal-v1")).toBeInTheDocument();
    expect(screen.getByText("signal-v1")).toBeInTheDocument();
    expect(screen.getByText("收益 1.25%")).toBeInTheDocument();
    expect(screen.getByText("拒绝率 25.00%")).toBeInTheDocument();
    expect(screen.getByText("质量失败率 33.33%")).toBeInTheDocument();
  });

  it("renders empty states for a quiet trading day", async () => {
    mockFetch({
      ...dayFixture,
      watchlist: [],
      risk_decisions: [],
      llm_analysis: null,
      paper_orders: [],
      positions: [],
      source_snapshots: [],
      data_quality_reports: [],
      review_report: null,
      portfolio_snapshot: null,
    });

    render(<App />);

    await waitFor(() => expect(screen.getByText("暂无观察名单")).toBeInTheDocument());
    expect(screen.getByText("暂无模拟订单")).toBeInTheDocument();
    expect(screen.getByText("暂无持仓")).toBeInTheDocument();
    expect(screen.getByText("暂无 source snapshot")).toBeInTheDocument();
    expect(screen.getByText("暂无数据质量报告")).toBeInTheDocument();
  });
});

function mockFetch(
  day: DashboardDay,
  trends: DashboardTrends = trendsFixture,
  strategyComparison = strategyComparisonFixture
): void {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/api/dashboard/runs")
      ? { runs: runsFixture }
      : url.includes("/api/dashboard/backtests")
        ? backtestsFixture
      : url.includes("/api/dashboard/strategy-comparison")
        ? strategyComparison
      : url.includes("/api/dashboard/trends")
        ? trends
        : day;
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
  });
}

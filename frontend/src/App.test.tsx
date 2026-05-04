import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type {
  DashboardDay,
  DashboardRun,
  DashboardStageRunGroup,
  DashboardStageRunGroupDetail,
  DashboardStrategyEvaluation,
  DashboardStrategyInsight,
  DashboardTrends,
} from "./types";

const runsFixture: DashboardRun[] = [
  {
    run_id: "run-pre",
    trade_date: "2026-04-29",
    stage: "pre_market",
    status: "success",
    report_path: "reports/2026-04-29/pre-market.md",
    failure_reason: null,
    created_at: "2026-04-29T07:30:00+00:00",
  },
  {
    run_id: "run-intraday",
    trade_date: "2026-04-29",
    stage: "intraday_watch",
    status: "success",
    report_path: "reports/2026-04-29/intraday-watch.md",
    failure_reason: null,
    created_at: "2026-04-29T07:45:00+00:00",
  },
  {
    run_id: "run-intraday-retry",
    trade_date: "2026-04-29",
    stage: "intraday_watch",
    status: "success",
    report_path: "reports/2026-04-29/intraday-watch-retry.md",
    failure_reason: null,
    created_at: "2026-04-29T07:55:00+00:00",
  },
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
  signals: [
    {
      run_id: "run-pre",
      symbol: "510300",
      trade_date: "2026-04-29",
      action: "paper_buy",
      score: 0.82,
      score_breakdown: { technical: 0.45, market: 0.2 },
      reasons: ["进入模拟买入候选"],
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
      run_id: "run-intraday",
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
      execution_source: "mock_intraday",
      execution_timestamp: "2026-04-29T09:31:00",
      execution_method: "first_valid_1m_bar",
      reference_price: "4.10",
      used_daily_fallback: false,
      execution_failure_reason: null,
      created_at: "2026-04-29T08:00:00+00:00",
    },
    {
      run_id: "run-intraday",
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
      execution_source: "mock_intraday",
      execution_timestamp: "2026-04-29T09:31:00",
      execution_method: "first_valid_1m_bar",
      reference_price: "110",
      used_daily_fallback: false,
      execution_failure_reason: null,
      created_at: "2026-04-29T08:00:00+00:00",
    },
  ],
  execution_events: [
    {
      run_id: "run-intraday",
      symbol: "159915",
      trade_date: "2026-04-29",
      side: "buy",
      status: "rejected",
      execution_method: "first_valid_1m_bar",
      used_daily_fallback: false,
      execution_source: null,
      execution_timestamp: null,
      reference_price: null,
      estimated_price: null,
      slippage: null,
      failure_reason: "无分钟线，无法成交",
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
  intraday_source_health: [
    {
      run_id: "run-intraday",
      stage: "intraday_watch",
      source: "akshare_em",
      symbol: "510300",
      status: "failed",
      returned_rows: 0,
      retry_attempts: 2,
      timeout_seconds: 2,
      last_error: "RemoteDisconnected",
    },
    {
      run_id: "run-intraday",
      stage: "intraday_watch",
      source: "akshare_sina",
      symbol: "510300",
      status: "success",
      returned_rows: 3,
      retry_attempts: 2,
      timeout_seconds: 2,
      last_error: null,
    },
  ],
  trading_calendar: {
    trade_date: "2026-04-29",
    is_trade_date: true,
    source: "trade_calendar",
    collected_at: "2026-04-29T07:00:00+00:00",
  },
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
  data_reliability_reports: [
    {
      run_id: "run-pre",
      trade_date: "2026-04-29",
      status: "failed",
      is_trade_date: true,
      lookback_trade_days: 30,
      total_sources: 3,
      failed_source_count: 1,
      empty_source_count: 1,
      source_failure_rate: 0.3333,
      missing_market_bar_count: 1,
      source_health: [
        {
          source: "market_bars",
          status: "success",
          total_snapshots: 1,
          failed_snapshots: 0,
          empty_snapshots: 0,
          row_count: 2,
          failure_rate: 0,
          last_failure_reason: null,
          required: true,
        },
        {
          source: "policy",
          status: "failed",
          total_snapshots: 1,
          failed_snapshots: 1,
          empty_snapshots: 0,
          row_count: 0,
          failure_rate: 1,
          last_failure_reason: "policy endpoint failed",
          required: false,
        },
      ],
      market_bar_gaps: [
        {
          symbol: "510300",
          missing_dates: ["2026-04-28"],
          missing_count: 1,
        },
      ],
      issues: [
        {
          severity: "error",
          check_name: "market_bar_gap",
          source: "market_bars",
          symbol: "510300",
          message: "510300 近 30 个交易日缺少 1 天行情",
          metadata: { missing_dates: ["2026-04-28"] },
        },
      ],
      created_at: "2026-04-29T07:00:00+00:00",
    },
  ],
};

const stageRunGroupsFixture: DashboardStageRunGroup[] = [
  {
    group_id: "2026-04-29:pre_market",
    trade_date: "2026-04-29",
    stage: "pre_market",
    status: "partial_failure",
    total_run_count: 2,
    success_count: 1,
    failed_count: 1,
    skipped_count: 0,
    latest_run_id: "run-pre",
    latest_success_run_id: "run-pre",
    member_run_ids: ["run-pre", "run-failed"],
    failure_reasons: ["必需数据源失败: market_bars"],
    created_at: "2026-04-29T07:30:00+00:00",
  },
  {
    group_id: "2026-04-29:intraday_watch",
    trade_date: "2026-04-29",
    stage: "intraday_watch",
    status: "success",
    total_run_count: 2,
    success_count: 2,
    failed_count: 0,
    skipped_count: 0,
    latest_run_id: "run-intraday-retry",
    latest_success_run_id: "run-intraday-retry",
    member_run_ids: ["run-intraday-retry", "run-intraday"],
    failure_reasons: [],
    created_at: "2026-04-29T07:55:00+00:00",
  },
  {
    group_id: "2026-04-29:post_market_review",
    trade_date: "2026-04-29",
    stage: "post_market_review",
    status: "success",
    total_run_count: 1,
    success_count: 1,
    failed_count: 0,
    skipped_count: 0,
    latest_run_id: "run-review",
    latest_success_run_id: "run-review",
    member_run_ids: ["run-review"],
    failure_reasons: [],
    created_at: "2026-04-29T08:00:00+00:00",
  },
  {
    group_id: "2026-04-28:post_market_review",
    trade_date: "2026-04-28",
    stage: "post_market_review",
    status: "success",
    total_run_count: 1,
    success_count: 1,
    failed_count: 0,
    skipped_count: 0,
    latest_run_id: "run-previous",
    latest_success_run_id: "run-previous",
    member_run_ids: ["run-previous"],
    failure_reasons: [],
    created_at: "2026-04-28T08:00:00+00:00",
  },
];

const intradayStageDetailFixture: DashboardStageRunGroupDetail = {
  group: stageRunGroupsFixture[1],
  runs: runsFixture.filter((run) =>
    ["run-intraday-retry", "run-intraday"].includes(run.run_id)
  ),
  watchlist: [],
  signals: [],
  llm_analyses: [],
  risk_decisions: [],
  paper_orders: [
    ...dayFixture.paper_orders,
    {
      run_id: "run-intraday-retry",
      order_id: "paper-2026-04-29-510300-buy-retry",
      symbol: "510300",
      trade_date: "2026-04-29",
      side: "buy",
      quantity: 100,
      price: "4.1050",
      amount: "410.50",
      slippage: "0.001",
      reason: "重跑盘中买入",
      is_real_trade: false,
      execution_source: "mock_intraday",
      execution_timestamp: "2026-04-29T09:32:00",
      execution_method: "first_valid_1m_bar",
      reference_price: "4.10",
      used_daily_fallback: false,
      execution_failure_reason: null,
      created_at: "2026-04-29T08:03:00+00:00",
    },
  ],
  execution_events: dayFixture.execution_events,
  positions: dayFixture.positions,
  portfolio_snapshots: dayFixture.portfolio_snapshot ? [dayFixture.portfolio_snapshot] : [],
  review_reports: [],
  source_snapshots: dayFixture.source_snapshots,
  intraday_source_health: dayFixture.intraday_source_health,
  data_quality_reports: [],
  data_reliability_reports: [],
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
      reliability_status: "passed",
      reliability_source_failure_rate: 0,
      reliability_missing_market_bar_count: 0,
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
      reliability_status: "failed",
      reliability_source_failure_rate: 0.3333,
      reliability_missing_market_bar_count: 1,
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

const duplicateStrategyComparisonFixture = {
  backtest_ids: ["bt-signal-v1", "bt-signal-v1"],
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
    {
      backtest_id: "bt-signal-v1",
      strategy_params_version: "signal-v1-duplicate",
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

const strategyEvaluationFixture: DashboardStrategyEvaluation = {
  evaluation_id: "eval-real",
  provider: "akshare",
  start_date: "2026-04-27",
  end_date: "2026-04-29",
  report_path: "reports/eval-real/strategy-evaluation.md",
  variant_count: 3,
  recommendation: {
    summary: "可考虑人工复核后替换参数: stronger",
    recommended_variant_ids: ["stronger"],
  },
  variants: [
    {
      id: "baseline",
      label: "当前参数",
      version: "params-baseline",
      backtest_id: "eval-real-baseline",
      success: true,
      attempted_days: 3,
      succeeded_days: 3,
      failed_days: 0,
      source_failure_rate: 0,
      data_quality_failure_rate: 0,
      signal_count: 2,
      risk_approved_count: 2,
      risk_rejected_count: 0,
      order_count: 1,
      execution_failed_count: 0,
      closed_trade_count: 1,
      signal_hit_count: 1,
      signal_hit_rate: 1,
      open_position_count: 0,
      holding_pnl: "120.00",
      total_return: 0.01,
      max_drawdown: 0.03,
      is_recommended: false,
      not_recommended_reasons: ["基准参数，不参与推荐比较"],
    },
    {
      id: "stronger",
      label: "更强收益",
      version: "params-stronger",
      backtest_id: "eval-real-stronger",
      success: true,
      attempted_days: 3,
      succeeded_days: 3,
      failed_days: 0,
      source_failure_rate: 0,
      data_quality_failure_rate: 0,
      signal_count: 3,
      risk_approved_count: 3,
      risk_rejected_count: 0,
      order_count: 2,
      execution_failed_count: 0,
      closed_trade_count: 1,
      signal_hit_count: 1,
      signal_hit_rate: 1,
      open_position_count: 1,
      holding_pnl: "180.00",
      total_return: 0.02,
      max_drawdown: 0.02,
      is_recommended: true,
      not_recommended_reasons: [],
    },
    {
      id: "weaker",
      label: "更弱参数",
      version: "params-weaker",
      backtest_id: "eval-real-weaker",
      success: true,
      attempted_days: 3,
      succeeded_days: 2,
      failed_days: 1,
      source_failure_rate: 0.2,
      data_quality_failure_rate: 0.3333333333,
      signal_count: 1,
      risk_approved_count: 1,
      risk_rejected_count: 1,
      order_count: 1,
      execution_failed_count: 1,
      closed_trade_count: 1,
      signal_hit_count: 0,
      signal_hit_rate: 0,
      open_position_count: 0,
      holding_pnl: "-50.00",
      total_return: 0.01,
      max_drawdown: 0.05,
      is_recommended: false,
      not_recommended_reasons: [
        "收益未优于基准",
        "命中率低于基准",
        "最大回撤高于基准",
        "失败天数多于基准",
        "source 失败率高于基准",
      ],
    },
  ],
};

const strategyEvaluationsFixture = {
  strategy_evaluations: [strategyEvaluationFixture],
};

const strategyInsightFixture: DashboardStrategyInsight = {
  insight_id: "insight-real",
  trade_date: "2026-04-30",
  provider: "mock",
  summary: "近期信号偏少，建议先小幅降低最低评分阈值做回测。",
  attribution: ["信号数量偏少", "风控拒绝较多"],
  manual_status: "pending_review",
  report_path: "reports/insight-real/strategy-insights.md",
  hypotheses: [
    {
      area: "signal.min_score",
      direction: "lower",
      reason: "近期信号偏少",
      risk: "可能增加低质量交易",
    },
  ],
  experiments: [
    {
      name: "降低最低评分阈值",
      param: "signal.min_score",
      candidate_value: "0.50",
      policy_status: "approved",
      policy_reason: null,
      variant_id: "llm-signal-min-score-050",
      overrides: { signal: { min_score: "0.50" } },
    },
    {
      name: "关闭止损",
      param: "risk.stop_loss_pct",
      candidate_value: "0",
      policy_status: "rejected_by_policy",
      policy_reason: "risk.stop_loss_pct 不能低于 0.02",
      variant_id: null,
      overrides: {},
    },
  ],
  evaluation_windows: [
    {
      window_trade_days: 20,
      evaluation_id: "insight-real-20d",
      report_path: "reports/insight-real-20d/strategy-evaluation.md",
      recommended_variant_ids: ["llm-signal-min-score-050"],
      passed_variant_ids: ["llm-signal-min-score-050"],
      failed_variant_reasons: {},
    },
    {
      window_trade_days: 40,
      evaluation_id: "insight-real-40d",
      report_path: "reports/insight-real-40d/strategy-evaluation.md",
      recommended_variant_ids: ["llm-signal-min-score-050"],
      passed_variant_ids: ["llm-signal-min-score-050"],
      failed_variant_reasons: {},
    },
    {
      window_trade_days: 60,
      evaluation_id: "insight-real-60d",
      report_path: "reports/insight-real-60d/strategy-evaluation.md",
      recommended_variant_ids: [],
      passed_variant_ids: [],
      failed_variant_reasons: {
        "llm-signal-min-score-050": ["收益未优于基准"],
      },
    },
  ],
  recommended_variant_ids: ["llm-signal-min-score-050"],
};

const strategyInsightsFixture = {
  strategy_insights: [strategyInsightFixture],
};

const duplicateBacktestsFixture = {
  backtests: [
    ...backtestsFixture.backtests,
    {
      ...backtestsFixture.backtests[0],
      created_at: "2026-04-29T10:00:00+00:00",
    },
  ],
};

describe("dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the overview board by default", async () => {
    mockFetch(dayFixture);

    render(<App />);

    expect(await screen.findByText("只读观察台")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "总览" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "交易执行" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "策略" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "质量" })).toBeInTheDocument();
    expect(await screen.findByText("账户总览")).toBeInTheDocument();
    expect(screen.getByText("区间盈亏")).toBeInTheDocument();
    expect(screen.getByText("每日盈亏")).toBeInTheDocument();
    expect(screen.getByText("今日交易摘要")).toBeInTheDocument();
    expect(screen.getByText("当前持仓")).toBeInTheDocument();
    expect(screen.getByText("收盘复盘摘要")).toBeInTheDocument();
    expect(screen.getByText("20.00 / 5.00%")).toBeInTheDocument();
    expect(screen.getByText("已实现盈亏")).toBeInTheDocument();
    expect(screen.getAllByText("500.00").length).toBeGreaterThan(0);
    expect(screen.getByText("胜率")).toBeInTheDocument();
    expect(screen.getByText("50.00%")).toBeInTheDocument();
    expect(screen.getByText("2.00 天")).toBeInTheDocument();
    expect(screen.getByText(/趋势走弱卖出: 1/)).toBeInTheDocument();
    expect(screen.getByText("6.86%")).toBeInTheDocument();
  });

  it("renders merged stage groups and opens an aggregated stage detail drawer", async () => {
    mockFetch(dayFixture);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "交易执行" }));

    expect(
      await screen.findByRole("button", { name: /2026-04-29 盘前 部分失败/ })
    ).toBeInTheDocument();
    const preMarketGroup = screen.getByRole("button", { name: /2026-04-29 盘前/ });
    expect(screen.getAllByRole("button", { name: /2026-04-29 盘前/ })).toHaveLength(1);
    expect(within(preMarketGroup).getByText("2 次尝试")).toBeInTheDocument();
    expect(within(preMarketGroup).getByText("失败 1")).toBeInTheDocument();
    expect(await screen.findByText("盘前计划")).toBeInTheDocument();
    expect(screen.getByText("风控结果")).toBeInTheDocument();
    expect(screen.getByText("盘中模拟订单")).toBeInTheDocument();
    expect(screen.getByText("成交失败")).toBeInTheDocument();
    expect(screen.getByText("收盘复盘")).toBeInTheDocument();
    expect(screen.getByText("风控通过后买入")).toBeInTheDocument();
    expect(screen.getAllByText("False").length).toBeGreaterThanOrEqual(4);

    fireEvent.click(screen.getByRole("button", { name: /2026-04-29 盘中 成功/ }));

    expect(await screen.findByRole("dialog", { name: "阶段详情" })).toBeInTheDocument();
    expect(screen.getByText("盘中详情")).toBeInTheDocument();
    expect(screen.getByText("成员 run")).toBeInTheDocument();
    expect(screen.getAllByText("run-intraday").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("run-intraday-retry").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("重跑盘中买入")).toBeInTheDocument();
    expect(screen.getByText("分钟线成交依据")).toBeInTheDocument();
  });

  it("renders date range filters and trend panels", async () => {
    mockFetch(dayFixture, trendsFixture);

    render(<App />);

    expect(await screen.findByLabelText("开始日期")).toHaveValue("2026-04-28");
    expect(screen.getByLabelText("结束日期")).toHaveValue("2026-04-29");
    expect(await screen.findByText("权益曲线")).toBeInTheDocument();
    expect(screen.getAllByText("100,500.00").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "策略" }));
    expect(screen.getByText("信号趋势")).toBeInTheDocument();
    expect(screen.getByText("买入候选信号，不是实际买卖订单。")).toBeInTheDocument();
    expect(screen.getByText("最高评分 0.91")).toBeInTheDocument();
    expect(screen.getByText("风控拒绝原因")).toBeInTheDocument();
    expect(screen.getByText(/接近涨停，不买入: 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "质量" }));
    expect(screen.getByText("数据质量趋势")).toBeInTheDocument();
    expect(screen.getByText("阻断 1")).toBeInTheDocument();
    expect(screen.getByText("warning 2")).toBeInTheDocument();
    expect(screen.getByText("可靠性 failed")).toBeInTheDocument();
    expect(screen.getByText("缺口 1")).toBeInTheDocument();
  });

  it("renders strategy board with comparisons and evaluations", async () => {
    mockFetch(dayFixture, trendsFixture, strategyComparisonFixture);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "策略" }));

    expect(await screen.findByText("策略版本对比")).toBeInTheDocument();
    expect(screen.getByText("bt-signal-v1")).toBeInTheDocument();
    expect(screen.getByText("signal-v1")).toBeInTheDocument();
    expect(screen.getByText("收益 1.25%")).toBeInTheDocument();
    expect(screen.getByText("拒绝率 25.00%")).toBeInTheDocument();
    expect(screen.getAllByText("质量失败率 33.33%").length).toBeGreaterThan(0);
    expect(screen.getByText("eval-real")).toBeInTheDocument();
    expect(screen.getByText("可考虑人工复核后替换参数: stronger")).toBeInTheDocument();
    expect(screen.getByText("reports/eval-real/strategy-evaluation.md")).toBeInTheDocument();
    expect(screen.getByText("更强收益")).toBeInTheDocument();
    expect(screen.getByText("收益 2.00%")).toBeInTheDocument();
    expect(screen.getByText("回撤 2.00%")).toBeInTheDocument();
    expect(screen.getByText("source 失败率 20.00%")).toBeInTheDocument();
    expect(screen.getByText("不可推荐原因")).toBeInTheDocument();
    expect(screen.getByText("收益未优于基准")).toBeInTheDocument();
    expect(screen.getByText("source 失败率高于基准")).toBeInTheDocument();
    expect(
      screen.getByText("历史模拟评估，不构成投资建议，不自动修改策略参数。")
    ).toBeInTheDocument();
    expect(screen.queryByText("自动调参")).not.toBeInTheDocument();
    expect(screen.queryByText("真实下单")).not.toBeInTheDocument();
  });

  it("renders the read-only strategy optimization view", async () => {
    mockFetch(dayFixture, trendsFixture, strategyComparisonFixture, backtestsFixture);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "策略" }));

    expect((await screen.findAllByText("策略优化")).length).toBeGreaterThan(0);
    expect(screen.getByText("策略优化批次")).toBeInTheDocument();
    expect(screen.queryByText("策略假设")).not.toBeInTheDocument();
    expect(screen.getByText("insight-real")).toBeInTheDocument();
    expect(screen.getAllByText("待复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("近期信号偏少").length).toBeGreaterThan(0);
    expect(screen.getByText("降低最低评分阈值")).toBeInTheDocument();
    expect(screen.getByText("rejected_by_policy")).toBeInTheDocument();
    expect(screen.getByText("risk.stop_loss_pct 不能低于 0.02")).toBeInTheDocument();
    expect(screen.getByText("20 日")).toBeInTheDocument();
    expect(screen.getByText("40 日")).toBeInTheDocument();
    expect(screen.getByText("60 日")).toBeInTheDocument();
    expect(screen.getByText("reports/insight-real/strategy-insights.md")).toBeInTheDocument();
    expect(screen.queryByText("自动调参")).not.toBeInTheDocument();
    expect(screen.queryByText("真实下单")).not.toBeInTheDocument();
  });

  it("renders an empty state when there are no strategy evaluations", async () => {
    mockFetch(
      dayFixture,
      trendsFixture,
      strategyComparisonFixture,
      backtestsFixture,
      { strategy_evaluations: [] },
      null
    );

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "策略" }));

    expect(await screen.findByText("暂无策略评估")).toBeInTheDocument();
  });

  it("renders quality board with data and run diagnostics", async () => {
    mockFetch(dayFixture, trendsFixture);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "质量" }));

    expect(await screen.findByText("数据质量趋势")).toBeInTheDocument();
    expect(await screen.findByText("数据质量")).toBeInTheDocument();
    expect(await screen.findByText("运行可靠性")).toBeInTheDocument();
    expect(await screen.findByText("分钟线源健康")).toBeInTheDocument();
    expect(screen.getByText("数据源状态")).toBeInTheDocument();
    expect(screen.getByText("运行详情")).toBeInTheDocument();
    expect(screen.getByText("EastMoney endpoint disconnected")).toBeInTheDocument();
    expect(screen.getByText("RemoteDisconnected")).toBeInTheDocument();
    expect(screen.getByText("质量失败会影响策略可信度，但不会被静默兜底。")).toBeInTheDocument();
  });

  it("deduplicates strategy comparison rows and request ids", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mockFetch(
      dayFixture,
      trendsFixture,
      duplicateStrategyComparisonFixture,
      duplicateBacktestsFixture
    );

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "策略" }));

    expect(await screen.findByText("策略版本对比")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("bt-signal-v1")).toHaveLength(1));
    expect(screen.queryByText("signal-v1-duplicate")).not.toBeInTheDocument();
    expect(
      consoleError.mock.calls.some((call) => String(call[0]).includes("same key"))
    ).toBe(false);
    const comparisonRequest = vi
      .mocked(globalThis.fetch)
      .mock.calls.find(([input]) => String(input).includes("/api/dashboard/strategy-comparison"));
    expect(String(comparisonRequest?.[0])).toContain("backtest_ids=bt-signal-v1");
    expect(String(comparisonRequest?.[0])).not.toContain("bt-signal-v1%2Cbt-signal-v1");
  });

  it("renders empty states for a quiet trading day", async () => {
    mockFetch({
      ...dayFixture,
      watchlist: [],
      risk_decisions: [],
      llm_analysis: null,
      paper_orders: [],
      execution_events: [],
      positions: [],
      source_snapshots: [],
      intraday_source_health: [],
      trading_calendar: null,
      data_quality_reports: [],
      data_reliability_reports: [],
      review_report: null,
      portfolio_snapshot: null,
    });

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "交易执行" }));

    await waitFor(() => expect(screen.getByText("暂无观察名单")).toBeInTheDocument());
    expect(screen.getByText("暂无盘中模拟订单")).toBeInTheDocument();
    expect(screen.getByText("暂无成交失败")).toBeInTheDocument();
    expect(screen.getByText("暂无持仓")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "质量" }));

    expect(screen.getByText("暂无分钟线源健康记录")).toBeInTheDocument();
    expect(screen.getByText("暂无 source snapshot")).toBeInTheDocument();
    expect(screen.getByText("暂无数据质量报告")).toBeInTheDocument();
    expect(screen.getByText("暂无运行可靠性报告")).toBeInTheDocument();
  });
});

function mockFetch(
  day: DashboardDay,
  trends: DashboardTrends = trendsFixture,
  strategyComparison = strategyComparisonFixture,
  backtests = backtestsFixture,
  strategyEvaluations = strategyEvaluationsFixture,
  strategyEvaluation: DashboardStrategyEvaluation | null = strategyEvaluationFixture,
  strategyInsights = strategyInsightsFixture,
  strategyInsight: DashboardStrategyInsight | null = strategyInsightFixture,
  stageRunGroups = { stage_run_groups: stageRunGroupsFixture },
  stageRunGroupDetail: DashboardStageRunGroupDetail | null = intradayStageDetailFixture
): void {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/api/dashboard/strategy-insights/")
      ? strategyInsight
      : url.includes("/api/dashboard/strategy-insights")
        ? strategyInsights
      : url.includes("/api/dashboard/strategy-evaluations/")
      ? strategyEvaluation
      : url.includes("/api/dashboard/strategy-evaluations")
        ? strategyEvaluations
      : url.includes("/api/dashboard/days/") && url.includes("/stage-groups/")
        ? stageRunGroupDetail
      : url.includes("/api/dashboard/stage-run-groups")
        ? stageRunGroups
        : url.includes("/api/dashboard/runs")
      ? { runs: runsFixture }
      : url.includes("/api/dashboard/backtests")
        ? backtests
      : url.includes("/api/dashboard/strategy-comparison")
        ? strategyComparison
      : url.includes("/api/dashboard/trends")
        ? trends
        : day;
    if (body === null) {
      return Promise.resolve(
        new Response(JSON.stringify({ detail: "strategy evaluation 不存在" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        })
      );
    }
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
  });
}

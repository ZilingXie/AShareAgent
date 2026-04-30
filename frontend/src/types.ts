export interface DashboardRun {
  run_id: string;
  trade_date: string;
  stage: string;
  status: string;
  report_path: string | null;
  failure_reason: string | null;
  created_at: string | null;
}

export interface DashboardWatchlistItem {
  run_id: string;
  symbol: string;
  score: number;
  score_breakdown: Record<string, number>;
  reasons: string[];
}

export interface DashboardRiskDecision {
  run_id: string;
  symbol: string;
  signal_action: string;
  approved: boolean;
  reasons: string[];
  target_position_pct: string;
}

export interface DashboardPaperOrder {
  run_id: string;
  order_id: string;
  symbol: string;
  trade_date: string;
  side: string;
  quantity: number;
  price: string;
  amount: string;
  slippage: string;
  reason: string;
  is_real_trade: boolean;
  created_at: string | null;
}

export interface DashboardPosition {
  run_id: string;
  symbol: string;
  opened_at: string;
  quantity: number;
  entry_price: string;
  current_price: string;
  status: string;
  closed_at: string | null;
  exit_price: string | null;
  pnl_amount: string;
  pnl_pct: number;
  holding_days: number;
}

export interface DashboardPortfolioSnapshot {
  run_id: string;
  trade_date: string;
  cash: string;
  market_value: string;
  total_value: string;
  open_positions: number;
}

export interface DashboardReviewMetrics {
  realized_pnl: string;
  win_rate: number;
  average_holding_days: number;
  sell_reason_distribution: Record<string, number>;
  max_drawdown: number;
}

export interface DashboardReviewReport {
  run_id: string;
  trade_date: string;
  summary: string;
  stats: Record<string, number>;
  attribution: string[];
  parameter_suggestions: string[];
  metrics: DashboardReviewMetrics;
}

export interface DashboardSourceSnapshot {
  run_id: string;
  stage: string | null;
  source: string;
  trade_date: string;
  status: string;
  failure_reason: string | null;
  row_count: number;
  metadata: Record<string, unknown>;
  collected_at: string | null;
}

export interface DashboardDataQualityIssue {
  severity: string;
  check_name: string;
  source: string | null;
  symbol: string | null;
  message: string;
  metadata: Record<string, unknown>;
}

export interface DashboardDataQualityReport {
  run_id: string;
  stage: string;
  trade_date: string;
  status: string;
  source_failure_rate: number;
  total_sources: number;
  failed_source_count: number;
  empty_source_count: number;
  missing_market_bar_count: number;
  abnormal_price_count: number;
  is_trade_date: boolean | null;
  issues: DashboardDataQualityIssue[];
  created_at: string | null;
}

export interface DashboardTradingCalendarDay {
  trade_date: string;
  is_trade_date: boolean;
  source: string;
  collected_at: string | null;
}

export interface DashboardDataReliabilityIssue {
  severity: string;
  check_name: string;
  source: string | null;
  symbol: string | null;
  message: string;
  metadata: Record<string, unknown>;
}

export interface DashboardDataSourceHealth {
  source: string;
  status: string;
  total_snapshots: number;
  failed_snapshots: number;
  empty_snapshots: number;
  row_count: number;
  failure_rate: number;
  last_failure_reason: string | null;
  required: boolean;
}

export interface DashboardMarketBarGap {
  symbol: string;
  missing_dates: string[];
  missing_count: number;
}

export interface DashboardDataReliabilityReport {
  run_id: string;
  trade_date: string;
  status: string;
  is_trade_date: boolean | null;
  lookback_trade_days: number;
  total_sources: number;
  failed_source_count: number;
  empty_source_count: number;
  source_failure_rate: number;
  missing_market_bar_count: number;
  source_health: DashboardDataSourceHealth[];
  market_bar_gaps: DashboardMarketBarGap[];
  issues: DashboardDataReliabilityIssue[];
  created_at: string | null;
}

export interface DashboardTrendPoint {
  trade_date: string;
  total_value: string | null;
  signal_count: number;
  approved_count: number;
  rejected_count: number;
  max_signal_score: number | null;
  source_failure_rate: number;
  blocked_count: number;
  warning_count: number;
  reliability_status: string;
  reliability_source_failure_rate: number;
  reliability_missing_market_bar_count: number;
}

export interface DashboardTrends {
  start_date: string;
  end_date: string;
  points: DashboardTrendPoint[];
  risk_reject_reasons: Record<string, number>;
}

export interface DashboardDay {
  trade_date: string;
  runs: DashboardRun[];
  watchlist: DashboardWatchlistItem[];
  risk_decisions: DashboardRiskDecision[];
  paper_orders: DashboardPaperOrder[];
  positions: DashboardPosition[];
  portfolio_snapshot: DashboardPortfolioSnapshot | null;
  review_report: DashboardReviewReport | null;
  source_snapshots: DashboardSourceSnapshot[];
  trading_calendar: DashboardTradingCalendarDay | null;
  data_quality_reports: DashboardDataQualityReport[];
  data_reliability_reports: DashboardDataReliabilityReport[];
}

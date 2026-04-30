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
}

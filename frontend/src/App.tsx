import {
  Activity,
  AlertTriangle,
  BriefcaseBusiness,
  ClipboardList,
  Database,
  FileText,
  Gauge,
  ListChecks,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { fetchDashboardDay, fetchDashboardTrends, fetchRuns } from "./api";
import { fetchBacktests, fetchStrategyComparison } from "./api";
import {
  boolText,
  breakdown,
  days,
  distributionText,
  listText,
  money,
  percent,
  score,
} from "./format";
import type {
  DashboardDay,
  DashboardStrategyComparison,
  DashboardStrategyComparisonItem,
  DashboardDataQualityReport,
  DashboardDataReliabilityReport,
  DashboardLLMAnalysis,
  DashboardPaperOrder,
  DashboardPosition,
  DashboardRun,
  DashboardTrendPoint,
  DashboardTrends,
} from "./types";

const stageLabels: Record<string, string> = {
  pre_market: "盘前",
  intraday_watch: "盘中",
  post_market_review: "复盘",
};

const statusLabels: Record<string, string> = {
  success: "成功",
  failed: "失败",
  passed: "通过",
  warning: "警告",
  skipped: "跳过",
};

export default function App(): JSX.Element {
  const [runs, setRuns] = useState<DashboardRun[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [rangeStart, setRangeStart] = useState<string | null>(null);
  const [rangeEnd, setRangeEnd] = useState<string | null>(null);
  const [day, setDay] = useState<DashboardDay | null>(null);
  const [trends, setTrends] = useState<DashboardTrends | null>(null);
  const [strategyComparison, setStrategyComparison] =
    useState<DashboardStrategyComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trendError, setTrendError] = useState<string | null>(null);

  async function loadRuns(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const loadedRuns = await fetchRuns(200);
      const loadedBacktests = await fetchBacktests(20);
      const tradeDates = [...new Set(loadedRuns.map((run) => run.trade_date))].sort();
      setRuns(loadedRuns);
      setSelectedDate((current) => current ?? loadedRuns[0]?.trade_date ?? null);
      setRangeStart((current) => current ?? tradeDates[0] ?? null);
      setRangeEnd((current) => current ?? tradeDates[tradeDates.length - 1] ?? null);
      if (loadedBacktests.length === 0) {
        setStrategyComparison(null);
      } else {
        setStrategyComparison(
          await fetchStrategyComparison(loadedBacktests.map((item) => item.backtest_id))
        );
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Dashboard API 请求失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadRuns();
  }, []);

  useEffect(() => {
    if (!selectedDate) {
      setDay(null);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    fetchDashboardDay(selectedDate)
      .then((loadedDay) => {
        if (active) {
          setDay(loadedDay);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : "Dashboard API 请求失败");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selectedDate]);

  useEffect(() => {
    if (!rangeStart || !rangeEnd) {
      setTrends(null);
      return;
    }
    if (rangeStart > rangeEnd) {
      setTrendError("开始日期不能晚于结束日期");
      setTrends(null);
      return;
    }
    let active = true;
    setTrendLoading(true);
    setTrendError(null);
    fetchDashboardTrends(rangeStart, rangeEnd)
      .then((loadedTrends) => {
        if (active) {
          setTrends(loadedTrends);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setTrendError(caught instanceof Error ? caught.message : "Dashboard API 请求失败");
        }
      })
      .finally(() => {
        if (active) {
          setTrendLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [rangeStart, rangeEnd]);

  const visibleRuns = useMemo(
    () =>
      runs.filter((run) => {
        if (rangeStart && run.trade_date < rangeStart) {
          return false;
        }
        if (rangeEnd && run.trade_date > rangeEnd) {
          return false;
        }
        return true;
      }),
    [rangeEnd, rangeStart, runs]
  );

  useEffect(() => {
    if (!rangeStart || !rangeEnd || !selectedDate) {
      return;
    }
    if (selectedDate >= rangeStart && selectedDate <= rangeEnd) {
      return;
    }
    setSelectedDate(visibleRuns[0]?.trade_date ?? rangeEnd);
  }, [rangeEnd, rangeStart, selectedDate, visibleRuns]);

  const selectedRuns = useMemo(
    () => visibleRuns.filter((run) => run.trade_date === selectedDate),
    [selectedDate, visibleRuns]
  );

  return (
    <main className="shell">
      <aside className="sidebar" aria-label="Pipeline runs">
        <div className="sidebar-header">
          <div>
            <p className="eyebrow">AShareAgent</p>
            <h1>只读观察台</h1>
          </div>
          <button className="icon-button" type="button" onClick={() => void loadRuns()}>
            <RefreshCw size={16} aria-hidden="true" />
            <span className="sr-only">刷新</span>
          </button>
        </div>
        <div className="run-list">
          {visibleRuns.length === 0 && !loading ? <EmptyState text="暂无 pipeline run" /> : null}
          {visibleRuns.map((run) => (
            <button
              className={`run-item ${run.trade_date === selectedDate ? "selected" : ""}`}
              key={`${run.run_id}-${run.stage}`}
              onClick={() => setSelectedDate(run.trade_date)}
              type="button"
            >
              <span className="run-date">{run.trade_date}</span>
              <span className="run-meta">
                {stageLabels[run.stage] ?? run.stage}
                <StatusBadge status={run.status} />
              </span>
              {run.failure_reason ? <span className="failure">{run.failure_reason}</span> : null}
            </button>
          ))}
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">交易日</p>
            <h2>{selectedDate ?? "-"}</h2>
          </div>
          <div className="date-controls" aria-label="日期范围">
            <label>
              开始日期
              <input
                max={rangeEnd ?? undefined}
                onChange={(event) => setRangeStart(event.target.value || null)}
                type="date"
                value={rangeStart ?? ""}
              />
            </label>
            <label>
              结束日期
              <input
                min={rangeStart ?? undefined}
                onChange={(event) => setRangeEnd(event.target.value || null)}
                type="date"
                value={rangeEnd ?? ""}
              />
            </label>
          </div>
          <div className="status-strip">
            <span>{selectedRuns.length} 次运行</span>
            <span>{day?.paper_orders.length ?? 0} 笔模拟订单</span>
            <span>{day?.positions.length ?? 0} 个持仓状态</span>
            <span>{day ? qualityStatusSummary(day) : "无质量报告"}</span>
            <span>{day ? reliabilityStatusSummary(day) : "无可靠性报告"}</span>
          </div>
        </header>

        {error ? <div className="alert">{error}</div> : null}
        {trendError ? <div className="alert">{trendError}</div> : null}
        {loading ? <div className="loading">加载中</div> : null}
        {trendLoading ? <div className="loading">趋势加载中</div> : null}

        {trends ? <TrendPanels trends={trends} /> : null}
        <StrategyComparisonPanel comparison={strategyComparison} />

        {day ? (
          <div className="dashboard-grid">
            <Section icon={ListChecks} title="观察名单">
              {day.watchlist.length === 0 ? (
                <EmptyState text="暂无观察名单" />
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>symbol</th>
                      <th>score</th>
                      <th>分数拆解</th>
                      <th>原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {day.watchlist.map((item) => (
                      <tr key={`${item.run_id}-${item.symbol}`}>
                        <td>{item.symbol}</td>
                        <td>{score(item.score)}</td>
                        <td>{breakdown(item.score_breakdown)}</td>
                        <td>{listText(item.reasons)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            <Section icon={ShieldCheck} title="风控结果">
              {day.risk_decisions.length === 0 ? (
                <EmptyState text="暂无风控结果" />
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>symbol</th>
                      <th>动作</th>
                      <th>结果</th>
                      <th>原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {day.risk_decisions.map((decision) => (
                      <tr key={`${decision.run_id}-${decision.symbol}`}>
                        <td>{decision.symbol}</td>
                        <td>{decision.signal_action}</td>
                        <td>
                          <span className={`badge ${decision.approved ? "safe" : "danger"}`}>
                            {decision.approved ? "通过" : "拒绝"}
                          </span>
                        </td>
                        <td>{listText(decision.reasons)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            <Section icon={FileText} title="LLM 盘前分析">
              <LLMAnalysisPanel analysis={day.llm_analysis} />
            </Section>

            <Section icon={Activity} title="盘中模拟订单">
              <OrdersTable orders={day.paper_orders} />
            </Section>

            <Section icon={BriefcaseBusiness} title="当前持仓">
              <PositionsTable positions={day.positions} />
            </Section>

            <Section icon={FileText} title="收盘复盘">
              {day.portfolio_snapshot ? (
                <dl className="metrics">
                  <div>
                    <dt>总资产</dt>
                    <dd>{money(day.portfolio_snapshot.total_value)}</dd>
                  </div>
                  <div>
                    <dt>现金</dt>
                    <dd>{money(day.portfolio_snapshot.cash)}</dd>
                  </div>
                  <div>
                    <dt>市值</dt>
                    <dd>{money(day.portfolio_snapshot.market_value)}</dd>
                  </div>
                  <div>
                    <dt>open</dt>
                    <dd>{day.portfolio_snapshot.open_positions}</dd>
                  </div>
                </dl>
              ) : null}
              {day.review_report ? (
                <div className="report">
                  <dl className="metrics review-metrics">
                    <div>
                      <dt>已实现盈亏</dt>
                      <dd
                        className={
                          Number(day.review_report.metrics.realized_pnl) >= 0
                            ? "positive"
                            : "negative"
                        }
                      >
                        {money(day.review_report.metrics.realized_pnl)}
                      </dd>
                    </div>
                    <div>
                      <dt>胜率</dt>
                      <dd>{percent(day.review_report.metrics.win_rate)}</dd>
                    </div>
                    <div>
                      <dt>平均持仓天数</dt>
                      <dd>{days(day.review_report.metrics.average_holding_days)}</dd>
                    </div>
                    <div>
                      <dt>最大回撤</dt>
                      <dd className="negative">{percent(day.review_report.metrics.max_drawdown)}</dd>
                    </div>
                  </dl>
                  <p className="reason-distribution">
                    卖出原因分布：
                    {distributionText(day.review_report.metrics.sell_reason_distribution)}
                  </p>
                  <p>{day.review_report.summary}</p>
                  <p className="muted">{listText(day.review_report.parameter_suggestions)}</p>
                </div>
              ) : (
                <EmptyState text="暂无复盘报告" />
              )}
            </Section>

            <Section icon={Gauge} title="数据质量">
              <DataQualityTable reports={day.data_quality_reports} />
            </Section>

            <Section icon={Database} title="运行可靠性">
              <ReliabilityPanel day={day} reports={day.data_reliability_reports} />
            </Section>

            <Section icon={Database} title="数据源状态">
              {day.source_snapshots.length === 0 ? (
                <EmptyState text="暂无 source snapshot" />
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>source</th>
                      <th>stage</th>
                      <th>status</th>
                      <th>rows</th>
                      <th>失败原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {day.source_snapshots.map((snapshot) => (
                      <tr key={`${snapshot.run_id}-${snapshot.source}`}>
                        <td>{snapshot.source}</td>
                        <td>{snapshot.stage ?? "-"}</td>
                        <td>
                          <StatusBadge status={snapshot.status} />
                        </td>
                        <td>{snapshot.row_count}</td>
                        <td className={snapshot.failure_reason ? "failure-cell" : ""}>
                          {snapshot.failure_reason ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>

            <Section icon={ClipboardList} title="运行详情">
              {day.runs.length === 0 ? (
                <EmptyState text="暂无运行详情" />
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>stage</th>
                      <th>status</th>
                      <th>report</th>
                      <th>失败原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {day.runs.map((run) => (
                      <tr key={run.run_id}>
                        <td>{stageLabels[run.stage] ?? run.stage}</td>
                        <td>
                          <StatusBadge status={run.status} />
                        </td>
                        <td>{run.report_path ?? "-"}</td>
                        <td className={run.failure_reason ? "failure-cell" : ""}>
                          {run.failure_reason ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Section>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function StrategyComparisonPanel({
  comparison,
}: {
  comparison: DashboardStrategyComparison | null;
}): JSX.Element {
  return (
    <div className="trend-grid">
      <Section icon={Gauge} title="策略版本对比">
        {!comparison || comparison.items.length === 0 ? (
          <EmptyState text="暂无策略回放对比" />
        ) : (
          <div className="comparison-list">
            {comparison.items.map((item) => (
              <StrategyComparisonItemRow item={item} key={item.backtest_id} />
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function StrategyComparisonItemRow({
  item,
}: {
  item: DashboardStrategyComparisonItem;
}): JSX.Element {
  return (
    <div className="comparison-row">
      <div>
        <strong>{item.backtest_id}</strong>
        <span>{item.strategy_params_version}</span>
        <span>
          {item.provider} · {item.start_date} 至 {item.end_date}
        </span>
      </div>
      <div className="trend-meta">
        <span>胜率 {percent(item.win_rate)}</span>
        <span>回撤 {percent(item.max_drawdown)}</span>
        <span>收益 {percent(item.total_return)}</span>
        <span>拒绝率 {percent(item.risk_reject_rate)}</span>
        <span>质量失败率 {percent(item.data_quality_failure_rate)}</span>
        <span>失败天数 {item.failed_days}</span>
      </div>
    </div>
  );
}

function TrendPanels({ trends }: { trends: DashboardTrends }): JSX.Element {
  return (
    <div className="trend-grid">
      <Section icon={Activity} title="权益曲线">
        <EquityTrend points={trends.points} />
      </Section>
      <Section icon={Gauge} title="信号趋势">
        <SignalTrend points={trends.points} />
      </Section>
      <Section icon={ShieldCheck} title="风控拒绝原因">
        <RiskRejectReasons reasons={trends.risk_reject_reasons} />
      </Section>
      <Section icon={Database} title="数据质量趋势">
        <DataQualityTrend points={trends.points} />
      </Section>
    </div>
  );
}

function EquityTrend({ points }: { points: DashboardTrendPoint[] }): JSX.Element {
  const equityPoints = points.filter((point) => point.total_value !== null);
  const latest = equityPoints[equityPoints.length - 1];
  if (!latest) {
    return <EmptyState text="暂无权益曲线" />;
  }
  return (
    <div className="trend-block">
      <div className="trend-headline">
        <span>最新总资产</span>
        <strong>{money(latest.total_value)}</strong>
      </div>
      <MiniLineChart points={equityPoints} />
      <div className="trend-row-list">
        {equityPoints.map((point) => (
          <div className="trend-row" key={`equity-${point.trade_date}`}>
            <span>{point.trade_date}</span>
            <strong>{money(point.total_value)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniLineChart({ points }: { points: DashboardTrendPoint[] }): JSX.Element {
  const values = points.map((point) => Number(point.total_value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || 1;
  const width = 320;
  const height = 96;
  const coordinates = values.map((value, index) => {
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = height - 12 - ((value - min) / spread) * (height - 24);
    return { x, y };
  });
  const line = coordinates.map((point) => `${point.x},${point.y}`).join(" ");
  return (
    <svg
      aria-label="权益曲线图"
      className="line-chart"
      preserveAspectRatio="none"
      role="img"
      viewBox={`0 0 ${width} ${height}`}
    >
      <polyline points={line} />
      {coordinates.map((point, index) => (
        <circle
          cx={point.x}
          cy={point.y}
          key={`${points[index].trade_date}-${point.x}`}
          r="3"
        />
      ))}
    </svg>
  );
}

function SignalTrend({ points }: { points: DashboardTrendPoint[] }): JSX.Element {
  if (points.length === 0) {
    return <EmptyState text="暂无信号趋势" />;
  }
  const maxSignals = Math.max(...points.map((point) => point.signal_count), 1);
  return (
    <div className="trend-row-list">
      {points.map((point) => (
        <div className="trend-row stacked" key={`signal-${point.trade_date}`}>
          <div>
            <span>{point.trade_date}</span>
            <strong>{point.signal_count} 个信号</strong>
          </div>
          <div className="mini-bars" aria-hidden="true">
            <span
              className="mini-bar approved"
              style={{ width: `${(point.approved_count / maxSignals) * 100}%` }}
            />
            <span
              className="mini-bar rejected"
              style={{ width: `${(point.rejected_count / maxSignals) * 100}%` }}
            />
          </div>
          <div className="trend-meta">
            <span>通过 {point.approved_count}</span>
            <span>拒绝 {point.rejected_count}</span>
            <span>最高评分 {scoreOrDash(point.max_signal_score)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function RiskRejectReasons({ reasons }: { reasons: Record<string, number> }): JSX.Element {
  if (Object.keys(reasons).length === 0) {
    return <EmptyState text="暂无风控拒绝原因" />;
  }
  return <p className="reason-distribution">{distributionText(reasons)}</p>;
}

function DataQualityTrend({ points }: { points: DashboardTrendPoint[] }): JSX.Element {
  if (points.length === 0) {
    return <EmptyState text="暂无数据质量趋势" />;
  }
  return (
    <div className="trend-row-list">
      {points.map((point) => (
        <div className="trend-row stacked" key={`quality-${point.trade_date}`}>
          <div>
            <span>{point.trade_date}</span>
            <strong>source 失败率 {percent(point.source_failure_rate)}</strong>
          </div>
          <div className="trend-meta">
            <span>阻断 {point.blocked_count}</span>
            <span>warning {point.warning_count}</span>
            <span>可靠性 {point.reliability_status}</span>
            <span>缺口 {point.reliability_missing_market_bar_count}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function Section({
  children,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  icon: LucideIcon;
  title: string;
}): JSX.Element {
  return (
    <section className="panel">
      <h3>
        <Icon size={17} aria-hidden="true" />
        {title}
      </h3>
      {children}
    </section>
  );
}

function scoreOrDash(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return score(value);
}

function StatusBadge({ status }: { status: string }): JSX.Element {
  const className =
    status === "success" || status === "passed"
      ? "safe"
      : status === "failed"
        ? "danger"
        : status === "warning" || status === "skipped"
          ? "warning"
          : "neutral";
  const icon =
    status === "failed" || status === "warning" ? (
      <AlertTriangle size={13} aria-hidden="true" />
    ) : null;
  return (
    <span className={`badge ${className}`}>
      {icon}
      {statusLabels[status] ?? status}
    </span>
  );
}

function qualityStatusSummary(day: DashboardDay): string {
  if (day.data_quality_reports.some((report) => report.status === "failed")) {
    return "数据质量失败";
  }
  if (day.data_quality_reports.some((report) => report.status === "warning")) {
    return "数据质量警告";
  }
  if (day.data_quality_reports.length > 0) {
    return "数据质量通过";
  }
  return "无质量报告";
}

function reliabilityStatusSummary(day: DashboardDay): string {
  if (day.data_reliability_reports.some((report) => report.status === "failed")) {
    return "运行可靠性失败";
  }
  if (day.data_reliability_reports.some((report) => report.status === "warning")) {
    return "运行可靠性警告";
  }
  if (day.data_reliability_reports.some((report) => report.status === "skipped")) {
    return "非交易日跳过";
  }
  if (day.data_reliability_reports.length > 0) {
    return "运行可靠性通过";
  }
  return "无可靠性报告";
}

function DataQualityTable({ reports }: { reports: DashboardDataQualityReport[] }): JSX.Element {
  if (reports.length === 0) {
    return <EmptyState text="暂无数据质量报告" />;
  }
  return (
    <div className="quality-block">
      <table>
        <thead>
          <tr>
            <th>stage</th>
            <th>status</th>
            <th>失败率</th>
            <th>失败/空源</th>
            <th>缺失行情</th>
            <th>异常价格</th>
            <th>交易日</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((report) => (
            <tr key={`${report.run_id}-${report.stage}`}>
              <td>{stageLabels[report.stage] ?? report.stage}</td>
              <td>
                <StatusBadge status={report.status} />
              </td>
              <td>{percent(report.source_failure_rate)}</td>
              <td>
                {report.failed_source_count}/{report.empty_source_count}
              </td>
              <td>{report.missing_market_bar_count}</td>
              <td>{report.abnormal_price_count}</td>
              <td>{report.is_trade_date === null ? "-" : boolText(report.is_trade_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="issue-list">
        {reports.flatMap((report) =>
          report.issues.map((issue) => (
            <div
              className="issue-row"
              key={`${report.run_id}-${issue.check_name}-${issue.message}`}
            >
              <StatusBadge status={issue.severity === "error" ? "failed" : "warning"} />
              <span>{issue.source ?? "-"}</span>
              <span>{issue.symbol ?? "-"}</span>
              <strong>{issue.message}</strong>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ReliabilityPanel({
  day,
  reports,
}: {
  day: DashboardDay;
  reports: DashboardDataReliabilityReport[];
}): JSX.Element {
  if (reports.length === 0) {
    return (
      <div className="quality-block">
        <p className="muted">
          交易日历：
          {day.trading_calendar
            ? boolText(day.trading_calendar.is_trade_date)
            : "-"}
        </p>
        <EmptyState text="暂无运行可靠性报告" />
      </div>
    );
  }
  return (
    <div className="quality-block">
      <table>
        <thead>
          <tr>
            <th>status</th>
            <th>交易日</th>
            <th>source 失败率</th>
            <th>失败/空源</th>
            <th>近 30 交易日缺口</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((report) => (
            <tr key={`${report.run_id}-${report.trade_date}`}>
              <td>
                <StatusBadge status={report.status} />
              </td>
              <td>{report.is_trade_date === null ? "-" : boolText(report.is_trade_date)}</td>
              <td>{percent(report.source_failure_rate)}</td>
              <td>
                {report.failed_source_count}/{report.empty_source_count}
              </td>
              <td>{report.missing_market_bar_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="issue-list">
        {reports.flatMap((report) =>
          report.source_health.map((source) => (
            <div className="issue-row" key={`${report.run_id}-source-${source.source}`}>
              <StatusBadge status={source.status === "failed" ? "failed" : source.status} />
              <span>{source.source}</span>
              <span>{source.row_count} rows</span>
              <strong>{source.last_failure_reason ?? `失败率 ${percent(source.failure_rate)}`}</strong>
            </div>
          ))
        )}
        {reports.flatMap((report) =>
          report.market_bar_gaps.map((gap) => (
            <div className="issue-row" key={`${report.run_id}-gap-${gap.symbol}`}>
              <StatusBadge status="failed" />
              <span>{gap.symbol}</span>
              <span>{gap.missing_count} 天</span>
              <strong>{gap.missing_dates.join(", ")}</strong>
            </div>
          ))
        )}
        {reports.flatMap((report) =>
          report.issues.map((issue) => (
            <div
              className="issue-row"
              key={`${report.run_id}-${issue.check_name}-${issue.message}`}
            >
              <StatusBadge status={issue.severity === "error" ? "failed" : "warning"} />
              <span>{issue.source ?? "-"}</span>
              <span>{issue.symbol ?? "-"}</span>
              <strong>{issue.message}</strong>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function LLMAnalysisPanel({ analysis }: { analysis: DashboardLLMAnalysis | null }): JSX.Element {
  if (!analysis) {
    return <EmptyState text="暂无 LLM 盘前分析" />;
  }
  return (
    <div className="report">
      <p>
        <strong>{analysis.model}</strong>
      </p>
      <p>{analysis.summary}</p>
      <div className="llm-list">
        {analysis.key_points.map((point) => (
          <div className="llm-row" key={`point-${point}`}>
            <span>重点</span>
            <strong>{point}</strong>
          </div>
        ))}
        {analysis.risk_notes.map((note) => (
          <div className="llm-row" key={`risk-${note}`}>
            <span>风险</span>
            <strong>{note}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function OrdersTable({ orders }: { orders: DashboardPaperOrder[] }): JSX.Element {
  if (orders.length === 0) {
    return <EmptyState text="暂无盘中模拟订单" />;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>side</th>
          <th>symbol</th>
          <th>数量</th>
          <th>价格</th>
          <th>金额</th>
          <th>原因</th>
          <th>滑点</th>
          <th>真实交易</th>
        </tr>
      </thead>
      <tbody>
        {orders.map((order) => (
          <tr key={order.order_id}>
            <td>
              <span className={`side ${order.side}`}>{order.side}</span>
            </td>
            <td>{order.symbol}</td>
            <td>{order.quantity}</td>
            <td>{money(order.price)}</td>
            <td>{money(order.amount)}</td>
            <td>{order.reason}</td>
            <td>{order.slippage}</td>
            <td>
              <span className={`badge ${order.is_real_trade ? "danger" : "safe"}`}>
                {boolText(order.is_real_trade)}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PositionsTable({ positions }: { positions: DashboardPosition[] }): JSX.Element {
  if (positions.length === 0) {
    return <EmptyState text="暂无持仓" />;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>symbol</th>
          <th>status</th>
          <th>成本</th>
          <th>当前价</th>
          <th>盈亏</th>
          <th>持有天数</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((position) => (
          <tr key={`${position.run_id}-${position.symbol}`}>
            <td>{position.symbol}</td>
            <td>
              <span className={`badge ${position.status === "open" ? "safe" : "neutral"}`}>
                {position.status}
              </span>
            </td>
            <td>{money(position.entry_price)}</td>
            <td>{money(position.exit_price ?? position.current_price)}</td>
            <td className={Number(position.pnl_amount) >= 0 ? "positive" : "negative"}>
              {money(position.pnl_amount)} / {percent(position.pnl_pct)}
            </td>
            <td>{position.holding_days}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function EmptyState({ text }: { text: string }): JSX.Element {
  return <div className="empty">{text}</div>;
}

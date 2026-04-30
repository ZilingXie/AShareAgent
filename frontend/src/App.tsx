import {
  Activity,
  AlertTriangle,
  BriefcaseBusiness,
  ClipboardList,
  Database,
  FileText,
  ListChecks,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

import { fetchDashboardDay, fetchRuns } from "./api";
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
  DashboardPaperOrder,
  DashboardPosition,
  DashboardRun,
} from "./types";

const stageLabels: Record<string, string> = {
  pre_market: "盘前",
  intraday_watch: "盘中",
  post_market_review: "复盘",
};

const statusLabels: Record<string, string> = {
  success: "成功",
  failed: "失败",
};

export default function App(): JSX.Element {
  const [runs, setRuns] = useState<DashboardRun[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [day, setDay] = useState<DashboardDay | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadRuns(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const loadedRuns = await fetchRuns();
      setRuns(loadedRuns);
      setSelectedDate((current) => current ?? loadedRuns[0]?.trade_date ?? null);
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

  const selectedRuns = useMemo(
    () => runs.filter((run) => run.trade_date === selectedDate),
    [runs, selectedDate]
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
          {runs.length === 0 && !loading ? <EmptyState text="暂无 pipeline run" /> : null}
          {runs.map((run) => (
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
          <div className="status-strip">
            <span>{selectedRuns.length} 次运行</span>
            <span>{day?.paper_orders.length ?? 0} 笔模拟订单</span>
            <span>{day?.positions.length ?? 0} 个持仓状态</span>
          </div>
        </header>

        {error ? <div className="alert">{error}</div> : null}
        {loading ? <div className="loading">加载中</div> : null}

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

            <Section icon={Activity} title="模拟订单">
              <OrdersTable orders={day.paper_orders} />
            </Section>

            <Section icon={BriefcaseBusiness} title="当前持仓">
              <PositionsTable positions={day.positions} />
            </Section>

            <Section icon={FileText} title="复盘报告">
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

function StatusBadge({ status }: { status: string }): JSX.Element {
  const className = status === "success" ? "safe" : status === "failed" ? "danger" : "neutral";
  const icon = status === "failed" ? <AlertTriangle size={13} aria-hidden="true" /> : null;
  return (
    <span className={`badge ${className}`}>
      {icon}
      {statusLabels[status] ?? status}
    </span>
  );
}

function OrdersTable({ orders }: { orders: DashboardPaperOrder[] }): JSX.Element {
  if (orders.length === 0) {
    return <EmptyState text="暂无模拟订单" />;
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

import {
  Activity,
  AlertTriangle,
  BarChart3,
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

import {
  fetchBacktests,
  fetchDashboardDay,
  fetchDashboardTrends,
  fetchRuns,
  fetchStrategyComparison,
  fetchStrategyEvaluation,
  fetchStrategyEvaluations,
  fetchStrategyInsight,
  fetchStrategyInsights,
} from "./api";
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
  DashboardExecutionEvent,
  DashboardIntradaySourceHealth,
  DashboardLLMAnalysis,
  DashboardPaperOrder,
  DashboardPosition,
  DashboardRun,
  DashboardStrategyEvaluation,
  DashboardStrategyEvaluationVariant,
  DashboardStrategyInsight,
  DashboardStrategyInsightWindow,
  DashboardTrendPoint,
  DashboardTrends,
} from "./types";

type ActiveView = "daily" | "strategy" | "insights";

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
  rejected: "拒绝",
  filled: "成交",
  empty: "空数据",
};

export default function App(): JSX.Element {
  const [activeView, setActiveView] = useState<ActiveView>("daily");
  const [runs, setRuns] = useState<DashboardRun[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [rangeStart, setRangeStart] = useState<string | null>(null);
  const [rangeEnd, setRangeEnd] = useState<string | null>(null);
  const [day, setDay] = useState<DashboardDay | null>(null);
  const [trends, setTrends] = useState<DashboardTrends | null>(null);
  const [strategyComparison, setStrategyComparison] =
    useState<DashboardStrategyComparison | null>(null);
  const [strategyEvaluations, setStrategyEvaluations] = useState<
    DashboardStrategyEvaluation[]
  >([]);
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(null);
  const [strategyEvaluation, setStrategyEvaluation] =
    useState<DashboardStrategyEvaluation | null>(null);
  const [strategyInsights, setStrategyInsights] = useState<DashboardStrategyInsight[]>([]);
  const [selectedInsightId, setSelectedInsightId] = useState<string | null>(null);
  const [strategyInsight, setStrategyInsight] = useState<DashboardStrategyInsight | null>(null);
  const [loading, setLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(false);
  const [strategyEvaluationLoading, setStrategyEvaluationLoading] = useState(false);
  const [strategyInsightLoading, setStrategyInsightLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trendError, setTrendError] = useState<string | null>(null);
  const [strategyEvaluationError, setStrategyEvaluationError] = useState<string | null>(null);
  const [strategyInsightError, setStrategyInsightError] = useState<string | null>(null);

  async function loadRuns(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const loadedRuns = await fetchRuns(200);
      const loadedBacktests = await fetchBacktests(20);
      const loadedEvaluations = await fetchStrategyEvaluations(50);
      const loadedInsights = await fetchStrategyInsights(50);
      const tradeDates = [...new Set(loadedRuns.map((run) => run.trade_date))].sort();
      setRuns(loadedRuns);
      setSelectedDate((current) => current ?? loadedRuns[0]?.trade_date ?? null);
      setRangeStart((current) => current ?? tradeDates[0] ?? null);
      setRangeEnd((current) => current ?? tradeDates[tradeDates.length - 1] ?? null);
      setStrategyEvaluations(loadedEvaluations);
      setStrategyInsights(loadedInsights);
      setSelectedEvaluationId((current) =>
        current && loadedEvaluations.some((item) => item.evaluation_id === current)
          ? current
          : loadedEvaluations[0]?.evaluation_id ?? null
      );
      setSelectedInsightId((current) =>
        current && loadedInsights.some((item) => item.insight_id === current)
          ? current
          : loadedInsights[0]?.insight_id ?? null
      );
      const backtestIds = uniqueStrings(loadedBacktests.map((item) => item.backtest_id));
      if (backtestIds.length === 0) {
        setStrategyComparison(null);
      } else {
        setStrategyComparison(await fetchStrategyComparison(backtestIds));
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
    if (!selectedEvaluationId) {
      setStrategyEvaluation(null);
      return;
    }
    let active = true;
    setStrategyEvaluationLoading(true);
    setStrategyEvaluationError(null);
    fetchStrategyEvaluation(selectedEvaluationId)
      .then((loadedEvaluation) => {
        if (active) {
          setStrategyEvaluation(loadedEvaluation);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setStrategyEvaluationError(
            caught instanceof Error ? caught.message : "Dashboard API 请求失败"
          );
          setStrategyEvaluation(null);
        }
      })
      .finally(() => {
        if (active) {
          setStrategyEvaluationLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selectedEvaluationId]);

  useEffect(() => {
    if (!selectedInsightId) {
      setStrategyInsight(null);
      return;
    }
    let active = true;
    setStrategyInsightLoading(true);
    setStrategyInsightError(null);
    fetchStrategyInsight(selectedInsightId)
      .then((loadedInsight) => {
        if (active) {
          setStrategyInsight(loadedInsight);
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setStrategyInsightError(
            caught instanceof Error ? caught.message : "Dashboard API 请求失败"
          );
          setStrategyInsight(null);
        }
      })
      .finally(() => {
        if (active) {
          setStrategyInsightLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selectedInsightId]);

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
      <aside className="sidebar" aria-label="Dashboard navigation">
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
        <div className="view-toggle" aria-label="视图切换">
          <button
            className={activeView === "daily" ? "selected" : ""}
            onClick={() => setActiveView("daily")}
            type="button"
          >
            日常观察
          </button>
          <button
            className={activeView === "strategy" ? "selected" : ""}
            onClick={() => setActiveView("strategy")}
            type="button"
          >
            策略评估
          </button>
          <button
            className={activeView === "insights" ? "selected" : ""}
            onClick={() => setActiveView("insights")}
            type="button"
          >
            策略假设
          </button>
        </div>
        {activeView === "daily" ? (
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
                {run.failure_reason ? (
                  <span className="failure" title={run.failure_reason}>
                    {run.failure_reason}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        ) : activeView === "strategy" ? (
          <StrategyEvaluationSidebarList
            evaluations={strategyEvaluations}
            loading={loading}
            onSelect={setSelectedEvaluationId}
            selectedEvaluationId={selectedEvaluationId}
          />
        ) : (
          <StrategyInsightSidebarList
            insights={strategyInsights}
            loading={loading}
            onSelect={setSelectedInsightId}
            selectedInsightId={selectedInsightId}
          />
        )}
      </aside>

      <section className="content">
        <header className="topbar">
          {activeView === "daily" ? (
            <>
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
            </>
          ) : activeView === "strategy" ? (
            <>
              <div>
                <p className="eyebrow">策略评估批次</p>
                <h2>{selectedEvaluationId ? `批次 ${selectedEvaluationId}` : "-"}</h2>
              </div>
              <div className="status-strip">
                <span>{strategyEvaluations.length} 个评估批次</span>
                <span>{strategyEvaluation?.variant_count ?? 0} 个 variant</span>
                <span>{strategyEvaluation?.provider ?? "-"}</span>
                <span>
                  {strategyEvaluation?.recommendation.recommended_variant_ids.length ?? 0} 个推荐候选
                </span>
              </div>
            </>
          ) : (
            <>
              <div>
                <p className="eyebrow">策略假设批次</p>
                <h2>{selectedInsightId ? `批次 ${selectedInsightId}` : "-"}</h2>
              </div>
              <div className="status-strip">
                <span>{strategyInsights.length} 个假设批次</span>
                <span>{strategyInsight?.provider ?? "-"}</span>
                <span>{strategyInsight ? manualStatusLabel(strategyInsight.manual_status) : "-"}</span>
                <span>{strategyInsight?.recommended_variant_ids.length ?? 0} 个候选</span>
              </div>
            </>
          )}
        </header>

        {error ? <div className="alert">{error}</div> : null}
        {activeView === "daily" ? (
          <>
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

            <Section icon={AlertTriangle} title="成交失败">
              <ExecutionEventsTable events={day.execution_events} />
            </Section>

            <Section icon={Activity} title="分钟线源健康">
              <IntradaySourceHealthTable items={day.intraday_source_health} />
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
          </>
        ) : activeView === "strategy" ? (
          <>
            {strategyEvaluationError ? (
              <div className="alert">{strategyEvaluationError}</div>
            ) : null}
            {loading || strategyEvaluationLoading ? (
              <div className="loading">策略评估加载中</div>
            ) : null}
            <StrategyEvaluationDecisionView
              evaluation={strategyEvaluation}
              evaluations={strategyEvaluations}
            />
          </>
        ) : (
          <>
            {strategyInsightError ? <div className="alert">{strategyInsightError}</div> : null}
            {loading || strategyInsightLoading ? (
              <div className="loading">策略假设加载中</div>
            ) : null}
            <StrategyInsightDecisionView insight={strategyInsight} insights={strategyInsights} />
          </>
        )}
      </section>
    </main>
  );
}

function StrategyEvaluationSidebarList({
  evaluations,
  loading,
  onSelect,
  selectedEvaluationId,
}: {
  evaluations: DashboardStrategyEvaluation[];
  loading: boolean;
  onSelect: (evaluationId: string) => void;
  selectedEvaluationId: string | null;
}): JSX.Element {
  return (
    <div className="run-list">
      {evaluations.length === 0 && !loading ? <EmptyState text="无评估批次" /> : null}
      {evaluations.map((evaluation) => (
        <button
          className={`run-item ${evaluation.evaluation_id === selectedEvaluationId ? "selected" : ""}`}
          key={evaluation.evaluation_id}
          onClick={() => onSelect(evaluation.evaluation_id)}
          type="button"
        >
          <span className="run-date">{evaluation.evaluation_id}</span>
          <span className="run-meta">
            {evaluation.provider} · {evaluation.start_date} 至 {evaluation.end_date}
          </span>
          <span className="run-meta">
            {evaluation.variant_count} 个 variant · 推荐{" "}
            {evaluation.recommendation.recommended_variant_ids.length}
          </span>
        </button>
      ))}
    </div>
  );
}

function StrategyInsightSidebarList({
  insights,
  loading,
  onSelect,
  selectedInsightId,
}: {
  insights: DashboardStrategyInsight[];
  loading: boolean;
  onSelect: (insightId: string) => void;
  selectedInsightId: string | null;
}): JSX.Element {
  return (
    <div className="run-list">
      {insights.length === 0 && !loading ? <EmptyState text="无策略假设批次" /> : null}
      {insights.map((insight) => (
        <button
          className={`run-item ${insight.insight_id === selectedInsightId ? "selected" : ""}`}
          key={insight.insight_id}
          onClick={() => onSelect(insight.insight_id)}
          type="button"
        >
          <span className="run-date">{insight.insight_id}</span>
          <span className="run-meta">
            {insight.provider} · {insight.trade_date} · {manualStatusLabel(insight.manual_status)}
          </span>
          <span className="run-meta">
            {insight.hypotheses.length} 个假设 · {insight.recommended_variant_ids.length} 个候选
          </span>
        </button>
      ))}
    </div>
  );
}

function StrategyEvaluationDecisionView({
  evaluation,
  evaluations,
}: {
  evaluation: DashboardStrategyEvaluation | null;
  evaluations: DashboardStrategyEvaluation[];
}): JSX.Element {
  if (evaluations.length === 0) {
    return <EmptyState text="暂无策略评估" />;
  }
  if (!evaluation) {
    return <EmptyState text="暂无策略评估详情" />;
  }
  return (
    <div className="strategy-evaluation-grid">
      <Section icon={BarChart3} title="推荐结论">
        <div className="strategy-summary">
          <p className="summary-text">{evaluation.recommendation.summary}</p>
          <dl className="metrics strategy-metrics">
            <div>
              <dt>provider</dt>
              <dd>{evaluation.provider}</dd>
            </div>
            <div>
              <dt>日期范围</dt>
              <dd>
                {evaluation.start_date} 至 {evaluation.end_date}
              </dd>
            </div>
            <div>
              <dt>variant</dt>
              <dd>{evaluation.variant_count}</dd>
            </div>
            <div>
              <dt>推荐候选</dt>
              <dd>{evaluation.recommendation.recommended_variant_ids.length}</dd>
            </div>
          </dl>
          <p className="report-path">{evaluation.report_path}</p>
          <p className="safety-note">
            历史模拟评估，不构成投资建议，不自动修改策略参数。
          </p>
        </div>
      </Section>

      <Section icon={Gauge} title="Variant 排名">
        <StrategyEvaluationRanking variants={evaluation.variants} />
      </Section>

      <Section icon={AlertTriangle} title="不可推荐原因">
        <StrategyEvaluationReasons variants={evaluation.variants} />
      </Section>
    </div>
  );
}

function StrategyInsightDecisionView({
  insight,
  insights,
}: {
  insight: DashboardStrategyInsight | null;
  insights: DashboardStrategyInsight[];
}): JSX.Element {
  if (insights.length === 0) {
    return <EmptyState text="暂无策略假设" />;
  }
  if (!insight) {
    return <EmptyState text="暂无策略假设详情" />;
  }
  return (
    <div className="strategy-evaluation-grid">
      <Section icon={BarChart3} title="策略假设">
        <div className="strategy-summary">
          <p className="summary-text">{insight.summary}</p>
          <dl className="metrics strategy-metrics">
            <div>
              <dt>provider</dt>
              <dd>{insight.provider}</dd>
            </div>
            <div>
              <dt>交易日</dt>
              <dd>{insight.trade_date}</dd>
            </div>
            <div>
              <dt>人工状态</dt>
              <dd>{manualStatusLabel(insight.manual_status)}</dd>
            </div>
            <div>
              <dt>候选</dt>
              <dd>{insight.recommended_variant_ids.length}</dd>
            </div>
          </dl>
          <p className="report-path">{insight.report_path}</p>
          <p className="safety-note">
            LLM 只提出假设，代码回测验证，不自动修改策略参数。
          </p>
        </div>
      </Section>

      <Section icon={ListChecks} title="LLM 归因">
        <ul className="issue-list compact-list">
          {insight.attribution.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Section>

      <Section icon={Gauge} title="假设与参数变更">
        <StrategyInsightExperiments insight={insight} />
      </Section>

      <Section icon={ShieldCheck} title="三窗口验证">
        <StrategyInsightWindows windows={insight.evaluation_windows} />
      </Section>
    </div>
  );
}

function StrategyInsightExperiments({
  insight,
}: {
  insight: DashboardStrategyInsight;
}): JSX.Element {
  return (
    <div className="strategy-ranking">
      {insight.hypotheses.map((hypothesis) => (
        <div className="strategy-variant-row" key={`${hypothesis.area}-${hypothesis.direction}`}>
          <div className="strategy-variant-head">
            <div>
              <strong>{hypothesis.area}</strong>
              <span>{hypothesis.direction}</span>
              <span>{hypothesis.reason}</span>
              <span>{hypothesis.risk}</span>
            </div>
          </div>
        </div>
      ))}
      {insight.experiments.map((experiment) => (
        <div className="strategy-variant-row" key={`${experiment.param}-${experiment.name}`}>
          <div className="strategy-variant-head">
            <div>
              <strong>{experiment.name}</strong>
              <span>
                {experiment.param} = {experiment.candidate_value}
              </span>
              <span>{experiment.variant_id ?? "-"}</span>
            </div>
            <span
              className={`badge ${
                experiment.policy_status === "approved" ? "safe" : "danger"
              }`}
            >
              {experiment.policy_status}
            </span>
          </div>
          <div className="trend-meta strategy-variant-metrics">
            <span>{jsonPreview(experiment.overrides)}</span>
            {experiment.policy_reason ? <span>{experiment.policy_reason}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyInsightWindows({
  windows,
}: {
  windows: DashboardStrategyInsightWindow[];
}): JSX.Element {
  if (windows.length === 0) {
    return <EmptyState text="暂无多窗口评估" />;
  }
  return (
    <div className="strategy-ranking">
      {windows.map((window) => (
        <div className="strategy-variant-row" key={window.evaluation_id}>
          <div className="strategy-variant-head">
            <div>
              <strong>{window.window_trade_days} 日</strong>
              <span>{window.evaluation_id}</span>
              <span>{window.report_path}</span>
            </div>
            <span className="badge neutral">
              通过 {window.passed_variant_ids.length}
            </span>
          </div>
          <div className="trend-meta strategy-variant-metrics">
            <span>评估推荐 {listText(window.recommended_variant_ids)}</span>
            <span>门槛通过 {listText(window.passed_variant_ids)}</span>
            {Object.entries(window.failed_variant_reasons).map(([variantId, reasons]) => (
              <span key={variantId}>
                {variantId}: {listText(reasons)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyEvaluationRanking({
  variants,
}: {
  variants: DashboardStrategyEvaluationVariant[];
}): JSX.Element {
  const ranked = [...variants].sort(
    (left, right) =>
      right.total_return - left.total_return ||
      right.signal_hit_rate - left.signal_hit_rate ||
      left.failed_days - right.failed_days
  );
  return (
    <div className="strategy-ranking">
      {ranked.map((variant) => (
        <div className="strategy-variant-row" key={variant.id}>
          <div className="strategy-variant-head">
            <div>
              <strong>{variant.label}</strong>
              <span>
                {variant.id} · {variant.version}
              </span>
              <span>{variant.backtest_id}</span>
            </div>
            {variant.is_recommended ? (
              <span className="badge safe">推荐候选</span>
            ) : (
              <span className="badge neutral">{variant.success ? "已评估" : "失败"}</span>
            )}
          </div>
          <div className="trend-meta strategy-variant-metrics">
            <span>收益 {percent(variant.total_return)}</span>
            <span>命中率 {percent(variant.signal_hit_rate)}</span>
            <span>回撤 {percent(variant.max_drawdown)}</span>
            <span>source 失败率 {percent(variant.source_failure_rate)}</span>
            <span>质量失败率 {percent(variant.data_quality_failure_rate)}</span>
            <span>订单 {variant.order_count}</span>
            <span>成交失败 {variant.execution_failed_count}</span>
            <span>
              持仓 open/closed {variant.open_position_count}/{variant.closed_trade_count}
            </span>
            <span>风控通过/拒绝 {variant.risk_approved_count}/{variant.risk_rejected_count}</span>
            <span>失败天数 {variant.failed_days}</span>
            <span>持仓盈亏 {money(variant.holding_pnl)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyEvaluationReasons({
  variants,
}: {
  variants: DashboardStrategyEvaluationVariant[];
}): JSX.Element {
  const rows = variants.filter((variant) => variant.not_recommended_reasons.length > 0);
  if (rows.length === 0) {
    return <EmptyState text="暂无不可推荐原因" />;
  }
  return (
    <div className="issue-list">
      {rows.map((variant) => (
        <div className="strategy-reason-row" key={variant.id}>
          <div>
            <strong>{variant.label}</strong>
            <span>{variant.id}</span>
          </div>
          <ul>
            {variant.not_recommended_reasons.map((reason) => (
              <li key={`${variant.id}-${reason}`}>{reason}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function StrategyComparisonPanel({
  comparison,
}: {
  comparison: DashboardStrategyComparison | null;
}): JSX.Element {
  const items = comparison ? uniqueStrategyComparisonItems(comparison.items) : [];
  return (
    <div className="trend-grid">
      <Section icon={Gauge} title="策略版本对比">
        {items.length === 0 ? (
          <EmptyState text="暂无策略回放对比" />
        ) : (
          <div className="comparison-list">
            {items.map((item) => (
              <StrategyComparisonItemRow item={item} key={item.backtest_id} />
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (normalized === "" || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    unique.push(normalized);
  }
  return unique;
}

function manualStatusLabel(status: DashboardStrategyInsight["manual_status"]): string {
  if (status === "accepted") {
    return "已接受";
  }
  if (status === "rejected") {
    return "已拒绝";
  }
  return "待复核";
}

function jsonPreview(value: Record<string, unknown>): string {
  return JSON.stringify(value);
}

function uniqueStrategyComparisonItems(
  items: DashboardStrategyComparisonItem[]
): DashboardStrategyComparisonItem[] {
  const seen = new Set<string>();
  const unique: DashboardStrategyComparisonItem[] = [];
  for (const item of items) {
    if (seen.has(item.backtest_id)) {
      continue;
    }
    seen.add(item.backtest_id);
    unique.push(item);
  }
  return unique;
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
      : status === "failed" || status === "rejected"
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
          <th>成交依据</th>
          <th>价格时间点</th>
          <th>估价方法</th>
          <th>日线兜底</th>
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
            <td>{order.execution_source ?? "-"}</td>
            <td>{order.execution_timestamp ?? "-"}</td>
            <td>{order.execution_method ?? "-"}</td>
            <td>
              <span className={`badge ${order.used_daily_fallback ? "danger" : "safe"}`}>
                {boolText(order.used_daily_fallback)}
              </span>
            </td>
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

function ExecutionEventsTable({ events }: { events: DashboardExecutionEvent[] }): JSX.Element {
  const rejectedEvents = events.filter((event) => event.status === "rejected");
  if (rejectedEvents.length === 0) {
    return <EmptyState text="暂无成交失败" />;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>side</th>
          <th>symbol</th>
          <th>status</th>
          <th>估价方法</th>
          <th>成交依据</th>
          <th>参考价</th>
          <th>日线兜底</th>
          <th>失败原因</th>
        </tr>
      </thead>
      <tbody>
        {rejectedEvents.map((event) => (
          <tr key={`${event.trade_date}-${event.side}-${event.symbol}-${event.failure_reason}`}>
            <td>
              <span className={`side ${event.side}`}>{event.side}</span>
            </td>
            <td>{event.symbol}</td>
            <td>
              <StatusBadge status={event.status} />
            </td>
            <td>{event.execution_method}</td>
            <td>{event.execution_source ?? "-"}</td>
            <td>{event.reference_price ? money(event.reference_price) : "-"}</td>
            <td>
              <span className={`badge ${event.used_daily_fallback ? "danger" : "safe"}`}>
                {boolText(event.used_daily_fallback)}
              </span>
            </td>
            <td className="failure-cell">{event.failure_reason ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function IntradaySourceHealthTable({
  items,
}: {
  items: DashboardIntradaySourceHealth[];
}): JSX.Element {
  if (items.length === 0) {
    return <EmptyState text="暂无分钟线源健康记录" />;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>source</th>
          <th>symbol</th>
          <th>status</th>
          <th>rows</th>
          <th>retry</th>
          <th>timeout</th>
          <th>最后错误</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={`${item.run_id}-${item.source}-${item.symbol}-${item.status}`}>
            <td>{item.source}</td>
            <td>{item.symbol}</td>
            <td>
              <StatusBadge status={item.status} />
            </td>
            <td>{item.returned_rows}</td>
            <td>{item.retry_attempts ?? "-"}</td>
            <td>{item.timeout_seconds ?? "-"}</td>
            <td className={item.last_error ? "failure-cell" : ""}>{item.last_error ?? "-"}</td>
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

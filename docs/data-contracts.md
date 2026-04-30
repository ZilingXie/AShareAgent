# AShareAgent 数据契约

当前状态：已落地第一版 domain models、provider 契约、真实 DataCollector 入口、DataQualityAgent 质量报告、PostgreSQL schema、核心 pipeline 持久化、策略参数版本审计、DashboardQueryAgent 只读 DTO 契约、复盘指标 DTO、日期范围趋势 DTO 和 dashboard API DTO。

## DataProvider 原则

- 业务逻辑依赖统一 `DataProvider` 接口。
- 不直接把业务逻辑绑定到 AKShare、TuShare 或其他外部数据源。
- `MockProvider` 和真实 provider 应返回同一类标准 domain models。
- 默认测试不访问外网；真实数据源测试必须单独标记。
- `ASHARE_PROVIDER=akshare` 只读取 `configs/universe.yml` 中 `enabled=true` 的固定池资产。
- `AKShareProvider` 的日线行情标准化为统一 `MarketBar`：ETF 使用 `fund_etf_hist_sina`，A 股使用 `stock_zh_a_daily`，返回的英文字段会映射为 `date/open/high/low/close/volume/amount` 对应的 domain 字段。

## 审计字段原则

核心数据模型应保留足够的审计信息，至少覆盖：

- 数据来源。
- 数据时间。
- 采集或运行时间。
- `run_id`。
- `trade_date`。
- 股票代码或市场标识。
- 决策原因。
- 失败原因或排除原因。
- 策略参数版本和参数快照。

## 核心模型

当前代码中的标准模型集中在 `src/ashare_agent/domain.py`：

- 数据输入：`Asset`、`MarketBar`、`AnnouncementItem`、`NewsItem`、`PolicyItem`、`IndustrySnapshot`。
- 分析输出：`AnnouncementEvent`、`TechnicalIndicator`、`MarketRegime`、`LLMAnalysis`。
- 数据质量：`DataQualityIssue`、`DataQualityReport`。
- 信号与风控：`WatchlistCandidate`、`Signal`、`RiskDecision`、`ExitDecision`。
- 模拟交易：`PaperOrder`、`PaperPosition`、`PortfolioSnapshot`、`ReviewReport`。
- 流程审计：`SourceSnapshot`、`MarketDataset`、`PipelineRunContext`、`AgentResult`。

## 公告分析规则契约

`AnnouncementAnalyzer` 保持输出 `AnnouncementEvent`，不新增运行时字段或数据库表。当前规则用标题和来源分类做可解释判断：分红归为 `distribution`，减持归为 `share_reduction`，诉讼归为 `litigation`，处罚或立案归为 `penalty`，资产重组归为 `restructuring`，风险提示、退市或亏损风险归为 `risk`。减持、诉讼、处罚和风险提示默认作为排除类负面事件；资产重组默认重大，情绪仍由标题关键词决定。固定样本放在 `tests/fixtures/announcement_golden_cases.yml`，每条样本用 `case_id` 追踪误判。

## 策略参数契约

默认策略参数配置位于 `configs/strategy_params.yml`，由 `StrategyParamsAgent` 加载和校验。配置必须包含显式 `version`、`risk` 和 `paper_trader` 两组参数。百分比字段必须在 0 到 1 之间，最多持有交易日不能小于最少持有交易日。每次 `pipeline_runs.payload` 必须写入：

- `strategy_params_version`：本次运行使用的配置版本。
- `strategy_params_snapshot`：JSON-safe 完整参数快照，Decimal 以字符串保存，黑名单以排序列表保存。

## PostgreSQL schema

本地开发复用现有 Podman PostgreSQL 的 `supportportal` 数据库，但所有 AShareAgent 对象都放在独立 `ashare_agent` schema。Alembic 版本表固定为 `ashare_agent.alembic_version`，避免污染共享数据库中其他项目的迁移状态。若 schema 已存在但缺少该版本表，迁移会停止，避免在状态不明的共享库里继续写入。

Alembic 迁移创建以下表分组：

- `pipeline_runs`
- `universe_assets`
- `raw_source_snapshots`
- `market_bars`
- `announcements`
- `news_items`
- `policy_items`
- `industry_snapshots`
- `technical_indicators`
- `data_quality_reports`
- `llm_analyses`
- `watchlist_candidates`
- `signals`
- `risk_decisions`
- `paper_orders`
- `paper_positions`
- `portfolio_snapshots`
- `review_reports`
- `artifacts`

当前 repository 已将核心运行结果写入专表，`pipeline_runs.payload` 额外保存策略参数版本和完整参数快照，不新增数据库列：

- `pre-market` 先写入 `universe_assets`、`raw_source_snapshots`、`market_bars`、`announcements`、`news_items`、`policy_items`，再写入 `data_quality_reports`；质量通过或仅警告后继续写 `technical_indicators`、`pipeline_runs`、`llm_analyses`、`watchlist_candidates`、`signals`、`risk_decisions` 和 `artifacts`。
- `intraday-watch` 写入 `pipeline_runs` 和 `artifacts`。
- `post-market-review` 从 repository 读取当日最新 pre-market 风控决策、开放持仓、最新现金和当日已有模拟订单；若当前 pipeline 没有内存中的 market dataset，会重新采集并写入 raw/source 专表，再写入 `paper_orders`、`paper_positions`、`portfolio_snapshots`、`review_reports`、`pipeline_runs` 和 `artifacts`。
- `paper_positions` 中的 payload 可保存 `open` 和 `closed` 状态；repository 恢复开放持仓时只返回每个 symbol 的最新 `open` payload。

真实 provider 下 `universe`、`market_bars`、`trade_calendar` 是必需源；这些源失败、必需源空数据、交易日缺失当日行情或行情价格异常时，`pre-market` 会先保存失败的 `raw_source_snapshots`、`data_quality_reports` 和失败的 `pipeline_runs`，再明确失败。交易日历本轮只保存采集快照和摘要，不新增 `trading_calendar` 表。

## 数据质量契约

`DataQualityReport` 每个 pipeline run 写一条，字段包括 `stage`、`status`、`source_failure_rate`、`total_sources`、`failed_source_count`、`empty_source_count`、`missing_market_bar_count`、`abnormal_price_count`、`is_trade_date`、`issues` 和 `created_at`。

`DataQualityIssue` 使用 `severity`、`check_name`、`source`、`symbol`、`message` 和 `metadata` 描述具体问题。`severity=error` 会让报告状态变为 `failed`；只有 warning 时报告状态为 `warning`；无 issue 时为 `passed`。

质量规则固定如下：

- source 失败率为失败 source 数除以 source 总数。
- 必需源失败或空数据为 error，非必需源失败或空数据为 warning。
- 交易日内每个 enabled asset 必须存在当日 `MarketBar`；非交易日跳过缺失行情失败检查，只记录 warning。
- OHLC 必须为正，`high/low` 必须覆盖开收盘价格，成交量和成交额不能为负。
- 同 symbol 相邻收盘价跳变超过 35% 记为异常价格。

`artifacts` 仍保留为报告和聚合 payload 的审计表；专表 payload 是后续连续模拟交易和只读观察台的数据基础。

## Dashboard 查询契约

- `DashboardQueryAgent` 是 dashboard 读取 pipeline 数据的稳定入口。
- `src/ashare_agent/dashboard.py` 只提供 API 兼容封装：`DashboardQueryService.list_runs()` 委托 `DashboardQueryAgent.list_pipeline_runs()`，趋势查询沿用 `DashboardQueryAgent.trends()`，避免出现两套查询逻辑。
- dashboard/API/frontend 不直接解析 `payload`；只能消费查询层返回的 DTO。
- DTO 中日期使用 ISO 字符串，金额和 Decimal 使用字符串，评分使用 `float`，列表字段保持列表。
- `day_summary(trade_date)` 使用当日最新成功 `pre_market` run 的 watchlist、signals 和 risk decisions；orders、review reports 和 source snapshots 按当日查询；positions 和 portfolio snapshots 使用截至当日的最新状态。
- DTO 覆盖 pipeline runs、watchlist、signals、risk decisions、paper orders、positions、portfolio snapshot、review report、review metrics、source snapshots、data quality reports 和 range trends。
- `trends(start_date, end_date)` 使用闭区间日期范围，输出 `DashboardTrendSummary`：
  - `points` 按日期升序排列，只包含范围内有 pipeline run、组合快照或数据质量报告的日期。
  - 权益曲线使用范围内每个交易日最新一条 `portfolio_snapshots.total_value`；没有快照时为 `null`。
  - 信号趋势使用当天最新成功 `pre_market` run 的 `signals`，统计 `signal_count` 和 `max_signal_score`。
  - 通过/拒绝使用同一最新成功 `pre_market` run 的 `risk_decisions`，统计 `approved_count` 和 `rejected_count`。
  - `risk_reject_reasons` 只统计被拒绝风控决策中的 `reasons` 原文次数，不做归类或改写。
  - 数据质量趋势按天统计 `source_failure_rate` 的最大值、`status=failed` 的阻断次数，以及 `severity=warning` 的 warning issue 次数。
- dashboard/API/frontend 只能展示质量结果，不修改数据或触发交易。
- `holding_days` 第一版用自然日差计算；后续如果新增结构化交易日历表，再替换为交易日口径。
- `DashboardReviewReport.metrics` 是截至所选交易日的累计复盘指标，字段包括：
  - `realized_pnl`：只统计已关闭模拟持仓，按 `(exit_price - entry_price) * quantity` 计算，DTO 用金额字符串。
  - `win_rate`：盈利 closed trade 数 / closed trade 总数；无 closed trade 时为 `0`。
  - `average_holding_days`：只统计 closed trade，沿用自然日口径；无 closed trade 时为 `0`。
  - `sell_reason_distribution`：按截至所选日所有模拟卖单的 `reason` 原文计数，不做额外归类。
  - `max_drawdown`：按截至所选日 `portfolio_snapshots.total_value` 序列计算峰值到谷值最大跌幅，输出正数百分比小数。
- `PaperOrder.is_real_trade` 必须保留在 DTO 和 API JSON 中；正常模拟订单必须为 `False`，前端也会显式展示该字段。
- 查询层遇到缺字段、字段类型错误、未知枚举或 `paper_orders.is_real_trade=True` 时必须显式失败，不能补默认值或静默兜底；复盘指标计算也遵守同一规则。

## 后续维护

涉及数据模型、provider 契约、字段含义、数据质量或审计要求的变化，必须同步更新本文。

# AShareAgent 数据契约

当前状态：已落地第一版 domain models、provider 契约、真实 DataCollector 入口、分钟线成交估价审计、DataQualityAgent 质量报告、DataReliabilityAgent 运行可靠性报告、结构化交易日历、PostgreSQL schema、核心 pipeline 持久化、策略参数版本审计、策略实验 Markdown 报告、backtest 状态隔离、DashboardQueryAgent 只读 DTO 契约、LLM 盘前分析 DTO、复盘指标 DTO、日期范围趋势 DTO、策略对比 DTO 和 dashboard API DTO。

## DataProvider 原则

- 业务逻辑依赖统一 `DataProvider` 接口。
- 不直接把业务逻辑绑定到 AKShare、TuShare 或其他外部数据源。
- `MockProvider` 和真实 provider 应返回同一类标准 domain models。
- 默认测试不访问外网；真实数据源测试必须单独标记。
- `ASHARE_PROVIDER=akshare` 只读取 `configs/universe.yml` 中 `enabled=true` 的固定池资产。
- `AKShareProvider` 的日线行情标准化为统一 `MarketBar`：ETF 使用 `fund_etf_hist_sina`，A 股使用 `stock_zh_a_daily`，返回的英文字段会映射为 `date/open/high/low/close/volume/amount` 对应的 domain 字段。
- `DataProvider.get_intraday_bars(trade_date, symbols, period="1")` 返回统一 `IntradayBar`，用于盘中模拟成交估价。默认真实分钟线源为 `ASHARE_INTRADAY_SOURCE=akshare_em`；可显式配置 `akshare_sina` 或 `akshare_em,akshare_sina` source chain。`akshare_em` 直连 EastMoney `trends2/get`，`akshare_sina` 直连 Sina `CN_MarketDataService.getKLineData`，都只支持 1 分钟 K 线；timeout、重试次数和退避由 `ASHARE_INTRADAY_TIMEOUT_SECONDS`、`ASHARE_INTRADAY_RETRY_ATTEMPTS`、`ASHARE_INTRADAY_RETRY_BACKOFF_SECONDS` 控制。
- 分钟线源链路整体不可用必须抛 `DataProviderError`，错误 metadata 至少包含 `intraday_source`、`failed_symbol`、`retry_attempts`、`timeout_seconds`、最后失败原因和 `source_attempts`；不能静默返回空数据或切回 Mock。至少一个源正常响应但单个 symbol 当日无分钟线时返回该 symbol 的空结果，由执行估价层生成 rejected execution event。

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
- 模拟成交依据、估价方法、价格时间点和是否使用日线兜底。
- 策略参数版本和参数快照。
- 运行模式 `run_mode` 和回放批次 `backtest_id`。

## 核心模型

当前代码中的标准模型集中在 `src/ashare_agent/domain.py`：

- 数据输入：`Asset`、`MarketBar`、`IntradayBar`、`AnnouncementItem`、`NewsItem`、`PolicyItem`、`IndustrySnapshot`。
- 分析输出：`AnnouncementEvent`、`TechnicalIndicator`、`MarketRegime`、`LLMAnalysis`。
- 数据质量与可靠性：`DataQualityIssue`、`DataQualityReport`、`TradingCalendarDay`、`DataReliabilityIssue`、`DataSourceHealth`、`MarketBarGap`、`DataReliabilityReport`。
- 信号与风控：`WatchlistCandidate`、`Signal`、`RiskDecision`、`ExitDecision`。
- 模拟交易：`PaperOrder`、`PaperPosition`、`PortfolioSnapshot`、`ReviewReport`、`ExecutionEvent`。
- 流程审计：`SourceSnapshot`、`MarketDataset`、`PipelineRunContext`、`AgentResult`。

## 公告分析规则契约

`AnnouncementAnalyzer` 保持输出 `AnnouncementEvent`，不新增运行时字段或数据库表。当前规则用标题和来源分类做可解释判断：分红归为 `distribution`，减持归为 `share_reduction`，诉讼归为 `litigation`，处罚或立案归为 `penalty`，资产重组归为 `restructuring`，风险提示、退市或亏损风险归为 `risk`。减持、诉讼、处罚和风险提示默认作为排除类负面事件；资产重组默认重大，情绪仍由标题关键词决定。固定样本放在 `tests/fixtures/announcement_golden_cases.yml`，每条样本用 `case_id` 追踪误判。

## 策略参数契约

默认策略参数配置位于 `configs/strategy_params.yml`，由 `StrategyParamsAgent` 加载和校验。配置必须包含显式 `version`、`risk`、`paper_trader` 和 `signal` 四组参数。百分比字段必须在 0 到 1 之间，最多持有交易日不能小于最少持有交易日，`signal.max_daily_signals` 必须大于等于 1。每次 `pipeline_runs.payload` 必须写入：

- `strategy_params_version`：本次运行使用的配置版本。
- `strategy_params_snapshot`：JSON-safe 完整参数快照，Decimal 以字符串保存，黑名单以排序列表保存。

`signal` 参数控制 SignalEngine 的 `min_score`、`max_daily_signals` 和 `weights.technical/market/event/risk_penalty`。每条 `watchlist_candidates` 和 `signals` payload 也必须保留完整策略版本和快照；历史数据缺失这些字段时不参与策略版本对比。

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
- `data_reliability_reports`
- `trading_calendar`
- `llm_analyses`
- `watchlist_candidates`
- `signals`
- `risk_decisions`
- `paper_orders`
- `paper_positions`
- `portfolio_snapshots`
- `review_reports`
- `artifacts`

当前 repository 已将核心运行结果写入专表，payload 额外保存策略参数版本、完整参数快照、`run_mode` 和 `backtest_id`，不新增数据库列：

- `pre-market` 先写入 `universe_assets`、`raw_source_snapshots`、`trading_calendar`、`market_bars`、`announcements`、`news_items`、`policy_items`，再写入 `data_quality_reports`；质量通过或仅警告后继续写 `technical_indicators`、`pipeline_runs`、`llm_analyses`、`watchlist_candidates`、`signals`、`risk_decisions` 和 `artifacts`。
- `intraday-watch` 从 repository 读取同日成功 `pre-market` 风控决策、开放持仓、最新现金和当日已有模拟订单；当日已有模拟订单只认同日成功 `intraday_watch` run 生成的 `paper_orders`。若当前 pipeline 没有内存中的 market dataset，会重新采集并写入 raw/source 专表和 `trading_calendar`。执行模拟买卖前会按获批买入 symbol 和当前 open position symbol 采集 1 分钟 K 线，只写 `raw_source_snapshots(source=intraday_bars)` 审计，不新增分钟线专表。snapshot metadata 必须记录 `intraday_source`、`requested_symbols`、`returned_symbols`、`missing_symbols`、`period`、`timeout_seconds`、`retry_attempts` 和 `source_attempts`；链路失败时还要记录 `failed_symbol` 和最后失败原因。成功成交写入 `paper_orders`、`paper_positions`、`portfolio_snapshots`、`pipeline_runs` 和 `artifacts`；同日重复运行不会重复生成买卖订单。
- 模拟成交契约：`IntradayPriceEstimator` 固定选择当日首个有效 1 分钟 K 线；有效 K 线必须有 timestamp、正数 OHLC、`volume > 0` 且 `amount > 0`。买入遇涨停、卖出遇跌停、缺少分钟线或无有效成交量时，不写 `paper_orders`，只在 `intraday_watch` artifact / pipeline payload 的 `execution_events` 中记录 `status=rejected`、失败原因、估价方法和 `used_daily_fallback=false`。成功 `PaperOrder` payload 必须包含 `execution_source`、`execution_timestamp`、`execution_method`、`reference_price`、`used_daily_fallback=false` 和空的 `execution_failure_reason`；历史订单缺少这些字段时读取层按可选字段兼容。
- `post-market-review` 不新增 `paper_orders`，只读取同日成功 `intraday_watch` run 生成的盘中订单和持仓，执行收盘盯市，再写入 `paper_positions`、`portfolio_snapshots`、`review_reports`、`pipeline_runs` 和 `artifacts`。盘后还会生成 `strategy-experiment.md`，并在 `post_market_review` artifact 与 pipeline run payload 中记录 `new_order_count=0`、`reviewed_order_count` 和 `experiment_report_path`；`reviewed_order_count` 不统计旧流程遗留的 `post_market_review` 订单。
- 历史兼容规则：旧数据库中已经存在的 `post_market_review` 订单不删除、不迁移；dashboard “盘中模拟订单”、盘后 `reviewed_orders` 和复盘订单统计只读取可关联到同日成功 `intraday_watch` run 的订单。
- `daily-run` 先采集并 upsert 结构化 `trading_calendar`；非交易日写 `pipeline_runs(stage=daily_run,status=skipped)` 和 `data_reliability_reports` 后退出；交易日依次运行盘前、盘中和复盘，并在成功或失败后写 `data_reliability_reports` 和 `daily_run` 审计。
- `paper_positions` 中的 payload 可保存 `open` 和 `closed` 状态；repository 恢复开放持仓时只返回每个 symbol 的最新 `open` payload。
- `backtest` 不新增表；每个交易日按 `pre_market -> intraday_watch -> post_market_review` 执行，每条回放 payload 使用 `run_mode=backtest` 和同一个 `backtest_id`。repository 恢复持仓、订单、现金和最新 snapshot 时按运行模式隔离，普通 `run_mode=normal` 不读取回放状态。

真实 provider 下 `universe`、`market_bars`、`trade_calendar` 是必需源；这些源失败、必需源空数据、交易日缺失近 30 个交易日行情或行情价格异常时，`pre-market` 会先保存失败的 `raw_source_snapshots`、`data_quality_reports` 和失败的 `pipeline_runs`，再明确失败。

`trading_calendar` 是结构化日历事实表，字段包含 `calendar_date`、`is_trade_date`、`source`、`collected_at` 和 `created_at`。DataCollector 会把 provider 返回的交易日列表展开为连续日期行，列表内日期标记为交易日，范围内其他日期标记为非交易日；同一 `calendar_date/source` 重复写入时 upsert。

## 数据质量契约

`DataQualityReport` 每个 pipeline run 写一条，字段包括 `stage`、`status`、`source_failure_rate`、`total_sources`、`failed_source_count`、`empty_source_count`、`missing_market_bar_count`、`abnormal_price_count`、`is_trade_date`、`issues` 和 `created_at`。

`DataQualityIssue` 使用 `severity`、`check_name`、`source`、`symbol`、`message` 和 `metadata` 描述具体问题。`severity=error` 会让报告状态变为 `failed`；只有 warning 时报告状态为 `warning`；无 issue 时为 `passed`。

质量规则固定如下：

- source 失败率为失败 source 数除以 source 总数。
- 必需源失败或空数据为 error，非必需源失败或空数据为 warning。
- 交易日内每个 enabled asset 必须存在近 30 个交易日的 `MarketBar`；非交易日跳过缺失行情失败检查，只记录 warning。
- OHLC 必须为正，`high/low` 必须覆盖开收盘价格，成交量和成交额不能为负。
- 同 symbol 相邻收盘价跳变超过 35% 记为异常价格。

`artifacts` 仍保留为报告和聚合 payload 的审计表；专表 payload 是后续连续模拟交易和只读观察台的数据基础。

## 运行可靠性契约

`DataReliabilityReport` 每个 `daily-run` 写一条，字段包括 `status`、`is_trade_date`、`lookback_trade_days`、`total_sources`、`failed_source_count`、`empty_source_count`、`source_failure_rate`、`missing_market_bar_count`、`source_health`、`market_bar_gaps`、`issues` 和 `created_at`。

`DataSourceHealth` 按 source 聚合当日 `raw_source_snapshots`，记录 `status`、`total_snapshots`、`failed_snapshots`、`empty_snapshots`、`row_count`、`failure_rate`、`last_failure_reason` 和是否必需源。

`MarketBarGap` 按 symbol 记录近 30 个交易日缺失行情日期。交易日缺口让可靠性报告 `status=failed`；非交易日报告 `status=skipped`，不检查当日行情缺口，也不更新模拟交易状态。

## Dashboard 查询契约

- `DashboardQueryAgent` 是 dashboard 读取 pipeline 数据的稳定入口。
- `src/ashare_agent/dashboard.py` 只提供 API 兼容封装：`DashboardQueryService.list_runs()` 委托 `DashboardQueryAgent.list_pipeline_runs()`，趋势查询沿用 `DashboardQueryAgent.trends()`，避免出现两套查询逻辑。
- dashboard/API/frontend 不直接解析 `payload`；只能消费查询层返回的 DTO。
- DTO 中日期使用 ISO 字符串，金额和 Decimal 使用字符串，评分使用 `float`，列表字段保持列表。
- `day_summary(trade_date)` 使用当日最新成功 `pre_market` run 的 watchlist、signals 和 risk decisions；orders、review reports 和 source snapshots 按当日查询；positions 和 portfolio snapshots 使用截至当日的最新状态。
- DTO 覆盖 pipeline runs、watchlist、signals、LLM pre-market analysis、risk decisions、paper orders、execution events、positions、portfolio snapshot、review report、review metrics、source snapshots、trading calendar、data quality reports、data reliability reports、range trends 和 strategy comparison。
- `DashboardDaySummary.llm_analysis` 使用所选交易日最新成功 `pre_market` run 对应的 `llm_analyses` 记录；没有成功盘前 run 或没有 LLM 记录时为 `null`，记录存在但 payload 缺字段或类型错误时显式失败。
- `DashboardLLMAnalysis` 字段包括 `run_id`、`trade_date`、`model`、`summary`、`key_points`、`risk_notes` 和 `created_at`。DTO 只展示已落库 LLM 审计内容，不在查询时重新调用 LLM。
- `list_backtests(limit)` 返回最近的 backtest summary run；`strategy_comparison(backtest_ids)` 只比较明确传入的 backtest 批次。
- 策略对比 DTO 按 `backtest_id` 输出 `strategy_params_version`、provider、日期范围、尝试/成功/失败天数、胜率、最大回撤、总收益率、风控拒绝率和数据质量失败率。
- `trends(start_date, end_date)` 使用闭区间日期范围，输出 `DashboardTrendSummary`：
  - `points` 按日期升序排列，只包含范围内有 pipeline run、组合快照、数据质量报告或运行可靠性报告的日期。
  - 权益曲线使用范围内每个交易日最新一条 `portfolio_snapshots.total_value`；没有快照时为 `null`。
  - 信号趋势使用当天最新成功 `pre_market` run 的 `signals`，统计 `signal_count` 和 `max_signal_score`。
  - 通过/拒绝使用同一最新成功 `pre_market` run 的 `risk_decisions`，统计 `approved_count` 和 `rejected_count`。
  - `risk_reject_reasons` 只统计被拒绝风控决策中的 `reasons` 原文次数，不做归类或改写。
  - 数据质量趋势按天统计 `source_failure_rate` 的最大值、`status=failed` 的阻断次数，以及 `severity=warning` 的 warning issue 次数。
  - 运行可靠性趋势按天统计最严重 `reliability_status`、最大 `reliability_source_failure_rate` 和 `reliability_missing_market_bar_count`。
- dashboard/API/frontend 只能展示质量结果，不修改数据或触发交易。
- `holding_days` 第一版用自然日差计算；后续如果新增结构化交易日历表，再替换为交易日口径。
- `DashboardReviewReport.metrics` 是截至所选交易日的累计复盘指标，字段包括：
  - `realized_pnl`：只统计已关闭模拟持仓，按 `(exit_price - entry_price) * quantity` 计算，DTO 用金额字符串。
  - `win_rate`：盈利 closed trade 数 / closed trade 总数；无 closed trade 时为 `0`。
  - `average_holding_days`：只统计 closed trade，沿用自然日口径；无 closed trade 时为 `0`。
  - `sell_reason_distribution`：按截至所选日可关联到成功 `intraday_watch` run 的模拟卖单 `reason` 原文计数，不做额外归类。
  - `max_drawdown`：按截至所选日 `portfolio_snapshots.total_value` 序列计算峰值到谷值最大跌幅，输出正数百分比小数。
- `DashboardPaperOrder.reason` 使用 `PaperOrder.reason` 原文；卖出原因不做自动归类。`PaperOrder.is_real_trade`、`execution_source`、`execution_timestamp`、`execution_method`、`reference_price`、`used_daily_fallback` 和 `execution_failure_reason` 必须保留在 DTO 和 API JSON 中；正常模拟订单必须为 `False`，`used_daily_fallback` 必须为 `False`，前端也会显式展示这些字段。
- `DashboardExecutionEvent` 从最新成功 `intraday_watch` run payload 的 `execution_events` 读取，展示无法成交的 symbol、side、估价方法、失败原因、参考价和 `used_daily_fallback`。该 DTO 只读展示失败审计，不代表订单。
- `DashboardIntradaySourceHealth` 从 `raw_source_snapshots(source=intraday_bars).metadata.source_attempts` 读取，展示每个 source/symbol 的状态、返回行数、retry、timeout 和最后错误；旧 snapshot 没有 `source_attempts` 时返回空列表。
- 查询层遇到缺字段、字段类型错误、未知枚举或当前阶段语义内的 `paper_orders.is_real_trade=True` 时必须显式失败，不能补默认值或静默兜底；复盘指标计算也遵守同一规则。

## 后续维护

涉及数据模型、provider 契约、字段含义、数据质量或审计要求的变化，必须同步更新本文。

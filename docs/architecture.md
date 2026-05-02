# AShareAgent 架构说明

当前状态：已落地 Python 后端骨架、Mock pipeline、真实 DataCollector 入口、分钟线成交估价、DataQualityAgent 质量门禁、DataReliabilityAgent 运行可靠性报告、结构化交易日历、daily-run CLI、LLM adapter、PostgreSQL/Alembic schema、核心持久化接线、模拟持仓生命周期、策略参数版本审计、多日 backtest 回放、策略参数评估、策略假设闭环、复盘指标查询、策略实验 Markdown 报告，以及支持日期范围趋势、策略对比、策略评估和策略假设只读视图的观察台。

## 目标架构

AShareAgent 目标是构建一个面向 A 股研究与模拟交易的 Agent 工程框架。第一阶段先跑通可测试、可复现、可审计的最小闭环。

计划中的最小 pipeline：

```text
DataCollector -> DataQualityAgent -> AnnouncementAnalyzer -> MarketRegimeAnalyzer -> SignalEngine -> RiskManager -> PaperTrader -> ReviewAgent
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `DataCollector` | 获取、标准化和缓存公告、新闻、日线行情、分钟线行情、指数、板块和交易日历数据。 |
| `DataQualityAgent` | 检查缺失行情、异常价格、空数据源、source 失败率和非交易日运行提示。 |
| `DataReliabilityAgent` | 基于已落库数据生成 source 健康、近 30 交易日行情缺口和 daily-run 可靠性报告。 |
| `AnnouncementAnalyzer` | 将公告转换为结构化事件，判断分类、利好/利空、重大性和排除原因。 |
| `MarketRegimeAnalyzer` | 判断指数趋势、成交量、板块强弱和市场风险偏好。 |
| `SignalEngine` | 执行策略规则，对候选股票评分，并决定是否进入观察名单。 |
| `StrategyParamsAgent` | 加载和校验策略参数配置，生成参数版本和参数快照。 |
| `RiskManager` | 处理仓位、涨跌停、T+1、黑名单和单日最大亏损等交易前风控。 |
| `PaperTrader` | 基于盘中分钟线估价执行模拟买入、模拟卖出、滑点估算和持仓记录。 |
| `ReviewAgent` | 生成收盘复盘、策略统计、错误归因和参数调整建议。 |
| `ReviewMetricsAgent` | 基于已落库模拟交易审计数据计算累计复盘指标，不参与交易执行。 |
| `BacktestRunner` | 按交易日历执行多日 `pre_market + intraday_watch + post_market_review` 回放，并用 `backtest_id` 隔离状态。 |
| `StrategyEvaluationRunner` | 按显式 variants 配置批量调用 `BacktestRunner`，聚合信号、风控、成交失败、收益、命中率和回撤，输出 Markdown 评估报告和人工复核建议。 |
| `StrategyInsightAgent` | 读取已落库事实并调用 LLM 生成结构化策略假设，只输出解释和建议，不修改配置。 |
| `HypothesisVariantBuilder` | 将 LLM 假设按白名单和安全边界编译为 strategy-evaluate variants，非法建议标记为 `rejected_by_policy`。 |

## 当前边界

- 当前入口是 CLI：`pre-market`、`intraday-watch`、`post-market-review`、`daily-run`、`backtest`、`strategy-evaluate`、`strategy-insight`。
- 默认 provider 是 `MockProvider`；设置 `ASHARE_PROVIDER=akshare` 后，CLI 从 `configs/universe.yml` 读取 `enabled=true` 的固定 ETF/大盘股池，并使用 `AKShareProvider` 拉真实公开源。日线行情当前通过 AKShare 的 Sina 路径采集，ETF 使用 `fund_etf_hist_sina`，A 股使用 `stock_zh_a_daily`；盘中分钟线用于模拟成交估价，默认分钟线源为 `ASHARE_INTRADAY_SOURCE=akshare_em`，可显式配置 `akshare_em,akshare_sina` source chain。`akshare_em` 直连 EastMoney `trends2/get`，`akshare_sina` 直连 Sina `CN_MarketDataService.getKLineData`；timeout、重试次数和退避由 `ASHARE_INTRADAY_TIMEOUT_SECONDS`、`ASHARE_INTRADAY_RETRY_ATTEMPTS`、`ASHARE_INTRADAY_RETRY_BACKOFF_SECONDS` 控制。
- 默认 LLM 是 mock；`.env` 中设置 `ASHARE_LLM_PROVIDER=openai` 或 `deepseek` 后才调用真实 API。
- 默认策略参数配置是 `configs/strategy_params.yml`；可通过 `ASHARE_STRATEGY_PARAMS_CONFIG` 指向其他配置。`StrategyParamsAgent` 会在 pipeline 构建时显式校验 `risk`、`paper_trader` 和 `signal` 配置，并把版本和快照写入 `pipeline_runs`、watchlist 和 signals payload。
- CLI 必须配置 `DATABASE_URL`；缺失时明确失败，不做内存兜底。
- 本地开发复用现有 Podman PostgreSQL 容器 `deployment_local_postgres_1` 的 `supportportal` 数据库；AShareAgent 只使用独立 `ashare_agent` schema。
- PostgreSQL 通过 Alembic 创建 `ashare_agent` schema、`ashare_agent.alembic_version` 和业务表；DataCollector 的 universe、raw source snapshots、market bars、announcements、news items、policy items、结构化 `trading_calendar`、DataQualityAgent 的 data quality reports、DataReliabilityAgent 的 data reliability reports、technical indicators，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、portfolio snapshots 和 review reports 已写入专表。
- `DataQualityAgent` 在原始数据落库后、策略分析前运行；质量失败时保存 `data_quality_reports`、失败 artifact 和 failed pipeline run，然后阻断后续策略或模拟交易更新。交易日内检查近 30 个交易日行情缺口；非交易日运行只提示，不因缺失行情阻断。
- `DataReliabilityAgent` 在 `daily-run` 和 dashboard 查询链路中读取已落库数据，生成 source 健康和近 30 个交易日行情缺口报告；交易日缺口为 failed，非交易日记录 skipped。
- 交易日历由 DataCollector 从 provider 返回的交易日列表展开为连续日期行，写入结构化 `trading_calendar` 表；同一 `calendar_date/source` 使用 upsert。
- `intraday-watch` 必须从 repository 恢复同日成功 `pre_market` 风控决策、开放持仓、最新现金和当日已有订单，采集相关标的 1 分钟 K 线，执行买入、盯市、退出评估、卖出、closed position 落库和盘中组合快照；重复运行同一交易日不重复成交。分钟线采集只写 `raw_source_snapshots(source=intraday_bars)` 审计，metadata 记录具体分钟线源、请求/返回/缺失 symbol、period、timeout、retry 配置和逐 source/symbol 的 `source_attempts`；显式链路中的所有分钟线源都不可用时 failed run，至少一个源正常响应但单个 symbol 无分钟线时交给执行估价层生成 rejected `execution_events`。模拟成交由 `IntradayPriceEstimator` 选择首个有效分钟 K 线并叠加动态滑点；缺少分钟线、停牌、买入涨停或卖出跌停时只写 rejected `execution_events`，不写失败订单，也不允许日线 close 兜底。
- `post-market-review` 不新增模拟订单，只恢复盘中订单和持仓，执行收盘盯市、持仓/组合快照、复盘，并生成独立 `strategy-experiment.md`，集中展示盘前 LLM 分析、风控拒绝原因、模拟订单、卖出原因和累计复盘指标。
- `backtest` 使用 provider 交易日历确定回放日期，每个交易日跑 `pre_market + intraday_watch + post_market_review`；结果写入现有 payload 专表，并用 `run_mode=backtest`、`backtest_id` 与普通模拟账户状态隔离，订单只归属 `intraday_watch`。
- `strategy-evaluate` 读取 `configs/strategy_evaluation.yml`，用 `base_config + variants[].overrides` 生成多个策略参数版本；默认窗口由 `default_window_trade_days` 控制，当前示例为最近 60 个交易日，也可由 CLI 日期覆盖。每个 variant 使用独立 `backtest_id=<evaluation_id>-<variant_id>` 调用 `BacktestRunner`，聚合 source/data quality failure rate、信号充足度、风控通过/拒绝、成交失败、买入后 2/5/10 个交易日表现、卖出触发原因、市场环境覆盖、closed trade 命中率、持仓收益、总收益率、最大回撤和参数差异；最终只写 `pipeline_runs(stage=strategy_evaluation)`、`artifacts(artifact_type=strategy_evaluation)` 和 Markdown 报告，不新增迁移，不修改生产策略参数。
- `strategy-insight` 读取 dashboard/query 层和 payload 表中的当天复盘事实、最近策略评估结果和当前策略参数快照，交给配置的 LLM 生成结构化 hypotheses JSON；确定性 `HypothesisVariantBuilder` 只允许白名单参数生成 variants，然后复用 `StrategyEvaluationRunner` 跑 20/40/60 日窗口并执行 gate 判断。结果只写 `pipeline_runs(stage=strategy_insight)`、`artifacts(artifact_type=strategy_insight)` 和 Markdown 报告，人工状态默认为 `pending_review`；不自动修改 `configs/strategy_params.yml`，不生成订单。
- `CachingDataProvider` 是 `strategy-evaluate` 的进程内 provider 包装层，按日期、symbol、period 缓存日线、分钟线、公告、新闻、政策、行业和交易日历结果；真实源失败也会缓存并重新抛出，避免多个 variants 重复打外部源，但不会吞错或补数据。
- `RiskManager` 同时负责买入前风控和退出决策；`PaperTrader` 只生成模拟订单，所有 `PaperOrder.is_real_trade` 固定为 `False`，成功订单必须记录成交来源、价格时间点、估价方法、参考价和 `used_daily_fallback=False`。
- `ReviewMetricsAgent` 只读取截至所选交易日的 `paper_positions`、`paper_orders` 和 `portfolio_snapshots` payload，计算已实现盈亏、胜率、平均持仓天数、卖出原因分布和最大回撤；缺字段、非法数字或真实交易订单必须显式失败。
- `daily-run` 先刷新交易日历；非交易日只写 skipped 审计和可靠性报告，不进入策略分析或模拟交易更新；交易日按盘前、盘中、复盘顺序运行，失败时先落库可靠性报告和 failed `daily_run`。
- `DashboardQueryAgent` 只读封装 `pipeline_runs`、观察名单、信号、盘前 LLM 分析、风控、盘中模拟订单、成交失败事件、分钟线源健康、持仓、组合快照、复盘、交易日历、数据源快照、数据质量、运行可靠性、日期范围趋势、策略版本对比、策略评估和策略假设查询，输出稳定 DTO。strategy evaluation 和 strategy insight 查询只读取已落库 payload，派生不可推荐原因或 gate 展示结构，不重新计算 backtest，也不读取 Markdown 文件内容。dashboard/API/frontend 后续应依赖该查询层，不直接解析 repository payload。
- 只读 dashboard 由 `DashboardQueryAgent`、FastAPI GET API 和 React/Vite 前端组成。前端只读取稳定 DTO，不直接读 PostgreSQL payload，也不提供交易操作入口。
- dashboard API 依赖 `DATABASE_URL`；缺失时明确失败，不做内存兜底。
- 模块边界发生变化时，同步更新本文件。

## 代码布局

```text
src/ashare_agent/
├── agents/              # 各业务 Agent
├── llm/                 # Mock/OpenAI/DeepSeek adapter
├── providers/           # Mock/AKShare data provider
├── api.py               # 只读 dashboard FastAPI app
├── backtest.py          # 多日策略回放 runner
├── cli.py               # Typer CLI
├── config.py            # .env 与 universe 配置
├── dashboard.py         # dashboard query DTO 和聚合服务
├── domain.py            # 标准 domain models
├── indicators.py        # 基础技术指标
├── pipeline.py          # 三段流程、盘中成交、daily-run、数据质量门禁和可靠性报告编排
├── reports.py           # Markdown 输出
├── repository.py        # In-memory/PostgreSQL repository
├── strategy_evaluation.py # 多 variant 策略评估 runner、配置加载和 provider 缓存
└── strategy_insights.py   # 策略假设 LLM 复盘、白名单 variant 编译和 gate
configs/
├── strategy_params.yml      # 默认策略参数配置
└── strategy_evaluation.yml  # 策略评估 variants 示例配置
```

`src/ashare_agent/agents/dashboard_query_agent.py` 属于只读查询适配层，不参与 pipeline 写入、不执行交易、不修改策略状态。`src/ashare_agent/dashboard.py` 是 API 使用的薄兼容层，避免前端/API 依赖内部 agent 文件路径。

前端代码位于 `frontend/`，使用 React、Vite、TypeScript 和 pnpm。当前页面是本地只读观察台，提供“日常观察 / 策略评估 / 策略假设”视图切换。日常观察展示日期范围内的 pipeline runs、范围趋势、策略版本对比、所选交易日的观察名单、风控结果、LLM 盘前分析、盘中模拟订单、成交失败事件、持仓、收盘复盘、数据质量、运行可靠性、数据源状态和运行详情；策略评估视图展示已落库 evaluation 批次、variant 排名、收益/回撤/失败率、推荐结论、不可推荐原因和报告路径；策略假设视图展示 LLM 假设、参数变更、policy reject 原因、20/40/60 日评估结果、gate 结论和人工复核状态。

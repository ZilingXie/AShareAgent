# AShareAgent

面向 A 股研究与模拟交易的 Agent 工程框架。

当前状态：`Foundation MVP / Real DataCollector / Data Quality Gate / Data Reliability / Structured Trading Calendar / Daily Run / PostgreSQL Persistence / Paper Trading Lifecycle / Intraday Price Realism / Strategy Params Audit / Strategy Backtest / Strategy Evaluation / Strategy Insight Loop / Read-only Dashboard`

本项目现阶段的重点不是追求策略复杂度，而是先建立一套可复现、可测试、可审计的工程底座。所有模块、接口和运行入口都应服务于一个目标：让后续策略开发可以在清晰边界和质量门禁下持续演进。

## 安全边界

- v1 只实现 `PaperTrader`，用于模拟交易和策略验证。
- 不连接真实券商账户。
- 不自动执行真实买入或卖出。
- 不提供荐股、收益承诺或投资建议。
- 所有交易相关能力必须默认停留在模拟环境，并保留可追踪的决策原因和输入数据快照。

## 项目目标

第一阶段目标是跑通一个可测试的最小闭环：

`DataCollector -> DataQualityAgent -> AnnouncementAnalyzer -> MarketRegimeAnalyzer -> SignalEngine -> RiskManager -> PaperTrader -> ReviewAgent`

这个闭环应支持：

- 使用 Mock 数据稳定回放核心流程。
- 使用 AKShare provider 接入固定 ETF/大盘股池的真实公开数据。
- 用规则基线完成公告分类、利好/利空、重大性判断。
- 对候选股票进行评分，并经过风控过滤后进入模拟交易。
- 在盘中完成模拟买卖和持仓/组合更新，收盘后完成盯市、复盘结果和错误归因。
- 模拟成交使用分钟线估价，不使用日线 close 兜底；无法成交时记录可审计失败原因。
- 用 mock 或真实公开源做多日历史回放，并按策略版本比较胜率、回撤、收益、拒绝率和数据质量失败率。
- 用显式策略参数 variants 做连续多日评估，统计信号、风控、成交失败、收益和回撤，只输出报告和建议，不自动改生产参数。
- 用 LLM 做只读复盘解释和策略假设生成，再由确定性代码编译白名单 variants、执行 20/40/60 日评估和 gate 判断，人工再决定是否另起配置变更。
- 通过只读观察台查看四大看板：总览、交易执行、策略、质量；覆盖资产走势、每日盈亏、pipeline run、观察名单、风控、盘中模拟订单、持仓、复盘、数据源状态、运行可靠性报告、策略评估决策视图和策略假设视图。

## 模块设计

```text
AShareAgent
├── DataCollector
│   ├── 公告抓取
│   ├── 新闻抓取
│   ├── 行情抓取
│   ├── 分钟线抓取
│   ├── 指数/板块数据
│   └── 交易日历
│
├── DataQualityAgent
│   ├── 缺失行情检查
│   ├── 异常价格检查
│   ├── 空数据源检查
│   ├── source 失败率统计
│   └── 非交易日运行提示
│
├── DataReliabilityAgent
│   ├── source 健康报告
│   ├── 近 30 交易日行情缺口报告
│   ├── 结构化交易日历读取
│   └── daily-run 跳过/失败/成功审计
│
├── AnnouncementAnalyzer
│   ├── 公告分类
│   ├── 利好/利空判断
│   ├── 是否重大
│   └── 是否需要排除
│
├── MarketRegimeAnalyzer
│   ├── 指数趋势
│   ├── 成交量
│   ├── 板块强弱
│   └── 风险偏好
│
├── SignalEngine
│   ├── 策略规则
│   ├── 候选股票评分
│   └── 是否进入观察名单
│
├── StrategyParamsAgent
│   ├── 策略参数配置加载
│   ├── 参数校验
│   └── 参数版本快照
│
├── RiskManager
│   ├── 仓位限制
│   ├── 涨跌停风险
│   ├── T+1 风险
│   ├── 黑名单过滤
│   └── 单日最大亏损
│
├── PaperTrader
│   ├── 模拟买入
│   ├── 模拟卖出
│   ├── 成交价格估算
│   └── 滑点估算
│
└── ReviewAgent
    ├── 收盘复盘
    ├── 策略统计
    ├── 错误归因
    └── 参数调整建议

BacktestRunner
└── 多日历史回放
    ├── mock / akshare provider
    ├── pre-market + intraday-watch + post-market-review
    ├── backtest_id 状态隔离
    └── 策略版本对比指标

StrategyEvaluationRunner
└── 多 variant 策略评估
    ├── base_config + overrides
    ├── 最近 60 个交易日默认窗口
    ├── CachingDataProvider 复用真实源结果
    └── Markdown 报告和 strategy_evaluation 审计

StrategyInsightAgent
└── 策略假设闭环
    ├── 读取已落库复盘事实
    ├── LLM 生成结构化假设 JSON
    ├── 白名单参数编译为 variants
    ├── 20/40/60 日 strategy-evaluate
    └── dashboard 只读展示和人工复核状态
```

### 模块职责边界

- `DataCollector`：负责数据获取、标准化和缓存，不直接做投资判断。
- `DataQualityAgent`：负责真实数据质量门禁和质量报告，不生成交易信号。
- `DataReliabilityAgent`：负责从已落库数据生成数据源健康和行情缺口报告，不生成交易信号。
- `AnnouncementAnalyzer`：负责将公告转成结构化事件和规则判断结果，不直接生成交易指令。
- `MarketRegimeAnalyzer`：负责判断市场环境、板块强弱和风险偏好，为信号和风控提供上下文。
- `SignalEngine`：负责策略规则、候选股票评分和观察名单决策，不绕过风控。
- `StrategyParamsAgent`：负责加载和校验策略参数配置，并为每次 pipeline run 生成可追溯参数快照。
- `RiskManager`：负责所有交易前风险过滤和仓位约束，是模拟交易前的强制门禁。
- `PaperTrader`：负责基于盘中分钟线估价模拟成交、持仓、滑点和资金曲线，不接真实交易通道。
- `ReviewAgent`：负责复盘、统计、错误归因和参数调整建议，不直接修改生产策略参数。
- `BacktestRunner`：负责多日策略回放，只复用 `PaperTrader` 模拟交易闭环，不接真实券商。
- `StrategyEvaluationRunner`：负责按多个策略参数 variant 调用 backtest，聚合命中率、拒绝率、成交失败、收益和回撤，并输出人工复核建议，不自动修改 `configs/strategy_params.yml`。
- `StrategyInsightAgent`：负责把当天复盘事实交给 LLM 生成结构化假设；`HypothesisVariantBuilder` 只编译白名单参数，非法建议标记为 `rejected_by_policy`，不修改生产配置。

当前默认策略参数位于 `configs/strategy_params.yml`：单日最大亏损 2%、止损 5%、涨跌停阈值 9.8%、最少持有 2 个交易日、最多持有 10 个交易日，以及 SignalEngine 权重、最低分阈值和每日最大信号数。止损在 T+1 后可优先触发；趋势走弱和到期卖出必须满足最少持有期。每次 pipeline run、watchlist 和 signal 都会记录 `strategy_params_version` 和 `strategy_params_snapshot`，用于复盘追溯当时使用的参数。

## 工程原则

- 可复现：关键流程必须能用固定输入重复运行并得到稳定输出。
- 可测试：每个 Agent 都应有独立测试，跨 Agent 的 pipeline 要有集成测试。
- 数据源适配器：业务逻辑依赖统一 `DataProvider` 接口，不直接绑定 AKShare 或其他外部数据源。
- 规则先行：第一版公告分析优先使用可解释规则，LLM 能力只预留接口，不作为核心依赖。
- 真实交易隔离：真实交易能力不进入 v1，任何相关扩展都必须先经过单独安全设计。
- 审计可追踪：信号、风控、模拟成交和复盘都必须记录输入、输出、时间和决策原因。

## 计划中的技术栈

后端：

- Python 3.12
- Typer CLI
- FastAPI
- PostgreSQL
- SQLAlchemy / Alembic
- AKShare provider
- Mock provider
- OpenAI / DeepSeek LLM adapter
- pytest
- ruff
- pyright

前端：

- React
- Vite
- TypeScript
- 只读观察台

工程：

- GitHub Actions
- pre-commit
- `.env.example`
- `uv`
- `AGENTS.md`
- `docs/`

## TODO

### Phase 0: Harness Engineering

- [x] 建立后端工程骨架。
- [x] 建立前端工程骨架。
- [x] 创建根目录 `AGENTS.md`，定义开发 Agent 必须遵守的编码、测试和安全规则。
- [x] 创建 `CONTEXT.md`，记录当前状态、停靠点和关键决定。
- [x] 创建 `docs/architecture.md`，记录模块边界和数据流。
- [x] 创建 `docs/safety.md`，记录 PaperTrader 边界和真实交易禁用规则。
- [x] 创建 `docs/data-contracts.md`，记录核心 domain models 和 provider 契约。
- [x] 创建 `docs/research-log.md`，记录外部调研结论。
- [x] 配置 ruff、pyright、pytest。
- [ ] 配置 pre-commit 和 GitHub Actions。

### Phase 1: Minimal Pipeline

- [x] 定义统一 `DataProvider` 接口。
- [x] 实现 `MockProvider`，用于无外网测试和固定回放。
- [x] 实现最小 `AKShareProvider`，只接入第一批必要 A 股数据。
- [x] 实现公告规则分析基线。
- [x] 实现候选股票评分规则。
- [x] 实现风险过滤规则。
- [x] 实现 PaperTrader 的模拟买入、模拟卖出、滑点估算和持仓记录。
- [x] 实现 ReviewAgent 的收盘复盘和基础策略统计。
- [x] 用 Mock 数据跑通完整 pipeline integration test。

### Phase 2: Read-only Web Console

- [x] 展示 pipeline run 列表。
- [x] 展示候选股票评分。
- [x] 展示风控拒绝原因。
- [x] 展示盘中模拟订单和真实交易安全标记。
- [x] 展示模拟订单成交依据、是否日线兜底和成交失败原因。
- [x] 展示模拟持仓和资金曲线摘要。
- [x] 展示日期范围内的资金曲线、信号趋势、风控拒绝原因和数据质量趋势。
- [x] 展示收盘复盘结果。
- [x] 展示 raw source snapshots 和真实源失败原因。
- [x] 展示策略评估批次、variant 排名、推荐结论和不可推荐原因。

### Phase 3: Hardening

- [x] 增加公告样本 golden tests。
- [x] 增加 provider contract tests。
- [x] 增加数据质量检查。
- [x] 增加结构化交易日历、数据源健康和缺口报告。
- [x] 增加每日运行 CLI 和脚本。
- [ ] 增加 pipeline run 审计日志。
- [x] 增加策略参数版本记录。
- [x] 增加策略参数驱动 SignalEngine 和多日 backtest 对比。
- [x] 增加连续多日策略参数评估入口。

## 开发入口

安装依赖：

```bash
uv sync
```

本地配置：

```bash
cp .env.example .env
```

`.env` 已被 `.gitignore` 忽略。使用 OpenAI 验证时，写入：

```bash
ASHARE_PROVIDER=mock
ASHARE_LLM_PROVIDER=openai
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=你的 key
```

普通离线测试使用：

```bash
ASHARE_LLM_PROVIDER=mock
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal
```

真实公开源使用：

```bash
ASHARE_PROVIDER=akshare
ASHARE_LLM_PROVIDER=mock
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal
ASHARE_INTRADAY_SOURCE=akshare_em
ASHARE_INTRADAY_TIMEOUT_SECONDS=15
ASHARE_INTRADAY_RETRY_ATTEMPTS=3
ASHARE_INTRADAY_RETRY_BACKOFF_SECONDS=0.5
```

`akshare` 模式固定从 `configs/universe.yml` 读取 `enabled=true` 的 ETF/大盘股池。真实源下 `universe`、`market_bars`、`trade_calendar` 是必需源；这些源失败、必需源空数据、交易日缺失当日行情或行情价格异常时，CLI 会明确失败，并把失败原因写入 `raw_source_snapshots`、`data_quality_reports` 和失败的 `pipeline_runs`。公告、新闻和政策为空会作为质量警告记录，接口异常仍会记录失败快照。

策略参数默认从 `configs/strategy_params.yml` 读取，也可用 `ASHARE_STRATEGY_PARAMS_CONFIG` 指向另一份配置。配置包含 `risk`、`paper_trader` 和 `signal` 三组参数；`signal` 控制 SignalEngine 权重、最低分阈值和每日最大信号数。策略参数配置缺字段、百分比非法、持有期范围非法或每日最大信号数小于 1 时，CLI 会明确失败，不会使用代码里的静默默认值。

当前真实日线行情使用 AKShare 的 Sina 路径：ETF 走 `fund_etf_hist_sina`，A 股走 `stock_zh_a_daily`。盘中成交估价默认使用 `ASHARE_INTRADAY_SOURCE=akshare_em`，由 `AKShareProvider` 直连 EastMoney `push2his.eastmoney.com/api/qt/stock/trends2/get` 获取 1 分钟 K 线。备用源为 `akshare_sina`，直连 Sina `CN_MarketDataService.getKLineData`；只有显式配置 `ASHARE_INTRADAY_SOURCE=akshare_em,akshare_sina` 时才会按链路尝试备用源，不会默认静默切换。timeout、重试次数和退避由 `ASHARE_INTRADAY_TIMEOUT_SECONDS`、`ASHARE_INTRADAY_RETRY_ATTEMPTS`、`ASHARE_INTRADAY_RETRY_BACKOFF_SECONDS` 控制。

运行 CLI 前必须先配置 `DATABASE_URL` 并完成迁移。CLI 不配置数据库会明确失败，避免误以为结果已持久化。

运行 CLI：

```bash
uv run ashare pre-market --trade-date 2026-04-29
uv run ashare intraday-watch --trade-date 2026-04-29
uv run ashare post-market-review --trade-date 2026-04-29
uv run ashare daily-run --trade-date 2026-04-29
scripts/daily_run.sh 2026-04-29
```

`daily-run` 会先刷新结构化交易日历。若所选日期不是交易日，只写入 `daily_run` skipped 审计、交易日历和运行可靠性报告，不进入策略分析，也不更新模拟订单或持仓；若是交易日，则按盘前、盘中、复盘顺序运行，模拟买卖只发生在盘中阶段，任一阶段失败都会先写入已有质量/可靠性报告和 failed `daily_run` 后再明确失败。

运行多日策略回放：

```bash
ASHARE_PROVIDER=mock ASHARE_LLM_PROVIDER=mock \
  uv run ashare backtest \
  --start-date 2026-04-27 \
  --end-date 2026-04-30 \
  --backtest-id smoke-strategy-v1
```

backtest 每个交易日跑 `pre-market + intraday-watch + post-market-review`，强制使用 mock LLM，模拟订单只归属 `intraday_watch` run，结果用 `run_mode=backtest` 和 `backtest_id` 写入现有 payload 专表。普通 CLI 运行使用 `run_mode=normal`，不会恢复 backtest 的持仓、订单或现金。

运行策略参数评估：

```bash
ASHARE_PROVIDER=akshare ASHARE_LLM_PROVIDER=mock \
ASHARE_INTRADAY_SOURCE=akshare_em,akshare_sina \
  uv run ashare strategy-evaluate \
  --config configs/strategy_evaluation.yml
```

`strategy-evaluate` 读取 `configs/strategy_evaluation.yml`，按 `base_config + variants[].overrides` 生成多组策略参数。默认窗口由 `default_window_trade_days` 控制，当前示例为最近 60 个交易日；也可用 `--start-date` 和 `--end-date` 覆盖。每个 variant 会生成独立 `backtest_id=<evaluation_id>-<variant_id>`，失败日计入失败率并继续后续日期/variant；聚合结果写入 `pipeline_runs(stage=strategy_evaluation)`、`artifacts(artifact_type=strategy_evaluation)` 和 `reports/<evaluation_id>/strategy-evaluation.md`。报告会汇总信号充足度、买入后 2/5/10 个交易日表现、卖出触发原因、数据源失败率、市场环境覆盖和参数差异。该入口强制使用 mock LLM，不接真实交易，不自动修改 `configs/strategy_params.yml`。当 `ASHARE_PROVIDER=akshare` 时，`ASHARE_INTRADAY_SOURCE` 必须包含 `akshare_sina`，用于验收 Sina 分钟线 fallback 链路。

运行策略假设复盘：

```bash
ASHARE_PROVIDER=akshare ASHARE_LLM_PROVIDER=openai \
ASHARE_INTRADAY_SOURCE=akshare_em,akshare_sina \
  uv run ashare strategy-insight \
  --trade-date 2026-04-30 \
  --insight-id insight-20260430
```

`strategy-insight` 读取 dashboard/query 层和 payload 表中的当天复盘事实、盘前 LLM、信号、风控、盘中订单、成交失败、持仓、资金曲线、数据质量和最近策略评估结果。LLM 只输出结构化 hypotheses JSON；真实 LLM JSON 解析失败会明确失败。`HypothesisVariantBuilder` 只允许编译 `signal.min_score`、`signal.weights.technical`、`signal.weights.market`、`risk.stop_loss_pct`、`risk.min_holding_trade_days`、`risk.max_holding_trade_days`、`risk.max_positions`，其他建议标记为 `rejected_by_policy`。通过白名单的 variants 会复用 `StrategyEvaluationRunner` 跑 20/40/60 日窗口，backtest 仍强制使用 mock LLM。结果写入 `pipeline_runs(stage=strategy_insight)`、`artifacts(artifact_type=strategy_insight)` 和 `reports/<insight_id>/strategy-insights.md`，dashboard 只读展示 `待复核` 状态；本入口不修改 `configs/strategy_params.yml`，不生成真实订单，不自动上线参数。

验证：

```bash
uv run pytest
uv run ruff check
uv run pyright
```

真实 AKShare smoke test 默认不进入普通测试。日线/交易日历和分钟线已拆开，手动运行：

```bash
uv run pytest -m external_daily
uv run pytest -m external_intraday
uv run pytest -m external_intraday_akshare_em
uv run pytest -m external_intraday_akshare_sina
uv run pytest -m external
```

`external_daily` 只验证交易日历和日线行情，不受分钟线端点影响；`external_intraday` 聚合所有分钟线源，`external_intraday_akshare_em` 和 `external_intraday_akshare_sina` 可分别定位 EastMoney 与 Sina 的真实源状态。若某个源出现 `RemoteDisconnected` 或代理错误，应记录为外部分钟线源不可用，不能切回 Mock 或使用日线兜底。

PostgreSQL 迁移：

```bash
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal \
  uv run alembic upgrade head
```

本地开发复用现有 Podman PostgreSQL：容器 `deployment_local_postgres_1`，宿主端口 `15432`，数据库 `supportportal`，用户 `supportportal`。迁移只创建 `ashare_agent` schema、本项目表和 `ashare_agent.alembic_version`，不主动删除已有对象，也不在 `public` 或 `supportportal` schema 建业务表。若 `ashare_agent` schema 已存在但缺少 `ashare_agent.alembic_version`，迁移会停止并要求先人工确认。

当前 CLI 会把 DataCollector 的 universe、raw source snapshots、market bars、announcements、news items、policy items、结构化 `trading_calendar`、DataQualityAgent 的 data quality reports、DataReliabilityAgent 的 data reliability reports、technical indicators，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、portfolio snapshots 和 review reports 写入 `ashare_agent` schema 下的专表，并继续写 `artifacts` 审计表。`pipeline_runs.payload` 会记录策略参数版本和完整参数快照。

策略评估和策略假设复盘都不新增数据库迁移；聚合结果复用 `pipeline_runs` 和 `artifacts`，单个 variant 的明细复用 backtest 已有专表和 `backtest_id` 隔离。`configs/strategy_evaluation.yml` 的 `default_window_trade_days` 必须在 20 到 60 之间，显式 CLI 日期范围优先于该默认窗口。策略假设复盘 payload 会保留 LLM 假设、policy reject 原因、20/40/60 日评估窗口、gate 结果、报告路径和 `manual_status=pending_review`。

`intraday-watch` 必须找到同日成功的 `pre-market` 风控决策，才会恢复开放持仓、最新现金和当日已有模拟订单，执行允许的买入、盯市、退出评估和卖出。当日已有模拟订单只读取同日成功 `intraday_watch` run 生成的订单；旧流程遗留的 `post_market_review` 订单保留在数据库里，但不参与盘中幂等判断。执行前会按获批买入标的和当前开放持仓采集 1 分钟 K 线，并写入 `raw_source_snapshots(source=intraday_bars)` 审计，metadata 记录 `intraday_source`、请求/返回/缺失 symbol、period、timeout、retry 配置和 `source_attempts`。成交价使用首个有效 1 分钟 K 线加动态滑点估算，不允许用日线 close 兜底。显式链路中的所有分钟线源都不可用时写 failed snapshot 和 failed run；至少一个源正常响应但单个 symbol 无分钟线时 run 可成功，不写 `paper_orders`，只在 `intraday_watch` artifact / payload 的 `execution_events` 中记录 rejected 原因。成功买卖订单写入 `paper_orders`，并记录 `execution_source`、`execution_timestamp`、`execution_method`、`reference_price` 和 `used_daily_fallback=False`；持仓和组合快照写入 `paper_positions`、`portfolio_snapshots`。重复运行同一交易日不会重复买入或卖出。

`post-market-review` 不新增 `paper_orders`，只恢复同日成功 `intraday_watch` run 生成的订单和持仓，执行收盘盯市，写入持仓快照、组合快照、复盘报告和策略实验报告。`reviewed_order_count` 和复盘报告里的订单列表只统计盘中订单，历史 `post_market_review` 订单不会污染新阶段语义。

只读观察台 API：

```bash
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal \
  uv run uvicorn ashare_agent.api:app --host 127.0.0.1 --port 8000
```

API 只提供 GET：`/api/health`、`/api/dashboard/runs?limit=50`、`/api/dashboard/days/{trade_date}`、`/api/dashboard/trends?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`、`/api/dashboard/backtests?limit=50`、`/api/dashboard/strategy-comparison?backtest_ids=id1,id2`、`/api/dashboard/strategy-evaluations?limit=50`、`/api/dashboard/strategy-evaluations/{evaluation_id}`、`/api/dashboard/strategy-insights?limit=50`、`/api/dashboard/strategy-insights/{insight_id}`。缺少 `DATABASE_URL` 时会明确失败，不做内存兜底。日汇总 DTO 包含 `trading_calendar`、`data_quality_reports` 和 `data_reliability_reports`，用于展示每次 run 的质量状态、source 失败率、缺失行情、异常价格、source 健康和近 30 交易日缺口；趋势 DTO 覆盖资金曲线、信号、风控拒绝原因、数据质量趋势和运行可靠性趋势；策略对比 DTO 按 `backtest_id` 展示胜率、回撤、收益、拒绝率和数据质量失败率；策略评估 DTO 展示 evaluation 批次、variant 指标、推荐结论、不可推荐原因和 Markdown 报告路径；策略假设 DTO 展示 LLM 假设、白名单编译结果、20/40/60 日 gate 结果和人工复核状态。

前端观察台：

```bash
pnpm --dir frontend install
pnpm --dir frontend dev --host 127.0.0.1 --port 5173
```

前端只通过 API 读取 dashboard DTO，不直接连接 PostgreSQL，不提供任何真实交易、模拟交易执行或自动调参按钮。页面支持四大只读看板和日期范围筛选：

- `总览`：账户视角，展示总资产、区间盈亏、每日盈亏、权益曲线、今日交易摘要、当前持仓和收盘复盘摘要。
- `交易执行`：交易链路视角，展示盘前计划、风控结果、盘中模拟订单、成交失败、当前持仓和收盘复盘。点击左侧任一 `盘前 / 盘中 / 复盘` run 会打开只读阶段详情抽屉；盘前详情包含观察名单、LLM 盘前分析和风控预检查，盘中详情包含模拟订单、成交失败和分钟线成交依据，复盘详情包含组合快照、复盘指标和报告路径。
- `策略`：策略视角，展示信号趋势、观察名单评分、风控拒绝原因、策略版本对比、策略评估批次、variant 排名、不可推荐原因和策略假设。这里的“信号趋势”表示买入候选信号和风控通过/拒绝，不等于实际买卖订单；策略评估只展示历史模拟指标，不构成投资建议，不自动修改策略参数；策略假设只读展示 LLM 假设、参数变更、policy reject 原因、三窗口评估结果和 `待复核` 状态，不提供接受/拒绝按钮。
- `质量`：数据与运行视角，展示数据质量趋势、DataQuality 报告、运行可靠性、分钟线源健康、数据源状态和运行详情。质量失败会影响策略可信度，但不会被静默兜底；失败原因默认摘要展示，完整错误保留在 hover/title 或阶段详情中。

所选单日的“盘中模拟订单”只展示同日成功 `intraday_watch` run 的订单，历史盘后订单不会展示到该区域。订单表会显示成交依据、价格时间点、估价方法、是否使用日线兜底和真实交易标记；“成交失败”区域展示分钟线缺失、停牌或涨跌停导致的 rejected execution events；“分钟线源健康”区域展示每个 source/symbol 的尝试结果、retry、timeout 和最后错误。`PaperOrder.is_real_trade` 会在页面中显式展示；正常模拟订单必须是 `False`，任何当前盘中订单出现 `True` 都视为安全异常。

前端验证：

```bash
pnpm --dir frontend test
pnpm --dir frontend build
```

## 文档导航

当前文档：

- `CONTEXT.md`：当前状态、停靠点和近期关键决定。
- `AGENTS.md`：开发 Agent 的编码规范、测试要求、安全约束和协作规则。
- `skills.md`：本项目推荐使用的 Codex skills。
- `docs/architecture.md`：系统架构、模块职责、数据流和 pipeline 设计。
- `docs/safety.md`：模拟交易边界、真实交易禁用规则和风险控制原则。
- `docs/data-contracts.md`：核心数据模型、provider 契约和数据质量要求。
- `docs/research-log.md`：外部调研记录和采纳结论。

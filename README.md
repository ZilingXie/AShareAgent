# AShareAgent

面向 A 股研究与模拟交易的 Agent 工程框架。

当前状态：`Foundation MVP / Real DataCollector / Data Quality Gate / PostgreSQL Persistence / Paper Trading Lifecycle / Strategy Params Audit / Read-only Dashboard`

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
- 在收盘后完成模拟买卖、持仓状态更新、复盘结果和错误归因。
- 通过只读观察台查看 pipeline run、观察名单、风控、模拟订单、持仓、复盘和数据源状态。

## 模块设计

```text
AShareAgent
├── DataCollector
│   ├── 公告抓取
│   ├── 新闻抓取
│   ├── 行情抓取
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
```

### 模块职责边界

- `DataCollector`：负责数据获取、标准化和缓存，不直接做投资判断。
- `DataQualityAgent`：负责真实数据质量门禁和质量报告，不生成交易信号。
- `AnnouncementAnalyzer`：负责将公告转成结构化事件和规则判断结果，不直接生成交易指令。
- `MarketRegimeAnalyzer`：负责判断市场环境、板块强弱和风险偏好，为信号和风控提供上下文。
- `SignalEngine`：负责策略规则、候选股票评分和观察名单决策，不绕过风控。
- `StrategyParamsAgent`：负责加载和校验策略参数配置，并为每次 pipeline run 生成可追溯参数快照。
- `RiskManager`：负责所有交易前风险过滤和仓位约束，是模拟交易前的强制门禁。
- `PaperTrader`：负责模拟成交、持仓、滑点和资金曲线，不接真实交易通道。
- `ReviewAgent`：负责复盘、统计、错误归因和参数调整建议，不直接修改生产策略参数。

当前默认策略参数位于 `configs/strategy_params.yml`：单日最大亏损 2%、止损 5%、涨跌停阈值 9.8%、最少持有 2 个交易日、最多持有 10 个交易日。止损在 T+1 后可优先触发；趋势走弱和到期卖出必须满足最少持有期。每次 pipeline run 都会记录 `strategy_params_version` 和 `strategy_params_snapshot`，用于复盘追溯当时使用的参数。

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
- [x] 展示模拟订单和真实交易安全标记。
- [x] 展示模拟持仓和资金曲线摘要。
- [x] 展示收盘复盘结果。
- [x] 展示 raw source snapshots 和真实源失败原因。

### Phase 3: Hardening

- [x] 增加公告样本 golden tests。
- [x] 增加 provider contract tests。
- [x] 增加数据质量检查。
- [ ] 增加 pipeline run 审计日志。
- [x] 增加策略参数版本记录。

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
```

`akshare` 模式固定从 `configs/universe.yml` 读取 `enabled=true` 的 ETF/大盘股池。真实源下 `universe`、`market_bars`、`trade_calendar` 是必需源；这些源失败、必需源空数据、交易日缺失当日行情或行情价格异常时，CLI 会明确失败，并把失败原因写入 `raw_source_snapshots`、`data_quality_reports` 和失败的 `pipeline_runs`。公告、新闻和政策为空会作为质量警告记录，接口异常仍会记录失败快照。

策略参数默认从 `configs/strategy_params.yml` 读取，也可用 `ASHARE_STRATEGY_PARAMS_CONFIG` 指向另一份配置。策略参数配置缺字段、百分比非法或持有期范围非法时，CLI 会明确失败，不会使用代码里的静默默认值。

当前真实日线行情使用 AKShare 的 Sina 路径：ETF 走 `fund_etf_hist_sina`，A 股走 `stock_zh_a_daily`。EastMoney 历史 K 线端点在本机代理和直连下都可能断开，provider 不会静默切回 Mock 或伪造行情。

运行 CLI 前必须先配置 `DATABASE_URL` 并完成迁移。CLI 不配置数据库会明确失败，避免误以为结果已持久化。

运行 CLI：

```bash
uv run ashare pre-market --trade-date 2026-04-29
uv run ashare intraday-watch --trade-date 2026-04-29
uv run ashare post-market-review --trade-date 2026-04-29
```

验证：

```bash
uv run pytest
uv run ruff check
uv run pyright
```

真实 AKShare smoke test 默认不进入普通测试，手动运行：

```bash
uv run pytest -m external
```

PostgreSQL 迁移：

```bash
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal \
  uv run alembic upgrade head
```

本地开发复用现有 Podman PostgreSQL：容器 `deployment_local_postgres_1`，宿主端口 `15432`，数据库 `supportportal`，用户 `supportportal`。迁移只创建 `ashare_agent` schema、本项目表和 `ashare_agent.alembic_version`，不主动删除已有对象，也不在 `public` 或 `supportportal` schema 建业务表。若 `ashare_agent` schema 已存在但缺少 `ashare_agent.alembic_version`，迁移会停止并要求先人工确认。

当前 CLI 会把 DataCollector 的 universe、raw source snapshots、market bars、announcements、news items、policy items、DataQualityAgent 的 data quality reports、technical indicators，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、portfolio snapshots 和 review reports 写入 `ashare_agent` schema 下的专表，并继续写 `artifacts` 审计表。`pipeline_runs.payload` 会记录策略参数版本和完整参数快照。交易日历本轮只作为 `raw_source_snapshots` 审计快照保存，不新增结构化日历表。

`post-market-review` 会从数据库恢复开放持仓、最新现金和当日已有模拟订单，执行允许的买入、盯市、退出评估和卖出。卖出订单写入 `paper_orders`，closed position 写入 `paper_positions`；重复运行同一交易日不会重复买入或卖出。

只读观察台 API：

```bash
DATABASE_URL=postgresql+psycopg://supportportal:<password>@localhost:15432/supportportal \
  uv run uvicorn ashare_agent.api:app --host 127.0.0.1 --port 8000
```

API 只提供 GET：`/api/health`、`/api/dashboard/runs?limit=50`、`/api/dashboard/days/{trade_date}`。缺少 `DATABASE_URL` 时会明确失败，不做内存兜底。日汇总 DTO 包含 `data_quality_reports`，用于展示每次 run 的质量状态、source 失败率、缺失行情和异常价格问题。

前端观察台：

```bash
pnpm --dir frontend install
pnpm --dir frontend dev --host 127.0.0.1 --port 5173
```

前端只通过 API 读取 dashboard DTO，不直接连接 PostgreSQL，不提供任何真实交易或模拟交易操作按钮。`PaperOrder.is_real_trade` 会在页面中显式展示；正常模拟订单必须是 `False`，任何 `True` 都视为安全异常。

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

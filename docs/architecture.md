# AShareAgent 架构说明

当前状态：已落地 Python 后端骨架、Mock pipeline、真实 DataCollector 入口、CLI、LLM adapter、PostgreSQL/Alembic 初始 schema、核心持久化接线、模拟持仓生命周期、复盘指标查询和第一版只读观察台。

## 目标架构

AShareAgent 目标是构建一个面向 A 股研究与模拟交易的 Agent 工程框架。第一阶段先跑通可测试、可复现、可审计的最小闭环。

计划中的最小 pipeline：

```text
DataCollector -> AnnouncementAnalyzer -> MarketRegimeAnalyzer -> SignalEngine -> RiskManager -> PaperTrader -> ReviewAgent
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `DataCollector` | 获取、标准化和缓存公告、新闻、行情、指数、板块和交易日历数据。 |
| `AnnouncementAnalyzer` | 将公告转换为结构化事件，判断分类、利好/利空、重大性和排除原因。 |
| `MarketRegimeAnalyzer` | 判断指数趋势、成交量、板块强弱和市场风险偏好。 |
| `SignalEngine` | 执行策略规则，对候选股票评分，并决定是否进入观察名单。 |
| `RiskManager` | 处理仓位、涨跌停、T+1、黑名单和单日最大亏损等交易前风控。 |
| `PaperTrader` | 执行模拟买入、模拟卖出、成交价格估算、滑点估算和持仓记录。 |
| `ReviewAgent` | 生成收盘复盘、策略统计、错误归因和参数调整建议。 |
| `ReviewMetricsAgent` | 基于已落库模拟交易审计数据计算累计复盘指标，不参与交易执行。 |

## 当前边界

- 当前入口是 CLI：`pre-market`、`intraday-watch`、`post-market-review`。
- 默认 provider 是 `MockProvider`；设置 `ASHARE_PROVIDER=akshare` 后，CLI 从 `configs/universe.yml` 读取 `enabled=true` 的固定 ETF/大盘股池，并使用 `AKShareProvider` 拉真实公开源。日线行情当前通过 AKShare 的 Sina 路径采集，ETF 使用 `fund_etf_hist_sina`，A 股使用 `stock_zh_a_daily`。
- 默认 LLM 是 mock；`.env` 中设置 `ASHARE_LLM_PROVIDER=openai` 或 `deepseek` 后才调用真实 API。
- CLI 必须配置 `DATABASE_URL`；缺失时明确失败，不做内存兜底。
- 本地开发复用现有 Podman PostgreSQL 容器 `deployment_local_postgres_1` 的 `supportportal` 数据库；AShareAgent 只使用独立 `ashare_agent` schema。
- PostgreSQL 通过 Alembic 创建 `ashare_agent` schema、`ashare_agent.alembic_version` 和业务表；DataCollector 的 universe、raw source snapshots、market bars、announcements、news items、policy items、technical indicators，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、portfolio snapshots 和 review reports 已写入专表。
- 交易日历本轮不建结构化专表，只作为 `raw_source_snapshots` 的 `trade_calendar` 采集快照记录。
- `post-market-review` 可从 repository 恢复当日最新 pre-market 风控决策、开放持仓、最新现金和当日已有订单，执行买入、盯市、退出评估、卖出、closed position 落库和复盘。
- `RiskManager` 同时负责买入前风控和退出决策；`PaperTrader` 只生成模拟订单，所有 `PaperOrder.is_real_trade` 固定为 `False`。
- `ReviewMetricsAgent` 只读取截至所选交易日的 `paper_positions`、`paper_orders` 和 `portfolio_snapshots` payload，计算已实现盈亏、胜率、平均持仓天数、卖出原因分布和最大回撤；缺字段、非法数字或真实交易订单必须显式失败。
- `DashboardQueryAgent` 只读封装 `pipeline_runs`、观察名单、信号、风控、模拟订单、持仓、组合快照、复盘和数据源快照查询，输出稳定 DTO。dashboard/API/frontend 后续应依赖该查询层，不直接解析 repository payload。
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
├── cli.py               # Typer CLI
├── config.py            # .env 与 universe 配置
├── dashboard.py         # dashboard query DTO 和聚合服务
├── domain.py            # 标准 domain models
├── indicators.py        # 基础技术指标
├── pipeline.py          # 三段流程编排
├── reports.py           # Markdown 输出
└── repository.py        # In-memory/PostgreSQL repository
```

`src/ashare_agent/agents/dashboard_query_agent.py` 属于只读查询适配层，不参与 pipeline 写入、不执行交易、不修改策略状态。`src/ashare_agent/dashboard.py` 是 API 使用的薄兼容层，避免前端/API 依赖内部 agent 文件路径。

前端代码位于 `frontend/`，使用 React、Vite、TypeScript 和 pnpm。当前页面是本地只读观察台，左侧展示 pipeline runs，右侧按交易日展示观察名单、风控结果、模拟订单、持仓、复盘、数据源状态和运行详情。

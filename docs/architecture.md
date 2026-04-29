# AShareAgent 架构说明

当前状态：已落地 Python 后端骨架、Mock pipeline、CLI、LLM adapter、PostgreSQL/Alembic 初始 schema。前端观察台尚未开始。

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

## 当前边界

- 当前入口是 CLI：`pre-market`、`intraday-watch`、`post-market-review`。
- 默认 provider 是 `MockProvider`；真实公开源通过 `AKShareProvider` 适配，后续再加外部测试标记。
- 默认 LLM 是 mock；`.env` 中设置 `ASHARE_LLM_PROVIDER=openai` 或 `deepseek` 后才调用真实 API。
- PostgreSQL 通过 Alembic 创建 `ashare_agent` schema，业务结果先可写入审计 artifact，核心表分组已预留。
- Streamlit/React dashboard 放到第二阶段，第一阶段只输出 Markdown 报告。
- 模块边界发生变化时，同步更新本文件。

## 代码布局

```text
src/ashare_agent/
├── agents/              # 各业务 Agent
├── llm/                 # Mock/OpenAI/DeepSeek adapter
├── providers/           # Mock/AKShare data provider
├── cli.py               # Typer CLI
├── config.py            # .env 与 universe 配置
├── domain.py            # 标准 domain models
├── indicators.py        # 基础技术指标
├── pipeline.py          # 三段流程编排
├── reports.py           # Markdown 输出
└── repository.py        # PostgreSQL artifact repository
```

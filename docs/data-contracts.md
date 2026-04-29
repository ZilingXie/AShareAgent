# AShareAgent 数据契约

当前状态：已落地第一版 domain models、provider 契约和 PostgreSQL 初始 schema。

## DataProvider 原则

- 业务逻辑依赖统一 `DataProvider` 接口。
- 不直接把业务逻辑绑定到 AKShare、TuShare 或其他外部数据源。
- `MockProvider` 和真实 provider 应返回同一类标准 domain models。
- 默认测试不访问外网；真实数据源测试必须单独标记。

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

## 核心模型

当前代码中的标准模型集中在 `src/ashare_agent/domain.py`：

- 数据输入：`Asset`、`MarketBar`、`AnnouncementItem`、`NewsItem`、`PolicyItem`、`IndustrySnapshot`。
- 分析输出：`AnnouncementEvent`、`TechnicalIndicator`、`MarketRegime`、`LLMAnalysis`。
- 信号与风控：`WatchlistCandidate`、`Signal`、`RiskDecision`。
- 模拟交易：`PaperOrder`、`PaperPosition`、`PortfolioSnapshot`、`ReviewReport`。
- 流程审计：`SourceSnapshot`、`MarketDataset`、`PipelineRunContext`、`AgentResult`。

## PostgreSQL schema

Alembic 初始迁移创建 `ashare_agent` schema，并预留以下表分组：

- `pipeline_runs`
- `universe_assets`
- `raw_source_snapshots`
- `market_bars`
- `announcements`
- `news_items`
- `policy_items`
- `industry_snapshots`
- `technical_indicators`
- `llm_analyses`
- `watchlist_candidates`
- `signals`
- `risk_decisions`
- `paper_orders`
- `paper_positions`
- `portfolio_snapshots`
- `review_reports`
- `artifacts`

第一版 repository 先写通用 `artifacts` 审计表；后续 Agent 分支可以逐步切到专表写入。

## 后续维护

涉及数据模型、provider 契约、字段含义、数据质量或审计要求的变化，必须同步更新本文。

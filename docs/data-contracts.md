# AShareAgent 数据契约

当前状态：已落地第一版 domain models、provider 契约、真实 DataCollector 入口、PostgreSQL 初始 schema 和核心 pipeline 持久化。

## DataProvider 原则

- 业务逻辑依赖统一 `DataProvider` 接口。
- 不直接把业务逻辑绑定到 AKShare、TuShare 或其他外部数据源。
- `MockProvider` 和真实 provider 应返回同一类标准 domain models。
- 默认测试不访问外网；真实数据源测试必须单独标记。
- `ASHARE_PROVIDER=akshare` 只读取 `configs/universe.yml` 中 `enabled=true` 的固定池资产。

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

本地开发复用现有 Podman PostgreSQL 的 `supportportal` 数据库，但所有 AShareAgent 对象都放在独立 `ashare_agent` schema。Alembic 版本表固定为 `ashare_agent.alembic_version`，避免污染共享数据库中其他项目的迁移状态。若 schema 已存在但缺少该版本表，迁移会停止，避免在状态不明的共享库里继续写入。

Alembic 初始迁移创建以下表分组：

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

当前 repository 已将核心运行结果写入专表：

- `pre-market` 先写入 `universe_assets`、`raw_source_snapshots`、`market_bars`、`announcements`、`news_items`、`policy_items`、`technical_indicators`，再写入 `pipeline_runs`、`llm_analyses`、`watchlist_candidates`、`signals`、`risk_decisions` 和 `artifacts`。
- `intraday-watch` 写入 `pipeline_runs` 和 `artifacts`。
- `post-market-review` 从 repository 读取当日最新 pre-market 风控决策和开放持仓；若当前 pipeline 没有内存中的 market dataset，会重新采集并写入 raw/source 专表，再写入 `paper_orders`、`paper_positions`、`portfolio_snapshots`、`review_reports`、`pipeline_runs` 和 `artifacts`。

真实 provider 下 `universe`、`market_bars`、`trade_calendar` 是必需源；这些源失败时，`pre-market` 会先保存失败的 `raw_source_snapshots` 和失败的 `pipeline_runs`，再明确失败。交易日历本轮只保存采集快照和摘要，不新增 `trading_calendar` 表。

`artifacts` 仍保留为报告和聚合 payload 的审计表；专表 payload 是后续连续模拟交易和只读观察台的数据基础。

## 后续维护

涉及数据模型、provider 契约、字段含义、数据质量或审计要求的变化，必须同步更新本文。

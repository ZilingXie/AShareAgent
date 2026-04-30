# CONTEXT.md

## 当前正在做什么

本地共享 Podman PostgreSQL 已接入 AShareAgent，并完成迁移和 mock CLI 落库验收。

## 上次停在哪

本轮已完成：

- 已将 `main` 同步到 GitHub `origin/main`。
- 已用 `ASHARE_PROVIDER=mock`、`ASHARE_LLM_PROVIDER=openai` 跑通一次 `pre-market --trade-date 2026-04-29`，确认 OpenAI adapter、配置加载和报告输出可用。
- 已实现 CLI `DATABASE_URL` 必需校验，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、review reports 的 repository 持久化接线。
- 已复用 Podman 容器 `deployment_local_postgres_1` 的 `supportportal` 数据库，在独立 `ashare_agent` schema 中完成 Alembic 迁移。
- 已用 mock LLM 跑通 `pre-market`、`intraday-watch`、`post-market-review`，确认真实 PostgreSQL 中有对应 pipeline、信号、风控、模拟订单、持仓和复盘记录。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端第一版使用 Python 3.12、Typer CLI、PostgreSQL、Alembic、AKShare provider、Mock provider。
- LLM 默认 mock；可通过 `.env` 切到 OpenAI，DeepSeek adapter 保留。
- CLI 现在必须配置 `DATABASE_URL`；缺失时明确失败，不做静默内存兜底。
- 本地数据库复用共享 PostgreSQL，但 AShareAgent 只使用 `ashare_agent` schema 和 `ashare_agent.alembic_version`，不在 `public` 或 `supportportal` schema 建业务表。
- 前端 dashboard 放到第二阶段，第一版只做 CLI 和 Markdown 报告。
- 初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。验证通过后默认自动提交 task 分支并合并回 `main`。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。

## 下一步

- 基于真实落库结果继续做 dashboard 或更细的持久化查询能力。

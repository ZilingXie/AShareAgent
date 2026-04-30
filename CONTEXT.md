# CONTEXT.md

## 当前正在做什么

OpenAI 验证和 PostgreSQL 持久化接线已完成。当前等待补充真实 PostgreSQL `DATABASE_URL` 后做落库验收。

## 上次停在哪

本轮已完成：

- 已将 `main` 同步到 GitHub `origin/main`。
- 已用 `ASHARE_PROVIDER=mock`、`ASHARE_LLM_PROVIDER=openai` 跑通一次 `pre-market --trade-date 2026-04-29`，确认 OpenAI adapter、配置加载和报告输出可用。
- 已实现 CLI `DATABASE_URL` 必需校验，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、review reports 的 repository 持久化接线。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端第一版使用 Python 3.12、Typer CLI、PostgreSQL、Alembic、AKShare provider、Mock provider。
- LLM 默认 mock；可通过 `.env` 切到 OpenAI，DeepSeek adapter 保留。
- CLI 现在必须配置 `DATABASE_URL`；缺失时明确失败，不做静默内存兜底。
- 真实 PostgreSQL 验收暂等用户补充数据库配置；当前先用自动化测试覆盖持久化接口和状态恢复行为。
- 前端 dashboard 放到第二阶段，第一版只做 CLI 和 Markdown 报告。
- 初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。验证通过后默认自动提交 task 分支并合并回 `main`。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。

## 下一步

- 补齐真实 PostgreSQL `DATABASE_URL` 后，运行 Alembic 迁移和 CLI 落库验收。

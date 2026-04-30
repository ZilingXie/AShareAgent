# CONTEXT.md

## 当前正在做什么

AShareAgent 的 foundation-core MVP 共同底座已合并到 `main` 并同步到 GitHub `origin/main`。本轮已完成收尾记录修正，按计划不改远端分支。

## 上次停在哪

已完成 foundation-core 收尾清理：

- 已删除 `/Users/xieziling/Desktop/personal_proj/AShareAgent-worktrees/foundation-core` worktree。
- 已删除本地 `codex/foundation-core` 分支。
- GitHub 上仅保留 `origin/main`，`origin/codex/foundation-core` 已不存在。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端第一版使用 Python 3.12、Typer CLI、PostgreSQL、Alembic、AKShare provider、Mock provider。
- LLM 默认 mock；可通过 `.env` 切到 OpenAI，DeepSeek adapter 保留。
- 前端 dashboard 放到第二阶段，第一版只做 CLI 和 Markdown 报告。
- 初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。验证通过后默认自动提交 task 分支并合并回 `main`。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。

## 下一步

- 从 clean `main` 创建新的 `codex/<thread-slug>` worktree，继续后续 Agent 分支或 dashboard 第二阶段。

# CONTEXT.md

## 当前正在做什么

AShareAgent 已在 `codex/foundation-core` worktree 中落地 MVP 共同底座，当前正在按新规则提交并合并回 `main`。

## 上次停在哪

已完成初始化文档基线，并在本次继续落地：

- `pyproject.toml`
- `src/ashare_agent/`
- `tests/`
- `migrations/`
- `.env.example`

本次继续补齐 `AGENTS.md` 的自动提交/合并规则，以及相关项目记录和 docs 文件。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端第一版使用 Python 3.12、Typer CLI、PostgreSQL、Alembic、AKShare provider、Mock provider。
- LLM 默认 mock；可通过 `.env` 切到 OpenAI，DeepSeek adapter 保留。
- 前端/Streamlit dashboard 放到第二阶段，第一版只做 CLI 和 Markdown 报告。
- 初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。验证通过后默认自动提交 task 分支并合并回 `main`。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。

## 下一步

- 合并后从 `main` 继续后续 Agent 分支或 dashboard 第二阶段。

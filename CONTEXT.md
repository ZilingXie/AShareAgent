# CONTEXT.md

## 当前正在做什么

AShareAgent 处于 Harness Engineering 初始化阶段。当前重点是补齐项目入口文档、开发规则、skill 推荐清单、worktree 规范和后续需要维护的基础文档。

## 上次停在哪

已完成初始化文档基线的主要文件：

- `README.md`
- `AGENTS.md`
- `skills.md`
- `.gitignore`

本次继续补齐 `AGENTS.md` 中要求维护的项目记录和 docs 文件。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端计划使用 Python 3.12、FastAPI、SQLite、AKShare provider 和 Mock provider。
- 前端计划使用 React、Vite、TypeScript，第一版只做只读观察台。
- 初始化基线提交前允许在根目录补齐文档；初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。

## 下一步

- 推送初始化基线，或开始后端、前端、测试、CI 的 scaffold。
- scaffold 开始后，再补齐具体运行命令和更详细的数据契约。

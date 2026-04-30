# CONTEXT.md

## 当前正在做什么

AnnouncementAnalyzer 固定公告样本回归和分类规则补强已完成，当前 `main` 可继续进入 dashboard 或策略参数硬化。

## 上次停在哪

本轮已完成：

- 已新增公告 golden cases，覆盖分红、减持、诉讼、处罚、重组、风险提示、亏损风险和中性公告。
- 已补强 AnnouncementAnalyzer 的可解释规则：减持、诉讼、处罚/立案、资产重组、风险提示等场景可稳定分类，并在 `reasons` 中保留命中关键词或分类原因。
- 已将 `main` 同步到 GitHub `origin/main`。
- 已用 `ASHARE_PROVIDER=mock`、`ASHARE_LLM_PROVIDER=openai` 跑通一次 `pre-market --trade-date 2026-04-29`，确认 OpenAI adapter、配置加载和报告输出可用。
- 已实现 CLI `DATABASE_URL` 必需校验，以及 pipeline run、watchlist、signals、risk decisions、paper orders、positions、review reports 的 repository 持久化接线。
- 已复用 Podman 容器 `deployment_local_postgres_1` 的 `supportportal` 数据库，在独立 `ashare_agent` schema 中完成 Alembic 迁移。
- 已用 mock LLM 跑通 `pre-market`、`intraday-watch`、`post-market-review`，确认真实 PostgreSQL 中有对应 pipeline、信号、风控、模拟订单、持仓和复盘记录。
- 已让 CLI 支持 `ASHARE_PROVIDER=akshare`，并从 `configs/universe.yml` 读取 enabled 固定池资产。
- 已将 DataCollector 的 universe、raw source snapshots、market bars、announcements、news items、policy items、technical indicators 写入 PostgreSQL。
- 已修复真实行情路径：ETF 日线改用 AKShare `fund_etf_hist_sina`，A 股日线改用 `stock_zh_a_daily`。
- 已跑通 `uv run pytest -m external`，并用 `ASHARE_PROVIDER=akshare`、`ASHARE_LLM_PROVIDER=mock` 跑通 `pre-market --trade-date 2026-04-29`。
- 已确认真实 PostgreSQL 中本次 AKShare run 写入 `raw_source_snapshots=7`、`market_bars=90`、`technical_indicators=3`，且 `public` / `supportportal` schema 未新增 AShareAgent 业务表。
- 已实现 RiskManager/PaperTrader 的模拟持仓生命周期：T+1、涨跌停、单日最大亏损、止损、趋势走弱、最多持有 10 个交易日、sell order 和 closed position 落库。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端第一版使用 Python 3.12、Typer CLI、PostgreSQL、Alembic、AKShare provider、Mock provider。
- LLM 默认 mock；可通过 `.env` 切到 OpenAI，DeepSeek adapter 保留。
- CLI 现在必须配置 `DATABASE_URL`；缺失时明确失败，不做静默内存兜底。
- 本地数据库复用共享 PostgreSQL，但 AShareAgent 只使用 `ashare_agent` schema 和 `ashare_agent.alembic_version`，不在 `public` 或 `supportportal` schema 建业务表。
- 真实公开源下 `universe`、`market_bars`、`trade_calendar` 是必需源；失败时流程明确失败，不能自动切回 Mock。
- EastMoney 历史 K 线端点在本机代理和直连下都会断开；当前真实日线行情统一使用 AKShare/Sina 路径，不使用 Mock 兜底。
- 单日最大亏损按账户总资产回撤口径：用最新 `portfolio_snapshots.total_value` 对比当前盯市总资产，回撤超过 2% 后拒绝新买入。
- PaperTrader 仍是唯一交易执行模块；所有 `PaperOrder.is_real_trade` 必须为 `False`。
- 交易日历本轮只作为 `raw_source_snapshots` 审计快照保存，不新增结构化日历表。
- 公告分析继续使用可解释规则，不引入 LLM 判断；误判追踪先落在固定样本 `case_id` 层，不改变运行时模型或落库边界。
- 前端 dashboard 放到第二阶段，第一版只做 CLI 和 Markdown 报告。
- 初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。验证通过后默认自动提交 task 分支并合并回 `main`。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。

## 下一步

- 下一步可继续补 dashboard 只读观察台，或扩展策略参数版本与更细的数据质量检查。

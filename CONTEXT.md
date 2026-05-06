# CONTEXT.md

## 当前正在做什么

定时 Agent 已完成：新增 `scheduled-run` 统一入口，用于 Codex 自动化按工作日 slot 运行早间采集、盘前简报、盘中模拟决策、收盘采集和收盘复盘简报。

阶段化日线质量检查已完成：`morning_collect`、`pre_market`、`pre_market_brief`、`intraday_watch` 和 `intraday_decision` 只要求日线覆盖到上一交易日，`close_collect` 和 `post_market_review` 才要求当前交易日完整日线。

2026-05-06 已用真实 AKShare provider + mock LLM 跑通 `pre-market -> intraday-watch`；两阶段最新 normal run 均为 success，`data_quality_reports` 没有再因缺少 2026-05-06 当天完整日线阻断。

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
- 本轮新增 DashboardQueryAgent 只读查询层，封装 pipeline runs、watchlist、signals、risk decisions、orders、positions、portfolio snapshots、review reports 和 source snapshots 查询。
- 已实现 dashboard query layer、FastAPI 只读 API 和 React/Vite/TypeScript 前端。
- 已用本地 `DATABASE_URL` 启动 API 和前端，通过 Chrome smoke 确认页面能显示 pipeline runs、观察名单、风控结果、模拟订单、持仓、复盘报告、数据源状态和真实源失败原因。
- 已清理已合入的本地 `codex/announcement-golden-tests` worktree 和本地分支。
- 已新增 `ReviewMetricsAgent`，按截至所选交易日累计统计已实现盈亏、胜率、平均持仓天数、卖出原因分布和最大回撤。
- 已将复盘指标接入 `DashboardQueryAgent` 的 `review_report.metrics` DTO，并在前端复盘报告区域展示。
- 本轮新增 `StrategyParamsAgent`，从 `configs/strategy_params.yml` 加载风控和模拟交易参数，并在每次 `pipeline_runs.payload` 记录 `strategy_params_version` 和 `strategy_params_snapshot`。
- 本轮新增 DataQualityAgent，检查必需源失败/空数据、缺失当日行情、异常价格、source 失败率和非交易日运行提示。
- 新增 `data_quality_reports` 专表和 DashboardQueryAgent DTO，dashboard 已显示每次 run 的数据质量状态和问题明细。
- 已将 `codex/data-quality-agent` 和 `codex/alembic-transaction-fix` 合并回本地 `main`；其中 Alembic 修复确保 schema 状态检查在迁移前提交事务，避免 PostgreSQL aborted transaction 影响后续迁移。
- 已清理 `codex/alembic-transaction-fix` worktree 和本地分支，并将 `main` 同步到 GitHub `origin/main`。
- 本轮新增 `DashboardQueryAgent.trends(start_date, end_date)` 和 `/api/dashboard/trends`，前端范围筛选已改为按日期区间展示趋势，同时保留所选单日明细。
- 已清理已合并的 `codex/dashboard-trends` worktree 和本地分支。
- 本轮更新 AGENTS.md：worktree 任务验证通过后默认进入 `finalizing-to-main`，自动提交、合并、复验、清理 task worktree/分支，并在远端没有分叉时自动 push。
- 本轮新增结构化 `trading_calendar` 表、`DataReliabilityAgent`、`data_reliability_reports`、`ashare daily-run` 和 `scripts/daily_run.sh`。
- dashboard 日汇总和趋势 DTO 已接入交易日历与运行可靠性报告，前端新增“运行可靠性”只读面板。
- 本轮新增独立 `strategy-experiment.md` 策略实验报告，在盘后复盘阶段生成，集中展示盘前 LLM 分析、风控拒绝原因、模拟订单、卖出原因、组合复盘摘要和累计复盘指标。
- 本轮将 `llm_analyses` 接入 `DashboardQueryAgent.day_summary().llm_analysis` DTO，并在前端只读观察台展示“LLM 盘前分析”；模拟订单表同步展示 `PaperOrder.reason` 原文。
- 本轮新增 `signal` 策略参数，SignalEngine 权重、最低分阈值和每日最大信号数已由 `StrategyParamsAgent` 加载并进入完整策略快照。
- 本轮新增 `BacktestRunner` 和 `ashare backtest`，按 provider 交易日历多日执行 `pre_market + intraday_watch + post_market_review` 回放，并用 `run_mode=backtest`、`backtest_id` 隔离回放状态。
- 本轮新增 dashboard backtest 列表和策略版本对比 DTO/API/前端区块，按 `backtest_id` 展示胜率、最大回撤、总收益率、风控拒绝率和数据质量失败率。
- 三阶段职责重排已完成：`pre_market` 只生成信号和风控决策，`intraday_watch` 执行模拟买入/卖出、持仓和组合快照，`post_market_review` 不新增订单，只生成收盘快照、复盘和策略实验报告。
- 本轮已将 `ASharePipeline` 的盘中交易输入准备、模拟买卖执行、盘中报告、收盘复盘总结拆成内部方法，保持现有 CLI/API/schema 不变。
- 前端单日详情已将“模拟订单”改为“盘中模拟订单”，将“复盘报告”改为“收盘复盘”，空状态同步改为“暂无盘中模拟订单”。
- 遗留 `codex/stage-contracts` worktree 已处理，当前 `main` 保留已合入的三阶段职责重排。
- 订单阶段过滤已完成：旧 `post_market_review` 订单保留在数据库中，但 dashboard 盘中订单、盘后 `reviewed_orders`、`reviewed_order_count` 和复盘卖出原因统计只读取可关联到同日成功 `intraday_watch` run 的订单。
- 盘中成交真实度增强已实现：DataProvider 增加分钟线接口，Mock/AKShare provider 可返回标准 `IntradayBar`；PaperTrader 不再用日线 close 成交，订单记录成交来源、价格时间点、估价方法、参考价和 `used_daily_fallback=False`。
- 不可成交不写 `paper_orders`，只在 `intraday_watch` artifact / pipeline payload 的 `execution_events` 中记录失败原因；dashboard 已增加成交依据和成交失败只读展示。
- `intraday-price-realism` 已合并到 `main` 并推送；真实 AKShare `intraday-watch --trade-date 2026-04-29` 暴露 EastMoney 分钟线端点 `push2his.eastmoney.com` 连接断开，数据库已正确记录 failed run 和 failed `raw_source_snapshots(source=intraday_bars)`。
- 本轮分钟线可靠性修复已改为 `AKShareProvider` 直连 EastMoney `trends2/get`，支持 `ASHARE_INTRADAY_SOURCE=akshare_em`、timeout、retry 和 backoff 配置，并在 source snapshot metadata 中记录分钟线源、请求/返回/缺失 symbol、重试和超时参数。
- 外部测试已拆分：`uv run pytest -m external_daily -q` 通过，`uv run pytest -m external_intraday -q` 仍因 EastMoney 分钟线端点返回 ProxyError/RemoteDisconnected 失败，但失败信息已明确包含 `akshare_em`、`symbol=510300`、`attempts=3` 和 `timeout=15.0`。
- 本轮已新增 `akshare_sina` 备用分钟线源：默认仍只用 `akshare_em`，只有显式配置 `ASHARE_INTRADAY_SOURCE=akshare_em,akshare_sina` 时才按链路尝试备用源；`raw_source_snapshots.metadata.source_attempts` 会记录每个 source/symbol 的状态、retry、timeout 和最后错误。
- dashboard 已新增“分钟线源健康”只读展示，读取 `raw_source_snapshots.metadata.source_attempts`，展示 source、symbol、状态、retry、timeout、返回行数和最后错误。
- 已将本机 ignored `.env` 明确配置为 `ASHARE_INTRADAY_SOURCE=akshare_em,akshare_sina`，用于后续真实盘中分钟线验收。
- 真实三阶段日常运行已重新跑通：`pre-market -> intraday-watch -> post-market-review` 最新 normal run 均为 success，可作为后续策略评估基线。
- 最新 `raw_source_snapshots(source=intraday_bars)` 为 success，metadata 显示 `intraday_source=akshare_em,akshare_sina`；`akshare_em` 对 510300 仍因 EastMoney/代理连接失败，随后 `akshare_sina` 成功返回 240 条 1 分钟 K 线。
- dashboard smoke 已确认页面可见“分钟线源健康”、`akshare_em`、`akshare_sina`、盘中模拟订单、成交失败和收盘复盘区块。
- 本轮已清理 dashboard 策略版本对比 duplicate key warning：backtest 列表和策略对比按 `backtest_id` 保序去重，只读展示层保留最新 summary，不删除历史回放数据。
- 本轮新增 `StrategyEvaluationRunner`、`CachingDataProvider` 和 `ashare strategy-evaluate`，读取 `configs/strategy_evaluation.yml` 后按 variant 生成独立 `backtest_id`，复用真实源缓存并输出 `reports/<evaluation_id>/strategy-evaluation.md`。
- 策略评估聚合结果复用现有 `pipeline_runs(stage=strategy_evaluation)` 和 `artifacts(artifact_type=strategy_evaluation)`，不新增数据库迁移；单个 variant 明细继续复用 backtest 专表和 `backtest_id` 隔离。
- 本轮新增 dashboard 策略评估只读查询/API/前端视图：可列出 evaluation 批次，查看 variant 收益、命中率、回撤、失败率、推荐结论、不可推荐原因和 Markdown 报告路径。
- 本轮重组 dashboard 前端为四大看板：`总览` 聚焦资产、盈亏、持仓和复盘摘要；`交易执行` 聚焦盘前计划、风控、盘中订单和成交失败；`策略` 聚焦信号、拒绝原因、策略对比和策略评估；`质量` 聚焦数据质量、运行可靠性、分钟线源健康、数据源状态和运行详情。左侧 run 卡片点击后打开只读阶段详情抽屉，不新增 API、schema、写接口或交易按钮。
- 本轮已将策略评估默认窗口扩展为 `default_window_trade_days=60`，并在评估 payload / Markdown 报告中补充日均信号、无信号天数、买入后 2/5/10 个交易日表现、卖出触发原因、市场环境覆盖和参数差异。
- 已用真实 AKShare provider + mock LLM 跑通 `eval-real-60d-20260501-r4`：窗口为 2026-01-28 到 2026-04-30，共 60 个交易日、3 个 variant，全部 succeeded_days=60、failed_days=0；报告已生成到 `reports/eval-real-60d-20260501-r4/strategy-evaluation.md`。
- 为支撑长窗口验收，`PostgresRepository` 已增加按 `backtest_id` 过滤 payload 的读取接口，并将结构化交易日历保存改为分批 bulk upsert，避免策略评估汇总和多日回放在真实 PostgreSQL 上反复全表扫描或单行 upsert。
- 本轮新增 `StrategyInsightAgent`、`HypothesisVariantBuilder`、`StrategyInsightGate` 和 `ashare strategy-insight`：LLM 只生成 hypotheses JSON，白名单编译后复用 20/40/60 日评估窗口，结果写入 `pipeline_runs(stage=strategy_insight)`、`artifacts(artifact_type=strategy_insight)` 和 `reports/<insight_id>/strategy-insights.md`。
- dashboard/API/frontend 已新增“策略优化”只读视图，展示 LLM 假设、参数变更、policy reject 原因、三窗口评估结果、gate 结论和 `待复核` 状态；不提供接受/拒绝按钮，不自动修改生产策略配置。
- 本轮新增 dashboard 阶段运行组：`DashboardQueryAgent.list_stage_run_groups()` 和 `stage_run_group_detail()` 按 `trade_date + stage` 聚合 normal runs，混合成功/失败显示 `partial_failure`，详情保留全部成员 run 和每条业务数据的 `run_id`。
- 前端左侧列表已改为阶段组卡片；点击 `盘前 / 盘中 / 复盘 / 策略优化` 阶段组打开只读详情抽屉，盘前展示观察名单/信号/LLM/风控，盘中展示订单/成交失败/分钟线源健康/持仓/资金快照，复盘展示复盘报告和报告路径。
- 本轮已修复左侧阶段组排序：日期由近到远，每个日期内固定为 `盘前 -> 盘中 -> 复盘 -> 策略优化`，未知 stage 保留在已知 stage 之后。
- 本轮已修复 DataQualityAgent 的日线质量窗口：盘前和盘中只检查原 30 日窗口中截至上一交易日的日线完整性，盘后才检查当天完整日线。
- 2026-05-06 真实盘中验收已通过：`pre_market` 最新 normal run 为 success，`intraday_watch` 最新 normal run 为 success；两条 `data_quality_reports` 均为 warning，但 `missing_market_bar_count=0`、`abnormal_price_count=0`，没有缺 5/6 当日日线问题。最新 `raw_source_snapshots(source=intraday_bars)` 为 success，`intraday_source=akshare_em,akshare_sina`，本次 `akshare_em` 对 510300 返回 121 条分钟线。期间一次盘中重跑遇到 600000 Sina 日线代理 503，已按 failed run 和质量报告审计，随后重跑成功。
- 本轮新增 `ScheduledRunAgent` 和 `ashare scheduled-run`：支持 `morning_collect`、`pre_market_brief`、`call_auction`、`intraday_decision`、`close_collect`、`post_market_brief` 六个 slot；每个 slot 先检查交易日历，非交易日写 skipped。`call_auction` 第一版 disabled，`pre_market_brief` / `intraday_decision` / `post_market_brief` 分别委托既有三阶段并额外生成分时 Markdown 简报。

## 近期关键决定和原因

- v1 只允许 `PaperTrader`，不接真实券商，不做真实下单，避免过早引入交易安全风险。
- 后端第一版使用 Python 3.12、Typer CLI、PostgreSQL、Alembic、AKShare provider、Mock provider。
- LLM 默认 mock；可通过 `.env` 切到 OpenAI，DeepSeek adapter 保留。
- CLI 现在必须配置 `DATABASE_URL`；缺失时明确失败，不做静默内存兜底。
- 本地数据库复用共享 PostgreSQL，但 AShareAgent 只使用 `ashare_agent` schema 和 `ashare_agent.alembic_version`，不在 `public` 或 `supportportal` schema 建业务表。
- 真实公开源下 `universe`、`market_bars`、`trade_calendar` 是必需源；失败时流程明确失败，不能自动切回 Mock。
- 数据质量门禁按“严重阻断”执行：必需源失败/空数据、阶段要求窗口内缺失近 30 个交易日行情和异常价格会阻断 pipeline；非交易日运行只提示。日线窗口按 stage 判定：`pre_market` / `intraday_watch` 到上一交易日，`post_market_review` 到当天。
- EastMoney 历史 K 线端点在本机代理和直连下都会断开；当前真实日线行情统一使用 AKShare/Sina 路径，不使用 Mock 兜底。
- 单日最大亏损按账户总资产回撤口径：用最新 `portfolio_snapshots.total_value` 对比当前盯市总资产，回撤超过 2% 后拒绝新买入。
- PaperTrader 仍是唯一交易执行模块；所有 `PaperOrder.is_real_trade` 必须为 `False`。
- `intraday_watch` 必须依赖同日成功 `pre_market` 风控决策；缺失时显式失败并写 failed run，不空跑。
- `post_market_review` 不再新增 `paper_orders`；盘后只读取盘中订单和持仓，生成收盘盯市、复盘和审计。
- 历史 `post_market_review` 模拟订单不删除、不迁移；读取层用 `pipeline_runs.stage` 过滤，新阶段语义只承认成功 `intraday_watch` run 生成的盘中订单。
- 盘中模拟成交只能使用分钟线估价，不允许日线 close 兜底成交；缺少分钟线、停牌、买入涨停或卖出跌停都必须记录 rejected execution event，不能写失败订单。
- 分钟线源整体不可用时必须 failed run；单个 symbol 正常响应但无分钟线时不视为 provider 失败，由 `IntradayPriceEstimator` 记录 rejected execution event。
- 分钟线备用源不能静默启用；只有显式配置 source chain 时才允许从 `akshare_em` 尝试到 `akshare_sina`。
- 策略参数使用显式版本号加完整快照，不使用自动哈希；当前已覆盖风控、模拟交易和 SignalEngine 评分参数。
- backtest 结果不新增数据库表，每个交易日必须按 `pre_market -> intraday_watch -> post_market_review` 执行；订单只归属 `intraday_watch` run，并用现有 payload 专表和 `backtest_id` 隔离。
- backtest 强制使用 mock LLM，避免多日回放消耗真实 API；真实数据失败必须记录失败并继续后续日期，不能切回 Mock 或伪造数据。
- strategy-evaluate 同样强制使用 mock LLM，不修改 `configs/strategy_params.yml`；当 `ASHARE_PROVIDER=akshare` 时要求 `ASHARE_INTRADAY_SOURCE` 包含 `akshare_sina`，确保真实分钟线 fallback 链路被纳入评估。
- 策略评估运行入口只输出历史模拟指标和人工复核建议，不做自动参数搜索，不接真实交易；默认窗口用最近 60 个交易日，CLI 显式日期范围优先。
- 策略评估 dashboard 只解释历史模拟结果，不读取 Markdown 正文，不重新计算 backtest，不自动修改策略参数，也不把评估结论包装成实盘建议；本轮不改 dashboard 前端。
- 策略优化闭环采用“LLM 提假设、代码验证、人来批准”：LLM 只能输出解释和候选假设，`HypothesisVariantBuilder` 只允许白名单参数进入 variants，采纳参数必须后续人工另起变更修改 `configs/strategy_params.yml`。
- dashboard/API/frontend 后续只能依赖 DashboardQueryAgent DTO；查询层内部可读 payload，但遇到坏数据或真实交易标记必须显式失败。
- dashboard 阶段组只是读取层聚合，不改变 pipeline 写入，不删除旧 `pipeline_runs`、订单或报告；日常总览仍用最新成功 run 作为 canonical 数据，阶段详情才展示全部尝试。
- 交易日历现在保存为结构化 `trading_calendar` 事实表；DataCollector 从 provider 交易日列表展开连续日期行，并按 `calendar_date/source` upsert。
- `daily-run` 遇到非交易日默认写 skipped 审计和可靠性报告，不进入策略分析，也不更新模拟订单或持仓。
- `scheduled-run` 是 Codex 自动化和本机定时器的统一入口；它只编排已有阶段和分时简报，不绕过 DataQualityAgent、RiskManager 或 PaperTrader。10:00 `intraday_decision` 只执行模拟买卖，其他 slot 不允许新增 `paper_orders`。
- 公告分析继续使用可解释规则，不引入 LLM 判断；误判追踪先落在固定样本 `case_id` 层，不改变运行时模型或落库边界。
- 观察台只读，不直接连接 PostgreSQL，不提供交易操作入口；`PaperOrder.is_real_trade` 必须在 API DTO 和 UI 中显式展示，正常值为 `False`。
- dashboard 第一版持有天数用自然日差计算，后续有结构化交易日历表后再替换为交易日口径。
- 复盘指标只基于已落库模拟交易审计数据，不新增数据库迁移，不接真实交易；卖出原因分布使用模拟卖单 `reason` 原文。
- 最大回撤按 `portfolio_snapshots.total_value` 序列计算，不基于单票价格或未落库临时估值。
- dashboard 趋势按日期范围闭区间查询；信号、通过/拒绝和风控拒绝原因只使用当天最新成功 `pre_market` run，避免旧 run 重复计数。
- 数据质量趋势按天取最大 source 失败率，阻断次数统计 `status=failed` 报告数，warning 次数统计 `severity=warning` issue 数。
- 初始化基线提交后，repo-tracked 修改默认走 `codex/<thread-slug>` worktree。验证通过后默认自动完整收尾：提交 task 分支、合并回 `main`、复验、清理 worktree/分支，并在远端没有分叉时自动 push。
- `CONTEXT.md` 保持极简，只记录当前状态、停靠点和关键决定。
- 策略实验报告和 dashboard LLM 展示只读取已落库审计数据；dashboard 查询没有 LLM 记录时返回 `null`，记录存在但 payload 坏数据时显式失败。
- 模拟订单原因统一展示 `PaperOrder.reason` 原文；卖出原因只按卖单原因计数，不做自动归类。

## 下一步

- 定时 Agent 合并到 `main` 后，需要配置 5 个 Codex 工作日自动化：08:30 `morning_collect`、09:00 `pre_market_brief`、10:00 `intraday_decision`、15:15 `close_collect`、16:00 `post_market_brief`；09:25 `call_auction` 暂不启用。
- 以 2026-05-06 成功盘前/盘中作为后续真实日常运行基线；当天 `post-market-review` 仍必须等完整日线可用后再跑。
- 若后续真实外部源失败，只记录失败阶段、source、symbol 和错误原因；不切 Mock、不伪造行情。
- 继续保持 v1 只做模拟交易：不接真实券商、不自动实盘下单、不自动修改生产策略参数。

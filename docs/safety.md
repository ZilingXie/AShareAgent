# AShareAgent 安全边界

当前状态：已落地 Mock pipeline、真实数据入口、分钟线模拟成交估价、DataQualityAgent 质量门禁、DataReliabilityAgent 运行可靠性报告、结构化交易日历、daily-run、完整 PaperTrader 模拟持仓生命周期、策略参数版本审计、多日 backtest 回放和只读观察台。本文记录项目必须长期遵守的交易和数据安全边界。

## 交易边界

- v1 只允许 `PaperTrader`。
- 禁止接入真实券商账户。
- 禁止自动真实下单。
- 禁止写收益承诺。
- 禁止输出荐股结论或投资建议。
- 真实交易能力不进入 v1；未来如果需要讨论，必须先做单独安全设计。
- 当前代码不包含 broker、real order 或 live trading 模块。
- `PaperOrder.is_real_trade` 必须始终为 `False`。
- `PaperTrader` 只允许生成模拟订单；卖出同样只写入 `paper_orders` 和 `paper_positions`，不接任何真实交易通道。
- 当前默认退出规则由 `configs/strategy_params.yml` 驱动：T+1、止损 5%、趋势走弱、最多持有 10 个交易日；止损可在 T+1 后突破最少持有 2 个交易日限制。
- `BacktestRunner` 只运行 `PaperTrader` 模拟交易闭环，使用 `backtest_id` 隔离状态，不提供真实交易或模拟交易手动操作入口。
- `intraday-watch` 是唯一允许新增模拟订单的日内阶段，且必须依赖同日成功 `pre-market` 风控决策；缺失决策时必须显式失败并写 failed run。
- 盘中模拟成交必须使用分钟线估价；不允许用日线 close 兜底成交。缺少分钟线、停牌、买入涨停或卖出跌停时不写失败订单，只写 rejected execution event。
- `post-market-review` 不允许新增模拟订单，只能读取盘中订单，生成收盘持仓/组合快照、复盘和审计报告。
- `DashboardQueryAgent` 和未来 dashboard/API/frontend 只能读取模拟交易数据，不允许提供真实下单入口；查询到 `paper_orders.is_real_trade=True` 时必须显式失败。
- 只读观察台只展示已有审计数据，不提供任何买入、卖出、调仓、真实交易或模拟交易执行按钮。
- 观察台必须显式展示 `PaperOrder.is_real_trade`；正常模拟订单为 `False`。
- 观察台必须显式展示模拟订单的成交依据、估价方法、价格时间点和 `used_daily_fallback`；正常模拟订单 `used_daily_fallback` 为 `False`。

## 数据边界

- 金融数据不可捏造。
- 数据缺失、接口失败、规则不确定时，必须显式失败或标记失败。
- 不允许静默兜底、吞错或伪造结果。
- 所有信号、风控和复盘结论都必须能追溯输入来源、运行时间和决策原因。
- 每次 pipeline run、watchlist 和 signal 必须记录策略参数版本和参数快照，确保复盘能追溯当时使用的风控、模拟交易和信号参数。
- 真实公开源模式下，`universe`、`market_bars`、`trade_calendar` 是必需源；失败时必须记录失败快照和质量报告并让流程失败，不能自动切回 Mock。
- 盘中分钟线 provider 显式配置的 source chain 整体失败时必须记录 failed `raw_source_snapshots(source=intraday_bars)` 和 failed run，snapshot metadata 必须保留具体分钟线源、请求 symbol、timeout、retry、失败 symbol 和逐 source 的尝试结果；未显式配置链路时不能自动切换备用源。单个 symbol 无分钟线或无有效成交时只记录 rejected execution event，不能造价成交。
- 必需源空数据、交易日缺失当日行情、OHLC 异常、成交量/成交额为负或相邻收盘价异常跳变时，必须阻断后续策略分析或模拟交易更新。
- 交易日内近 30 个交易日行情缺口必须进入质量门禁和运行可靠性报告；不能用旧行情、Mock 或空记录补齐。
- 非交易日 `daily-run` 只记录 skipped 审计、结构化交易日历和运行可靠性报告，不进入策略分析，也不更新模拟订单或持仓；非交易日不能伪造成交易日。

## Mock 边界

- `MockProvider` 允许用于测试和回放。
- 生产配置必须禁用 Mock 数据源。
- 测试中的 Mock 数据必须可识别，不能伪装成真实行情、公告或交易结果。

## LLM 边界

- LLM 只做盘前结构化分析辅助。
- backtest 强制使用 mock LLM，避免多日回放消耗真实 API；LLM 不参与 SignalEngine 或 RiskManager 决策。
- 买入信号只能由 `SignalEngine` 规则生成，并必须经过 `RiskManager`。
- `.env` 中的 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 不进入 Git。
- LLM 输出不得写收益承诺、荐股结论或真实交易建议。

## 后续维护

涉及交易、安全、风控、真实数据边界或 Mock 使用边界的变化，必须同步更新本文。

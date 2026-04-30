# AShareAgent 安全边界

当前状态：已落地 Mock pipeline、真实数据入口、完整 PaperTrader 模拟持仓生命周期、策略参数版本审计和只读观察台。本文记录项目必须长期遵守的交易和数据安全边界。

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
- `DashboardQueryAgent` 和未来 dashboard/API/frontend 只能读取模拟交易数据，不允许提供真实下单入口；查询到 `paper_orders.is_real_trade=True` 时必须显式失败。
- 只读观察台只展示已有审计数据，不提供任何买入、卖出、调仓、真实交易或模拟交易执行按钮。
- 观察台必须显式展示 `PaperOrder.is_real_trade`；正常模拟订单为 `False`。

## 数据边界

- 金融数据不可捏造。
- 数据缺失、接口失败、规则不确定时，必须显式失败或标记失败。
- 不允许静默兜底、吞错或伪造结果。
- 所有信号、风控和复盘结论都必须能追溯输入来源、运行时间和决策原因。
- 每次 pipeline run 必须记录策略参数版本和参数快照，确保复盘能追溯当时使用的风控与模拟交易参数。
- 真实公开源模式下，`universe`、`market_bars`、`trade_calendar` 是必需源；失败时必须记录失败快照并让流程失败，不能自动切回 Mock。

## Mock 边界

- `MockProvider` 允许用于测试和回放。
- 生产配置必须禁用 Mock 数据源。
- 测试中的 Mock 数据必须可识别，不能伪装成真实行情、公告或交易结果。

## LLM 边界

- LLM 只做盘前结构化分析辅助。
- 买入信号只能由 `SignalEngine` 规则生成，并必须经过 `RiskManager`。
- `.env` 中的 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 不进入 Git。
- LLM 输出不得写收益承诺、荐股结论或真实交易建议。

## 后续维护

涉及交易、安全、风控、真实数据边界或 Mock 使用边界的变化，必须同步更新本文。

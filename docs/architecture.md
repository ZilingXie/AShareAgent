# AShareAgent 架构说明

当前状态：文档基线阶段。项目还没有后端代码、前端代码或可运行 pipeline。

## 目标架构

AShareAgent 目标是构建一个面向 A 股研究与模拟交易的 Agent 工程框架。第一阶段先跑通可测试、可复现、可审计的最小闭环。

计划中的最小 pipeline：

```text
DataCollector -> AnnouncementAnalyzer -> MarketRegimeAnalyzer -> SignalEngine -> RiskManager -> PaperTrader -> ReviewAgent
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `DataCollector` | 获取、标准化和缓存公告、新闻、行情、指数、板块和交易日历数据。 |
| `AnnouncementAnalyzer` | 将公告转换为结构化事件，判断分类、利好/利空、重大性和排除原因。 |
| `MarketRegimeAnalyzer` | 判断指数趋势、成交量、板块强弱和市场风险偏好。 |
| `SignalEngine` | 执行策略规则，对候选股票评分，并决定是否进入观察名单。 |
| `RiskManager` | 处理仓位、涨跌停、T+1、黑名单和单日最大亏损等交易前风控。 |
| `PaperTrader` | 执行模拟买入、模拟卖出、成交价格估算、滑点估算和持仓记录。 |
| `ReviewAgent` | 生成收盘复盘、策略统计、错误归因和参数调整建议。 |

## 当前边界

- 当前只有文档和规则，没有运行时代码。
- 具体包结构、API、数据库表和前端页面等 scaffold 后再细化。
- 模块边界发生变化时，同步更新本文件。


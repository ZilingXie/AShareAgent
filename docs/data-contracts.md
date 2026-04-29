# AShareAgent 数据契约

当前状态：文档基线阶段。具体 schema、字段类型和数据库表结构将在 scaffold 后细化。

## DataProvider 原则

- 业务逻辑依赖统一 `DataProvider` 接口。
- 不直接把业务逻辑绑定到 AKShare、TuShare 或其他外部数据源。
- `MockProvider` 和真实 provider 应返回同一类标准 domain models。
- 默认测试不访问外网；真实数据源测试必须单独标记。

## 审计字段原则

后续核心数据模型应保留足够的审计信息，至少覆盖：

- 数据来源。
- 数据时间。
- 采集或运行时间。
- `run_id`。
- `trade_date`。
- 股票代码或市场标识。
- 决策原因。
- 失败原因或排除原因。

## 当前不提前定义的内容

- 不在文档基线阶段提前定义完整字段 schema。
- 不提前定义数据库表结构。
- 不提前固定 API response 结构。

这些内容等后端 scaffold、最小 pipeline 和测试夹具开始落地后再细化。

## 后续维护

涉及数据模型、provider 契约、字段含义、数据质量或审计要求的变化，必须同步更新本文。


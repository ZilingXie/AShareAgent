# AShareAgent

面向 A 股研究与模拟交易的 Agent 工程框架。

当前状态：`Planning / Harness Engineering`

本项目现阶段的重点不是追求策略复杂度，而是先建立一套可复现、可测试、可审计的工程底座。所有模块、接口和运行入口都应服务于一个目标：让后续策略开发可以在清晰边界和质量门禁下持续演进。

## 安全边界

- v1 只实现 `PaperTrader`，用于模拟交易和策略验证。
- 不连接真实券商账户。
- 不自动执行真实买入或卖出。
- 不提供荐股、收益承诺或投资建议。
- 所有交易相关能力必须默认停留在模拟环境，并保留可追踪的决策原因和输入数据快照。

## 项目目标

第一阶段目标是跑通一个可测试的最小闭环：

`DataCollector -> AnnouncementAnalyzer -> MarketRegimeAnalyzer -> SignalEngine -> RiskManager -> PaperTrader -> ReviewAgent`

这个闭环应支持：

- 使用 Mock 数据稳定回放核心流程。
- 使用 AKShare provider 接入少量真实公开数据。
- 用规则基线完成公告分类、利好/利空、重大性判断。
- 对候选股票进行评分，并经过风控过滤后进入模拟交易。
- 在收盘后生成复盘结果、策略统计和错误归因。

## 模块设计

```text
AShareAgent
├── DataCollector
│   ├── 公告抓取
│   ├── 新闻抓取
│   ├── 行情抓取
│   ├── 指数/板块数据
│   └── 交易日历
│
├── AnnouncementAnalyzer
│   ├── 公告分类
│   ├── 利好/利空判断
│   ├── 是否重大
│   └── 是否需要排除
│
├── MarketRegimeAnalyzer
│   ├── 指数趋势
│   ├── 成交量
│   ├── 板块强弱
│   └── 风险偏好
│
├── SignalEngine
│   ├── 策略规则
│   ├── 候选股票评分
│   └── 是否进入观察名单
│
├── RiskManager
│   ├── 仓位限制
│   ├── 涨跌停风险
│   ├── T+1 风险
│   ├── 黑名单过滤
│   └── 单日最大亏损
│
├── PaperTrader
│   ├── 模拟买入
│   ├── 模拟卖出
│   ├── 成交价格估算
│   └── 滑点估算
│
└── ReviewAgent
    ├── 收盘复盘
    ├── 策略统计
    ├── 错误归因
    └── 参数调整建议
```

### 模块职责边界

- `DataCollector`：负责数据获取、标准化和缓存，不直接做投资判断。
- `AnnouncementAnalyzer`：负责将公告转成结构化事件和规则判断结果，不直接生成交易指令。
- `MarketRegimeAnalyzer`：负责判断市场环境、板块强弱和风险偏好，为信号和风控提供上下文。
- `SignalEngine`：负责策略规则、候选股票评分和观察名单决策，不绕过风控。
- `RiskManager`：负责所有交易前风险过滤和仓位约束，是模拟交易前的强制门禁。
- `PaperTrader`：负责模拟成交、持仓、滑点和资金曲线，不接真实交易通道。
- `ReviewAgent`：负责复盘、统计、错误归因和参数调整建议，不直接修改生产策略参数。

## 工程原则

- 可复现：关键流程必须能用固定输入重复运行并得到稳定输出。
- 可测试：每个 Agent 都应有独立测试，跨 Agent 的 pipeline 要有集成测试。
- 数据源适配器：业务逻辑依赖统一 `DataProvider` 接口，不直接绑定 AKShare 或其他外部数据源。
- 规则先行：第一版公告分析优先使用可解释规则，LLM 能力只预留接口，不作为核心依赖。
- 真实交易隔离：真实交易能力不进入 v1，任何相关扩展都必须先经过单独安全设计。
- 审计可追踪：信号、风控、模拟成交和复盘都必须记录输入、输出、时间和决策原因。

## 计划中的技术栈

后端：

- Python
- FastAPI
- SQLite
- AKShare provider
- Mock provider
- pytest
- ruff
- pyright

前端：

- React
- Vite
- TypeScript
- 只读观察台

工程：

- GitHub Actions
- pre-commit
- `.env.example`
- `AGENTS.md`
- `docs/`

## TODO

### Phase 0: Harness Engineering

- [ ] 建立后端工程骨架。
- [ ] 建立前端工程骨架。
- [x] 创建根目录 `AGENTS.md`，定义开发 Agent 必须遵守的编码、测试和安全规则。
- [x] 创建 `CONTEXT.md`，记录当前状态、停靠点和关键决定。
- [x] 创建 `docs/architecture.md`，记录模块边界和数据流。
- [x] 创建 `docs/safety.md`，记录 PaperTrader 边界和真实交易禁用规则。
- [x] 创建 `docs/data-contracts.md`，记录核心 domain models 和 provider 契约。
- [x] 创建 `docs/research-log.md`，记录外部调研结论。
- [ ] 配置 ruff、pyright、pytest、pre-commit 和 GitHub Actions。

### Phase 1: Minimal Pipeline

- [ ] 定义统一 `DataProvider` 接口。
- [ ] 实现 `MockProvider`，用于无外网测试和固定回放。
- [ ] 实现最小 `AKShareProvider`，只接入第一批必要 A 股数据。
- [ ] 实现公告规则分析基线。
- [ ] 实现候选股票评分规则。
- [ ] 实现风险过滤规则。
- [ ] 实现 PaperTrader 的模拟买入、模拟卖出、滑点估算和持仓记录。
- [ ] 实现 ReviewAgent 的收盘复盘和基础策略统计。
- [ ] 用 Mock 数据跑通完整 pipeline integration test。

### Phase 2: Read-only Web Console

- [ ] 展示 pipeline run 列表。
- [ ] 展示候选股票评分。
- [ ] 展示风控拒绝原因。
- [ ] 展示模拟持仓和资金曲线。
- [ ] 展示收盘复盘结果。

### Phase 3: Hardening

- [ ] 增加公告样本 golden tests。
- [ ] 增加 provider contract tests。
- [ ] 增加数据质量检查。
- [ ] 增加 pipeline run 审计日志。
- [ ] 增加策略参数版本记录。

## 开发入口

项目尚未 scaffold，具体安装、运行、测试和本地开发命令会在工程骨架建立后补充。

在命令补齐前，README 只作为团队内部工程入口和设计约束，不代表当前已有可运行程序。

## 文档导航

当前文档：

- `CONTEXT.md`：当前状态、停靠点和近期关键决定。
- `AGENTS.md`：开发 Agent 的编码规范、测试要求、安全约束和协作规则。
- `skills.md`：本项目推荐使用的 Codex skills。
- `docs/architecture.md`：系统架构、模块职责、数据流和 pipeline 设计。
- `docs/safety.md`：模拟交易边界、真实交易禁用规则和风险控制原则。
- `docs/data-contracts.md`：核心数据模型、provider 契约和数据质量要求。
- `docs/research-log.md`：外部调研记录和采纳结论。

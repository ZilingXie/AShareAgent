# AGENTS.md | AShareAgent 开发规则

本文件是 AShareAgent 仓库内的开发规则。它约束所有 Agent 和开发者在本项目中的沟通、工程实现、测试、文档和金融安全边界。

## 一、核心原则

1. 从原始需求出发。动机不清、目标不清或验收标准不清时，先停下来问清楚。
2. 用中文沟通，结论先行，少废话。解释要简单直白，让非技术背景的人也能看懂。
3. 不使用 `P0/P1/P2` 这类优先级术语；需要表达严重程度时，用普通中文说明影响。
4. 显式失败，不静默兜底。数据缺失、接口失败、规则不确定时，必须报错或标记失败，不能造数据、吞错误或偷偷降级。
5. 自主完成明确的小任务；遇到会改变方向、范围、数据安全或破坏性操作的分叉点，再停下来确认。

## 二、项目启动顺序

开始任务前，按需读取项目上下文：

1. 优先读 `CONTEXT.md`；如果不存在，直接跳过。
2. 再根据任务需要读 `README.md`。
3. 涉及 skill 选择、复杂任务或新功能时，读 `skills.md`。
4. 涉及架构、模块边界或数据流时，读 `docs/architecture.md`。
5. 涉及交易、风控、数据真实性或安全边界时，读 `docs/safety.md`。
6. 涉及数据模型、provider、字段含义或数据质量时，读 `docs/data-contracts.md`。

外部调研结论记录在 `docs/research-log.md`，不要把搜索记录塞进 `README.md`。

## 三、项目记录规范

阶段性完成后，更新极简 `CONTEXT.md`，只记录：

- 当前正在做什么。
- 上次停在哪。
- 近期关键决定和原因。

只有发生以下变化时，才同步更新对应文档：

- 模块边界、调用关系或 pipeline 变化：更新 `docs/architecture.md`。
- 交易、安全、风控或真实数据边界变化：更新 `docs/safety.md`。
- 数据模型、provider 契约或数据质量规则变化：更新 `docs/data-contracts.md`。
- 运行方式、依赖、命令或项目入口变化：更新 `README.md`。
- 外部方案调研或重要资料来源变化：更新 `docs/research-log.md`。

## 四、工程工作流

1. 需求不明确时，先问清楚再动手。
2. 修 Bug 时，先查原因、上下游影响和是否存在同类问题，再提出修改方案。
3. 涉及数据库变更、删除文件、破坏性 Git 操作或安全边界变化时，必须先确认。
4. 每次改动后运行对应验证；没有可运行的测试或检查命令时，明确说明原因。
5. 不为了让测试通过而削弱规则、删除断言或放宽金融安全边界。
6. 使用 skill 时，优先遵循 `skills.md` 的项目推荐清单。
7. 分支和 worktree 规则见本文件的“分支与 Worktree 规则”。

## 五、分支与 Worktree 规则

1. 当前仓库还没有首个 commit，现有 `README.md`、`AGENTS.md`、`skills.md`、`.gitignore` 属于初始化基线；初始化基线提交后，本节规则开始严格生效。
2. 初始化基线之后，所有 repo-tracked 修改默认必须在独立 task worktree 中完成，除非用户明确要求在根目录直接修改。
3. 根目录必须长期保持 clean `main`，只用于浏览、同步 `main`、创建或检查 worktree、fast-forward 本地 `main`。
4. `main` 是唯一长期主分支；不要创建 `mac`、`mac-integration` 或临时集成分支。
5. 这里的 thread 指 Codex conversation thread，不是单个 shell session。
6. 一个 thread 同时只能绑定一个活跃 `codex/<thread-slug>` 分支和一个 worktree；暂停后继续复用同一个分支和 worktree。
7. 创建 worktree 前、恢复暂停任务前、合并前、清理前，必须运行：
   - `git status --short --branch`
   - `git branch -vv`
   - `git worktree list --porcelain`
8. 继续工作前必须说明当前分支名、绑定 worktree 路径、worktree 是否 clean，以及状态是 active、paused-not-finalized 还是 finalizing-to-main。
9. 如果根目录 dirty、detached HEAD、位于 `codex/*` 分支、分支已被其他 worktree 占用，或存在不明未提交改动，必须停下来说明情况，不能自行 stash、覆盖、强切或删除。
10. 默认 worktree 路径使用仓库同级目录：`../AShareAgent-worktrees/<thread-slug>`。
11. 默认创建方式：
    - 先确认根目录是 clean `main`。
    - 再同步 `origin/main`；如果远端 `main` 还不存在，先完成初始化基线。
    - 然后运行 `git worktree add -b codex/<thread-slug> ../AShareAgent-worktrees/<thread-slug> main`。
12. 不要在根目录直接运行 `git switch -c codex/...`、`git checkout -b codex/...` 或等价命令创建开发分支。
13. 如果 thread 明显切换到另一个功能，在修改前先问用户是继续当前分支还是创建新分支。
14. 任务停止但未合并时，必须报告 `paused, not finalized`，并给出分支名、worktree 路径、clean/dirty 状态。
15. 当前不自动 finalize 到 `main`。worktree 任务验证通过后，先报告任务分类、验证命令、分支名、worktree 路径和结果，等待用户确认后再合并、push 或清理。

任务分类与验证：

- `文档类`：只改文档、规则、注释等非运行内容；用文本检查验证。
- `修复类`：修 Bug、配置错误、脚本错误、逻辑错误；运行直接相关测试或检查。
- `功能类/重大行为变更`：新增能力、改变流程、扩展范围；运行最小但能覆盖行为的测试。

当前 AShareAgent 还没有容器或部署栈，不设置 post-merge live stack 规则。等 `backend/`、`frontend/` 或部署脚本落地后再补。

## 六、Python 环境

1. Python 版本固定为 3.12。
2. 使用 `uv + .venv` 管理后端环境。
3. 优先使用以下命令：
   - `uv sync`
   - `uv run pytest`
   - `uv run ruff check`
   - `uv run pyright`
4. 不直接裸跑 `python`、`pip` 或全局解释器，除非是在创建或修复本地环境。
5. `.venv` 由 `uv` 管理，不手工塞依赖。
6. 依赖、脚本入口或测试命令变化后，要同步更新 `README.md`。

## 七、前端环境

1. 前端技术栈使用 React、Vite、TypeScript。
2. 包管理器固定为 `pnpm`。
3. 不混用 `npm`、`yarn`、`pnpm` 的锁文件。
4. Web UI 第一版定位为只读观察台，不承担真实交易操作入口。

## 八、文件与编码

1. 所有文本文件使用 UTF-8。
2. 文档中文为主，保留必要英文工程名词。
3. 代码注释只在必要时写；业务解释可用中文，明显实现细节不要写废话注释。
4. 修改文件优先使用可靠补丁方式，避免使用会破坏中文编码或重写整文件的 shell 命令。
5. 不改动无关文件；遇到已有未提交变更，先判断是否与当前任务有关，不要擅自回滚。

## 九、A 股项目安全边界

1. v1 只允许 `PaperTrader`。
2. 禁止接入真实券商账户。
3. 禁止自动真实下单。
4. 禁止写收益承诺、荐股结论或投资建议。
5. 真实交易能力不进入 v1；未来如需讨论，必须先做单独安全设计。
6. 金融数据不可捏造。所有信号、风控和复盘结论都必须能追溯输入来源、运行时间和决策原因。
7. `MockProvider` 允许用于测试和回放；生产配置必须禁用 Mock 数据源。
8. 业务逻辑依赖统一 `DataProvider` 接口，不直接绑定 AKShare 或其他外部数据源。

## 十、测试与验证

1. 每个 Agent 都要有独立测试。
2. 跨 Agent 的 pipeline 要有集成测试。
3. 默认测试不访问外网；真实数据源测试必须单独标记，不进入普通 CI。
4. 公告分类、利好/利空和重大性判断应使用固定样本做回归测试。
5. provider 实现必须满足统一契约，Mock provider 和真实 provider 返回同一类标准数据模型。
6. 测试结果汇报只说通过/失败数量和关键失败原因，不逐条复述全部用例。

## 十一、输出规范

1. 用中文回复。
2. 先说结论，再说必要细节。
3. 简单任务用短段落，不强行拆成复杂结构。
4. 多项对比、评审或任务列表可以用 Markdown 表格。
5. 完成任务后，简短说明做了什么、结果是什么、验证是否通过。
6. 如果本次使用了 skill，在最终总结里一句话说明。

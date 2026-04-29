# skills.md | AShareAgent 推荐 Skills

本文件是 AShareAgent 项目的推荐 skill 清单，不是全局白名单，也不覆盖平台或系统强制规则。

使用原则：

- 先判断任务类型，再选择最小必要 skill。
- 优先使用本文件列出的 skill。
- 不因为本机安装了很多 skill，就主动使用和 AShareAgent 无关的 skill。
- 额外 skill 只有在用户明确点名、系统强制要求，或任务确实需要时才使用。

## 推荐 Skills

| Skill | 使用场景 |
| --- | --- |
| `superpowers:using-superpowers` | 会话开始，或需要判断是否应使用 skill 时。 |
| `superpowers:brainstorming` | 新功能、架构、模块边界、行为设计前。 |
| `superpowers:using-git-worktrees` | 初始化基线后，任何 repo-tracked 修改前创建或检查 task worktree。 |
| `superpowers:writing-plans` | 需求明确后，写可交付实现计划。 |
| `superpowers:executing-plans` | 用户明确要求执行已批准计划时。 |
| `superpowers:test-driven-development` | 实现新功能或修 Bug 前。 |
| `superpowers:systematic-debugging` | 遇到 Bug、测试失败或异常行为时。 |
| `superpowers:verification-before-completion` | 声明完成、通过或修复前。 |
| `superpowers:requesting-code-review` | 完成较大功能或合并前自检。 |
| `superpowers:receiving-code-review` | 处理 review 意见时。 |
| `code-reviewer` | 用户要求 review、PR 检查或 diff 检查时。 |
| `frontend-skill` | 实现 Web 观察台、页面、组件或交互时。 |
| `ui-ux-pro-max` | 需要更细 UI/UX 方案、布局或可用性检查时。 |
| `browser-use:browser` | 需要打开本地前端、截图、点击测试或检查 localhost 时。 |
| `openai-docs` | 未来接 OpenAI/LLM adapter、模型选择或 API 用法时；只查官方资料。 |

## 暂缓使用

以下 skill 暂不作为本项目默认推荐。不是永久禁用，后续规则完善后可重新评估。

| Skill | 暂缓原因 |
| --- | --- |
| `superpowers:dispatching-parallel-agents` | 子代理策略还未在项目中定稿。 |
| `superpowers:subagent-driven-development` | 子代理执行流程还未在项目中定稿。 |
| `superpowers:finishing-a-development-branch` | 分支完成流程还未在项目中定稿。 |
| `cloudflare-deploy` | 项目还没有部署目标。 |
| `mcp-builder` | 当前阶段不建设 MCP server。 |
| `skill-creator` | 普通项目开发不创建或修改 Codex skill。 |
| `superpowers:writing-skills` | 普通项目开发不创建或修改 Codex skill。 |

当前阶段也不默认使用 Agora、Jira、Confluence、QA、面试、Outlook、文档、表格、PPT 等与 AShareAgent 无关的 skill。

## 使用要求

- 如果任务同时匹配多个推荐 skill，选择最小必要组合。
- 如果用户明确指定某个 skill，优先按用户要求处理。
- 如果系统或平台强制要求某个 skill，系统或平台规则优先。
- 如果使用了本清单外的 skill，最终回复里用一句话说明原因。

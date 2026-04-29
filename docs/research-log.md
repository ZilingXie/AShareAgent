# AShareAgent 外部调研记录

当前状态：已有第一批外部调研记录。

本文件用于记录外部资料、方案搜索和重要技术决策来源，避免重复调研。不要把搜索记录塞进 `README.md`。

## 记录模板

```markdown
## YYYY-MM-DD | 问题标题

- 问题：
- 来源：
- 结论：
- 是否采纳：
- 备注：
```

## 2026-04-29 | 程序化交易监管边界

- 问题：MVP 是否应避免真实自动下单。
- 来源：中国证监会《证券市场程序化交易管理规定（试行）》发布说明。
- 结论：通过计算机程序自动生成或者下达证券交易指令属于程序化交易监管范围。
- 是否采纳：采纳。v1 只做 `PaperTrader`，不接真实券商，不真实下单。
- 备注：相关安全边界同步记录在 `docs/safety.md`。

## 2026-04-29 | DeepSeek V4 Pro API

- 问题：DeepSeek V4 Pro 是否可作为后续 LLM adapter。
- 来源：DeepSeek 官方 API 文档与 V4 Preview Release。
- 结论：官方模型名包含 `deepseek-v4-pro`，并兼容 OpenAI/Anthropic API 形式。
- 是否采纳：采纳。代码保留 `DeepSeekClient`，但默认不启用。
- 备注：真实调用需要 `.env` 中配置 `DEEPSEEK_API_KEY`。

## 2026-04-29 | AKShare 免费公开源覆盖

- 问题：第一版免费公开源能否覆盖 ETF 日线、公告、新闻和政策文本。
- 来源：AKShare 官方文档。
- 结论：AKShare 提供 ETF 日线、沪深京 A 股公告、个股新闻、新闻联播文本等接口。
- 是否采纳：采纳。第一版 `AKShareProvider` 作为真实公开源 adapter。
- 备注：普通测试默认不访问外网，真实源测试后续单独标记 `external`。

## 2026-04-29 | OpenAI API key 配置

- 问题：本地验证 OpenAI adapter 时如何管理 API key。
- 来源：OpenAI 官方 API 文档。
- 结论：API key 属于 secret，应从环境变量或服务端 key 管理读取，不应暴露在客户端代码中。
- 是否采纳：采纳。`.env` 已加入 `.gitignore`，并提供 `.env.example`。
- 备注：当前 `OpenAIClient` 只在 `ASHARE_LLM_PROVIDER=openai` 时启用。

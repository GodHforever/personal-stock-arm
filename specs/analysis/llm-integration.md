# Feature: LLM 集成模块

## User Story
As a Stock-ARM 用户，I want 系统通过 LiteLLM 统一接入多家大语言模型，支持主力/快速/兜底模型角色分配、Prompt 模板管理、结构化输出解析和 Token 预算控制，so that 我能灵活配置和切换不同 LLM 提供商进行股票分析，同时控制调用成本。

## Acceptance Criteria
- [ ] AC-1: BaseLLMProvider 抽象基类定义 `complete()` 异步方法，LLMResponse 为 Pydantic 数据模型，包含 content、parsed、model、input_tokens、output_tokens、latency_ms、success、error 字段
- [ ] AC-2: LiteLLMRouter 实现 BaseLLMProvider，通过 litellm.acompletion() 调用 LLM，支持从 ConfigManager 读取模型配置
- [ ] AC-3: 无 API Key 时 LiteLLMRouter 可正常初始化，调用 complete() 时返回 success=False 及明确错误信息
- [ ] AC-4: Fallback 机制——主模型调用失败后依次尝试 fallback_chain 中的模型，全部失败返回结构化错误
- [ ] AC-5: 结构化输出——传入 response_schema (Pydantic Model) 时，尝试 JSON 解析 + Pydantic 校验；失败则 retry 一次（附加格式提示）；仍失败返回 parsed=None
- [ ] AC-6: PromptManager 支持从 prompts/ 目录加载 Jinja2 (.j2) 和简单占位符 (.txt) 模板，并渲染变量
- [ ] AC-7: TokenBudgetTracker 在内存中跟踪当日 token 用量，80% 时记录警告日志，100% 时拒绝调用
- [ ] AC-8: 每次 LLM 调用记录日志（model, tokens, latency, success）
- [ ] AC-9: 所有外部依赖（litellm）在单元测试中被 mock，测试不需要真实 API Key

## Data Flow
Input: 用户/系统发起的分析请求（prompt 文本或模板名 + 变量）
Processing:
  1. PromptManager 加载并渲染 prompt 模板
  2. TokenBudgetTracker 检查当日预算是否充足
  3. LiteLLMRouter 调用主模型（litellm.acompletion）
  4. 若主模型失败，依次尝试 fallback_chain 中的模型
  5. 若提供了 response_schema，解析 JSON 并校验
  6. 解析失败则附加格式提示 retry 一次
  7. 记录调用日志和 token 用量
Output: LLMResponse 对象（content, parsed, model, tokens, latency, success, error）

## API Contract
- 内部 Python API（非 HTTP 接口）：
  - `LiteLLMRouter.complete(prompt, model, response_schema, temperature, max_tokens) -> LLMResponse`
  - `PromptManager.load_template(name) -> str`
  - `PromptManager.render(template_name, **kwargs) -> str`
  - `TokenBudgetTracker.check_budget(tokens) -> bool`
  - `TokenBudgetTracker.record_usage(model, input_tokens, output_tokens)`

## Dependencies
- Requires:
  - src/config（ConfigManager, LLMConfig）— Layer 1 配置管理
  - litellm（外部库）— LLM 调用统一接口
  - jinja2（外部库）— Prompt 模板渲染
- Provides:
  - LLM 统一调用接口，供上层分析模块使用
  - Prompt 模板管理，供所有需要 LLM 的模块使用
  - Token 预算控制，防止成本失控

## Non-functional Requirements
- Performance: 单次 LLM 调用超时默认 60 秒，可配置
- Security: API Key 仅通过 ConfigManager 的 SecretStr 访问，不会出现在日志中
- Reliability: Fallback chain 确保单一模型不可用时服务不中断
- Observability: 每次调用的 model、tokens、latency、success 记录到结构化日志

## File List
- `src/analysis/__init__.py` — 模块初始化
- `src/analysis/llm/__init__.py` — LLM 子模块初始化及公共导出
- `src/analysis/llm/base.py` — BaseLLMProvider ABC + LLMResponse
- `src/analysis/llm/router.py` — LiteLLMRouter 实现
- `src/analysis/llm/prompt_manager.py` — PromptManager
- `src/analysis/llm/budget.py` — TokenBudgetTracker
- `prompts/stock_analysis.j2` — 示例 prompt 模板
- `tests/unit/analysis/__init__.py` — 测试包初始化
- `tests/unit/analysis/test_llm.py` — 单元测试

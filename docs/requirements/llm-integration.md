# LLM Integration Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Multi-Model Support

Unified access via **LiteLLM** router:

| Provider | Model Examples | Use Case |
|----------|---------------|----------|
| OpenAI | gpt-4o, gpt-4o-mini | Comprehensive analysis |
| Anthropic | claude-sonnet-4-20250514 | Deep reasoning |
| DeepSeek | deepseek-chat, deepseek-reasoner | Cost-effective |
| Qwen (通义千问) | qwen-plus, qwen-max | Chinese language optimization |
| MiniMax | abab6.5s, abab7 | Chinese long-text processing |
| Zhipu AI (智谱) | glm-4-plus, glm-4-flash | Chinese comprehensive analysis |

## 2. Model Strategy

### Role Assignment
- **Primary model**: Core analysis tasks (individual stock analysis, macro interpretation, earnings report summarization)
- **Fast model**: Lightweight batch tasks (news classification, brief summaries, sentiment scoring)
- **Multi-model voting** (optional): Cross-validate critical decisions using multiple models

### Fallback Chain
```
Primary model fails
  → Try fallback model #1
    → Try fallback model #2
      → Return structured error with partial results if available
```

Configuration:
```yaml
# config.yaml example
llm:
  primary: "deepseek-chat"
  fast: "glm-4-flash"
  fallback_chain: ["qwen-plus", "gpt-4o-mini"]
```

## 3. LLM Call Conventions

### Prompt Management
- All prompts stored in `prompts/` directory as template files
- Template format: Jinja2 (`.j2`) or plain text with `{variable}` placeholders
- Organized by module: `prompts/stock_analysis.j2`, `prompts/macro_review.j2`, etc.
- Version controlled: prompt changes tracked in git like code

### Structured Output
- Every LLM call must define an expected output schema (Pydantic model)
- LLM output is parsed and validated against the schema
- Validation failure triggers:
  1. One retry with a more explicit prompt ("respond ONLY in the following JSON format...")
  2. If retry fails: return degraded result with missing fields marked as `null`
  3. Log the raw LLM output for debugging

### Call Logging
Every LLM call records:
```json
{
  "model": "deepseek-chat",
  "prompt_template": "stock_analysis.j2",
  "input_tokens": 2500,
  "output_tokens": 800,
  "latency_ms": 3200,
  "success": true,
  "retry_count": 0,
  "timestamp": "2026-03-29T18:05:00Z"
}
```

### Cost Control
- Configurable daily/monthly token budget per model
- Warning at 80% of budget, hard stop at 100%
- Config: `STOCK_ARM_LLM_DAILY_TOKEN_LIMIT`, `STOCK_ARM_LLM_MONTHLY_TOKEN_LIMIT`
- Budget tracking stored in database

## 4. Abstraction Layer

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse: ...

@dataclass
class LLMResponse:
    content: str                    # Raw text response
    parsed: BaseModel | None        # Parsed structured output (if schema provided)
    model: str                      # Model actually used (may differ from requested if fallback)
    input_tokens: int
    output_tokens: int
    latency_ms: int
    success: bool
    error: str | None
```

The concrete implementation wraps LiteLLM Router, handling:
- Multi-key load balancing (multiple API keys for same provider)
- Automatic fallback on failure
- Rate limit awareness (respect provider-specific limits)
- Timeout handling (configurable per model, default 60s)

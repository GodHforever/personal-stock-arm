# Configuration & Security Standards

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Configuration Management

### Zero Hardcoding Principle
All external addresses, API keys, thresholds, intervals, and timeouts must go through the config system. No magic numbers in code.

### Priority Chain
```
Environment variable (highest)
  → .env file
    → config.yaml defaults
      → Code-level defaults (lowest, for non-critical values only)
```

### Environment Variable Naming
```
STOCK_ARM_<CATEGORY>_<NAME>

Categories:
  LLM_    — LLM-related (API keys, model names, limits)
  DATA_   — Data source config (tokens, endpoints)
  PUSH_   — Notification/push config
  DB_     — Database config
  NET_    — Network config (proxy, timeouts)
  UI_     — Frontend/display config

Examples:
  STOCK_ARM_LLM_API_KEY=sk-xxx
  STOCK_ARM_LLM_PRIMARY_MODEL=deepseek-chat
  STOCK_ARM_DATA_TUSHARE_TOKEN=xxx
  STOCK_ARM_PUSH_WECHAT_WEBHOOK_URL=https://...
  STOCK_ARM_NET_PROXY=socks5://127.0.0.1:1080
  STOCK_ARM_NET_CONNECT_TIMEOUT=5
```

### .env.example Template
Must include every configurable setting with:
- Comment explaining purpose
- Default value (if any)
- Whether required or optional
- Format/example

```env
# ===== LLM Configuration =====
# Required: at least one LLM API key
STOCK_ARM_LLM_API_KEY=           # Primary LLM API key (required)
STOCK_ARM_LLM_PRIMARY_MODEL=deepseek-chat  # Primary model name
STOCK_ARM_LLM_FAST_MODEL=glm-4-flash      # Fast model for batch tasks
STOCK_ARM_LLM_DAILY_TOKEN_LIMIT=500000     # Daily token budget (0=unlimited)

# ===== Data Sources =====
STOCK_ARM_DATA_TUSHARE_TOKEN=    # Optional: Tushare Pro token
# ...
```

### config.yaml Format
```yaml
llm:
  primary_model: "deepseek-chat"
  fast_model: "glm-4-flash"
  fallback_chain: ["qwen-plus", "gpt-4o-mini"]
  daily_token_limit: 500000

data:
  connect_timeout: 5
  read_timeout: 30
  max_retries: 3

push:
  schedule_time: "18:00"
  silent_start: "22:00"
  silent_end: "08:00"

analysis:
  max_workers: 3
  delay_between_stocks: 10
```

---

## 2. Security Standards

### Secrets Management
- API keys **ONLY** via environment variables or `.env` file
- `.env` is in `.gitignore` — never committed
- API keys must **never** appear in:
  - Source code
  - Log output (mask with `***` if logging request metadata)
  - Frontend pages or JavaScript bundles
  - Error messages sent to users
  - Git history

### Database Security
- Database file stored in `data/` directory (gitignored)
- No raw SQL — use SQLAlchemy ORM to prevent injection
- If raw SQL is absolutely necessary: parameterized queries only

### Frontend Security
- Frontend accesses all external APIs through backend proxy
- No API keys stored in frontend code or localStorage
- Backend validates all input from frontend (trust boundary)

### Network Security
- Default bind: `127.0.0.1` (local only) in local mode
- Docker mode: `0.0.0.0` (container-internal, exposed via port mapping)
- HTTPS: not enforced for local tool, but proxy-friendly (behind nginx/caddy if needed)
- SSL verification enabled by default for all outbound HTTP requests

### Sensitive Data in Logs
```python
# BAD
logger.info(f"Calling API with key={api_key}")

# GOOD
logger.info(f"Calling API with key=***{api_key[-4:]}")

# BEST
logger.info("Calling LLM API", extra={"model": model_name})
# (don't log the key at all)
```

---

## 3. Error Handling Standards

### All External Calls Must Have

```python
async def fetch_data(url: str) -> Data:
    try:
        response = await client.get(url, timeout=config.connect_timeout)
        response.raise_for_status()
        return parse(response.json())
    except httpx.TimeoutException:
        raise DataSourceError(
            step="fetch stock quote",
            source="AkShare",
            url=url,
            error_type="ConnectionTimeout",
            error_msg=f"Timed out after {config.connect_timeout}s",
            suggestion="Check network or configure proxy"
        )
    except httpx.HTTPStatusError as e:
        raise DataSourceError(
            step="fetch stock quote",
            source="AkShare",
            url=url,
            error_type="HTTPError",
            error_msg=f"HTTP {e.response.status_code}",
            suggestion="Check if API endpoint has changed"
        )
```

### Structured Error Format
```python
@dataclass
class DataSourceError(Exception):
    step: str           # What operation was being performed
    source: str         # Which data source
    url: str            # Which URL/endpoint
    error_type: str     # Timeout, HTTPError, ParseError, etc.
    error_msg: str      # Human-readable description
    suggestion: str     # What the user can do
```

### Logging Levels
| Level | When to Use | Example |
|-------|------------|---------|
| DEBUG | Development details | Raw API response body |
| INFO | Normal operations | "Fetched 50 stocks from AkShare in 2.3s" |
| WARNING | Degradation/retry | "AkShare timeout, falling back to pytdx" |
| ERROR | Feature failure | "All data sources failed for stock 600519" |

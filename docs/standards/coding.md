# Coding Standards

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## Python

### Formatting & Linting
- **Formatter**: Black (line length 100)
- **Import sorting**: isort (Black-compatible profile)
- **Linting**: ruff (replaces flake8, fast)
- **Type checking**: mypy (strict mode on public APIs)

### Type Hints
- **Required** on all public functions (parameters + return type)
- Private/internal functions: recommended but not enforced
- Use `from __future__ import annotations` for forward references

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Files | `snake_case.py` | `akshare_fetcher.py` |
| Classes | `PascalCase` | `DataFetcherManager` |
| Functions | `snake_case` | `get_realtime_quote` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Private | `_leading_underscore` | `_parse_response` |
| Async functions | `snake_case` (same as sync) | `async def fetch_data` |

### Module Structure
```python
"""Module docstring: one-line purpose."""

from __future__ import annotations

# stdlib imports
# third-party imports
# local imports

# Constants

# Classes / Functions

# Private helpers
```

### Data Structures
- **Module boundaries**: Pydantic `BaseModel` for typed data exchange
- **Internal**: dataclasses or plain objects are acceptable
- **No raw dicts** crossing module boundaries

### Async Conventions
- Use `async/await` for I/O-bound operations (HTTP, database, file)
- CPU-bound work: run in thread pool via `asyncio.to_thread()`
- Database sessions: async SQLAlchemy with `async_sessionmaker`

---

## TypeScript / React

### Formatting & Linting
- **Formatter**: Prettier
- **Linting**: ESLint (recommended config)
- **Type checking**: TypeScript strict mode

### Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Component files | `PascalCase.tsx` | `StockChart.tsx` |
| Utility files | `camelCase.ts` | `apiClient.ts` |
| Hooks | `use` prefix, `camelCase` | `useStockData.ts` |
| Components | `PascalCase` | `<WatchlistPanel />` |
| Functions | `camelCase` | `formatPrice()` |
| Constants | `UPPER_SNAKE_CASE` | `API_BASE_URL` |
| Types/Interfaces | `PascalCase` | `StockQuote`, `AnalysisResult` |

### Component Structure
```tsx
// Imports
// Types (if component-specific)
// Component
// Styled components / helpers (if any)
```

### State Management
- **Zustand** for global state (lightweight, minimal boilerplate)
- Component-local state for UI-only concerns
- No prop drilling beyond 2 levels — use Zustand store instead

---

## Cross-Language Rules

1. **No commented-out code** in commits — use git history instead
2. **No TODO without ticket** — `TODO(#123): description` or remove it
3. **Chinese-first content** — 代码注释、文档、日志消息、错误提示、UI文本、Prompt模板、变量命名以外的所有人类可读文本均使用中文
4. **No abbreviations** in public APIs — `get_stock_analysis` not `get_stk_anal`

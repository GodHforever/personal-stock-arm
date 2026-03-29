# Technology Stack Rationale

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## Decision Record

Each technology choice is documented with alternatives considered and reasoning.

### Backend: Python 3.11+ / FastAPI

**Chosen over**: Node.js, Go, Java

**Reasoning**:
- Python has the most mature financial data ecosystem (akshare, tushare, efinance, baostock, pytdx)
- LLM SDKs are Python-first (LiteLLM, OpenAI, Anthropic, langchain)
- Data analysis libraries (pandas, numpy) are Python-native
- FastAPI provides async support, auto-generated API docs, Pydantic integration
- Reference project (`daily_stock_analysis`) validated this stack at ~51K lines

**Version**: 3.11+ for performance improvements and `tomllib` stdlib support

### Frontend: React 18 + TypeScript + Vite

**Chosen over**: Vue 3, Svelte, Streamlit

**Reasoning**:
- ECharts has best React bindings for financial charts (echarts-for-react)
- Rich component ecosystem (UI libraries, chart wrappers)
- TypeScript for type safety at API boundary (matches Pydantic models)
- Vite for fast dev server and optimized production builds
- Reference project validated React frontend

### Database: SQLite (WAL mode)

**Chosen over**: PostgreSQL, MySQL, MongoDB

**Reasoning**:
- Zero configuration — no separate server process
- Single file — trivial backup (`cp data/stock-arm.db backup/`)
- Cross-platform — works on Windows, macOS, in Docker
- WAL mode — supports concurrent reads during writes
- Sufficient for personal tool scale (thousands of rows, not millions)
- Alembic migrations work with SQLite

**Limitation accepted**: No full-text search (use Python-side filtering instead)

### Cache: Python `cachetools`

**Chosen over**: Redis, memcached

**Reasoning**:
- No additional infrastructure — runs in-process
- Sufficient for personal tool (hot data = today's quotes, ~100 items)
- TTL-based expiration prevents stale data
- Zero deployment complexity

### LLM Router: LiteLLM

**Chosen over**: Direct SDK calls, LangChain

**Reasoning**:
- Unified interface for 100+ models from all major providers
- Built-in fallback chain and load balancing
- Multi-key support (round-robin across API keys)
- Token counting and cost tracking
- Lighter than LangChain (no unnecessary abstractions)

### Charts: ECharts

**Chosen over**: Recharts, Chart.js, D3

**Reasoning**:
- Native financial chart types (candlestick, K-line)
- Best Chinese language support (labels, tooltips)
- Rich interactive features (zoom, crosshair, data views)
- Large ecosystem with financial chart examples

### State Management: Zustand

**Chosen over**: Redux, MobX, Jotai

**Reasoning**:
- Minimal boilerplate (no action types, reducers, dispatchers)
- TypeScript-first with good inference
- Small bundle size (1KB)
- Appropriate for personal tool complexity level

### Packaging: PyInstaller

**Chosen over**: Nuitka, cx_Freeze, Briefcase

**Reasoning**:
- Most widely used, best community support
- Single-file output (`--onefile`)
- Cross-platform (Windows, macOS)
- Handles complex dependency trees (numpy, pandas, etc.)

**Fallback**: Nuitka if PyInstaller encounters issues with specific dependencies

### Container: Docker + docker-compose

**Role**: Optional — for development environment consistency and containerized deployment

**Reasoning**:
- Eliminates "works on my machine" problems
- Single `docker-compose up` for users who prefer containers
- Multi-stage build keeps image small
- Development override for hot reload

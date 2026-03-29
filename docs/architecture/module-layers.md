# Module Dependency Layers

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)
> Execution order governed by: `docs/paradigm/sprint-workflow.md`

---

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│ Layer 6: Enhancement (optional)                         │
│   Trade Interface Framework │ Backtesting │ Multi-Vote  │
├─────────────────────────────────────────────────────────┤
│ Layer 5: Presentation                                   │
│   FastAPI Backend │ React Frontend (PWA) │ Bot Push     │
├─────────────────────────────────────────────────────────┤
│ Layer 4: Business Logic                                 │
│   Watchlist │ Macro │ Earnings │ Intl Finance │ Reports │
├─────────────────────────────────────────────────────────┤
│ Layer 3: Analysis                                       │
│   LLM Integration │ Technical Analysis │ Skills Adapter │
├─────────────────────────────────────────────────────────┤
│ Layer 2: Data                                           │
│   A-share Fetchers │ Intl Market Fetchers │ News/Sentiment│
├─────────────────────────────────────────────────────────┤
│ Layer 1: Infrastructure                                 │
│   Config │ Database/ORM │ NetworkClient │ Logging       │
└─────────────────────────────────────────────────────────┘
```

---

## Layer Details

### Layer 1: Infrastructure

| Module | Responsibility | Key Classes/Components |
|--------|---------------|----------------------|
| Config | Load and manage all configuration | `ConfigManager`, `.env` parsing, `config.yaml` loading |
| Database | SQLAlchemy ORM, Alembic migrations, session management | `Database`, model base classes, `async_sessionmaker` |
| NetworkClient | Unified HTTP client with timeout, retry, proxy, error reporting | `NetworkClient`, `DataSourceError` |
| Logging | Structured logging with level control | `setup_logging()`, formatters |

**Dependencies**: None (foundation layer)
**Must be complete before**: Any Layer 2 module

### Layer 2: Data

| Module | Responsibility | Key Classes/Components |
|--------|---------------|----------------------|
| A-share Fetchers | Multi-source data retrieval with failover | `BaseDataFetcher`, `DataFetcherManager`, concrete fetchers |
| Intl Market Fetchers | Longbridge + yfinance integration | `LongbridgeFetcher`, `YfinanceFetcher` |
| News/Sentiment | News search, platform scraping, RSS | `NewsSearchService`, scrapers, `AntiScrapeManager` |

**Dependencies**: Layer 1 (Config for API keys, NetworkClient for HTTP, Database for caching)
**Must be complete before**: Any Layer 3 module

### Layer 3: Analysis

| Module | Responsibility | Key Classes/Components |
|--------|---------------|----------------------|
| LLM Integration | Multi-model routing, prompt management, structured output | `BaseLLMProvider`, `LiteLLMRouter`, prompt templates |
| Technical Analysis | MA, MACD, RSI, volume analysis, signal scoring | `TechnicalAnalyzer`, indicator calculators |
| Skills Adapter | External skill integration and management | `BaseSkillAdapter`, `SkillRegistry`, YAML strategy loader |

**Dependencies**: Layer 1 (Config, Logging) + Layer 2 (data for analysis input)
**Must be complete before**: Any Layer 4 module

### Layer 4: Business Logic

| Module | Responsibility | Key Classes/Components |
|--------|---------------|----------------------|
| Watchlist | Stock group management, daily analysis pipeline | `WatchlistManager`, `StockAnalysisPipeline` |
| Macro Data | Macro indicator tracking, chart generation, LLM commentary | `MacroTracker`, indicator processors |
| Earnings | Earnings report scanning, PDF download, LLM summarization | `EarningsProcessor`, summary generators |
| Intl Finance | International briefing generation | `InternationalBriefingGenerator` |
| Research Reports | Report download, LLM summary, rating tracking | `ReportManager`, broker scrapers |

**Dependencies**: Layers 1-3

### Layer 5: Presentation

| Module | Responsibility | Key Classes/Components |
|--------|---------------|----------------------|
| FastAPI Backend | REST API endpoints, SSE streaming, static file serving | Route handlers, middleware, Pydantic schemas |
| React Frontend | Web UI with PWA support | Pages, components, stores, API client |
| Bot Push | Notification channel integration | `BaseNotifier`, channel implementations |

**Dependencies**: Layers 1-4

### Layer 6: Enhancement (Optional)

| Module | Responsibility | Key Classes/Components |
|--------|---------------|----------------------|
| Trade Interface | Abstract trading framework (no concrete implementation) | `BaseTradeProvider`, order models |
| Backtesting | Historical signal accuracy validation | `BacktestEngine`, result storage |
| Multi-Model Voting | Cross-validate decisions across LLMs | `VotingOrchestrator`, consensus logic |

**Dependencies**: Layers 1-5

---

## Dependency Rules

1. **Downward only**: A module may only depend on modules in lower layers
2. **No circular dependencies**: If A depends on B, B must not depend on A
3. **Interface at boundaries**: Cross-layer communication uses abstract interfaces (Base classes) and Pydantic models
4. **Layer completion**: A layer's development cannot start until all its dependency layers have merged to main
5. **Within-layer parallelism**: Modules in the same layer may be developed in parallel (separate sprints)

---

## Source Code Layout

```
src/
├── config/           # Layer 1: Configuration
├── db/               # Layer 1: Database & ORM
├── network/          # Layer 1: Network client
├── logging/          # Layer 1: Logging setup
├── data/             # Layer 2: Data fetchers
│   ├── a_share/      # A-share data sources
│   ├── international/ # Longbridge, yfinance
│   └── news/         # News & sentiment
├── analysis/         # Layer 3: Analysis engines
│   ├── llm/          # LLM integration
│   ├── technical/    # Technical analysis
│   └── skills/       # Skill adapters
├── business/         # Layer 4: Business logic
│   ├── watchlist/
│   ├── macro/
│   ├── earnings/
│   ├── international/
│   └── reports/
├── api/              # Layer 5: FastAPI routes
│   └── v1/
├── notification/     # Layer 5: Push channels
└── trade/            # Layer 6: Trade interface (framework only)
```

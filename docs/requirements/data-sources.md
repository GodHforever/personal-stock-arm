# Data Sources Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. A-Share Data Sources (Multi-source Failover)

### Priority Chain

| Priority | Source | Capabilities | Token Required |
|----------|--------|-------------|----------------|
| 0 | efinance | Real-time quotes, K-line, sector rankings | No |
| 0 | Tushare Pro | Quotes, financials, macro, dividends | Yes (limited free tier) |
| 1 | AkShare | Quotes, macro indicators, sectors, capital flow | No |
| 2 | pytdx (TDX) | Real-time quotes, K-line | No |
| 3 | Baostock | Historical K-line, fundamentals | No |

### Failover Strategy

```
Request → Try Priority 0 sources (efinance / Tushare)
           │
           ├── Success → Return data
           └── Fail → Log error, try Priority 1 (AkShare)
                        │
                        ├── Success → Return data
                        └── Fail → Log error, try Priority 2 (pytdx)
                                     │
                                     └── ... continue until exhausted
                                          │
                                          └── All fail → Return DataUnavailable
                                               with structured error report
```

### Error Reporting per Source

Every source failure must produce a structured error:
```json
{
  "source": "AkShare",
  "api": "stock_zh_a_spot_em",
  "error_type": "ConnectionTimeout",
  "error_msg": "Connection timed out after 5s",
  "timestamp": "2026-03-29T10:30:00Z",
  "suggestion": "Check network or configure proxy"
}
```

### Data Source Abstraction

All data sources implement `BaseDataFetcher`:

```python
class BaseDataFetcher(ABC):
    @abstractmethod
    async def get_realtime_quote(self, code: str) -> StockQuote: ...
    @abstractmethod
    async def get_kline(self, code: str, period: str, count: int) -> list[KlineBar]: ...
    @abstractmethod
    async def get_fundamentals(self, code: str) -> Fundamentals: ...

    # Metadata
    @property
    @abstractmethod
    def source_name(self) -> str: ...
    @property
    @abstractmethod
    def priority(self) -> int: ...
    @property
    @abstractmethod
    def requires_token(self) -> bool: ...
```

`DataFetcherManager` orchestrates failover across sources.

---

## 2. International Market Data Sources

| Source | Markets | Capabilities | Notes |
|--------|---------|-------------|-------|
| Longbridge OpenAPI | US, HK, Singapore | Quotes, K-line, financials, news, positions | OAuth authentication, refer to `/rvhome/hao.gao/personal/developers/skills/longbridge` |
| yfinance | US (fallback) | Historical K-line, fundamentals | Free, no token |

### Longbridge Integration Notes
- Authentication: OAuth 2.0 via `longbridge` Python SDK
- Symbol format: `CODE.MARKET` (e.g., `AAPL.US`, `700.HK`)
- Rate limit: max 10 API calls/second
- May also use CLI (`longbridge quote SYMBOL`) or MCP integration

### International Data Scope (limited compared to A-share)
- Daily index tracking: Dow Jones, S&P 500, NASDAQ, Hang Seng, Hang Seng Tech
- Key events and news (not full technical analysis)
- Fundamental data for specific tracked stocks only

---

## 3. News & Sentiment Data Sources

| Source | Purpose | Notes |
|--------|---------|-------|
| Tavily Search API | Chinese/English news search | Free 1000 queries/month |
| SerpAPI | Baidu/Google search | Paid |
| Xueqiu (雪球) scraper | Individual stock discussions, sector news | Anti-scraping required |
| East Money (东方财富) scraper | Research reports, announcements, capital flow | Anti-scraping required |
| RSS feeds | Financial media (Wall Street CN, Cailian Press) | Low-cost continuous tracking |

### Anti-Scraping Design

```
Request interval: base 2-5s + random 0-3s jitter
User-Agent pool: 50+ real UAs, random rotation
Cookie management: cookie pool for login-required content
Adaptive rate: exponential backoff on block (2s→4s→8s→...)
                stop source after threshold exceeded
Cache: same content not re-fetched within 24 hours
Degradation: on scraping failure, fallback to search engine API
```

### Key Rule
**Scraping failure must never block the main analysis pipeline.** Failed scraping degrades to "data unavailable" annotation — the analysis proceeds with whatever data is available.

---

## 4. Macro Economic Data

### Core Indicators

| Category | Indicator | Update Frequency | Data Source |
|----------|-----------|-----------------|------------|
| Prices | CPI, PPI | Monthly | AkShare / Tushare |
| Money | M1, M2, Total Social Financing | Monthly | AkShare |
| Interest Rates | LPR, Shibor, Treasury Yield (10Y/1Y) | Daily/Monthly | AkShare |
| Market | Equity Risk Premium (=1/A-share PE - 10Y Treasury) | Daily | Calculated |
| Market | Margin Trading Balance | Daily | AkShare |
| Market | Northbound Capital Net Inflow | Daily | AkShare / efinance |
| Market | Stock Connect Quota Usage | Daily | AkShare |
| International | Fed Rate Decision, Non-farm Payrolls, US CPI | Event-driven | Financial Calendar API |
| Commodities | Crude Oil (WTI/Brent), Gold, Copper | Daily | AkShare / yfinance |

### Processing Flow

1. Daily scheduled pull → Compare with previous value / expected value (store only latest value + previous value, not full history)
2. LLM analyzes current data's meaning and market impact
3. If no update available today: annotate "No update" with last available date and value
4. Push summary to notification channels

### Data Freshness Rules
- Daily indicators: pull after market close (18:00 default)
- Monthly indicators: pull on release day (usually 10th-15th of month)
- Event-driven: poll financial calendar daily, trigger on event day
- All indicators: display "last updated" timestamp alongside value

### Scheduling
- Registered as `daily_macro` in TaskScheduler (daily 18:30)
- Cloud mode: auto-pull every trading day
- Local mode: on startup, pull if today's macro data not yet fetched; user can backfill via Web UI

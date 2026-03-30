# Core Features Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Watchlist Management & Analysis (自选股管理与分析)

### Watchlist Groups
- Support multiple watchlist groups (e.g., "Long-term Holdings", "Short-term Watch", "Sector Tracking")
- Each group can have its own analysis strategy and push frequency（默认推送频率为0）
- Import methods: manual text input, CSV file, image (OCR stock code recognition)

### Daily Analysis per Stock

| Dimension | Content | Data Source |
|-----------|---------|------------|
| Technical | MA trends, MACD, RSI, volume-price relationship, support/resistance levels | DataFetcherManager (real-time fetch, not stored) |
| Fundamental | PE/PB/ROE, latest financial data summary | DataFetcherManager (real-time fetch) |
| News | Related news, announcements, research report summaries | News/Sentiment sources (summarize and discard originals) |
| Capital Flow | Main force capital flow, chip distribution (optional) | DataFetcherManager (real-time fetch) |
| LLM Synthesis | Bull/bear verdict, key risk alerts, operation advice | LLM Provider |
| Delta | Signal changes compared to previous trading day | Database (historical analysis results) |

### Output Format
Each stock produces a structured analysis result:
```
StockAnalysisResult:
  - stock_code: str
  - stock_name: str
  - analysis_date: date
  - technical_summary: TechnicalSummary
  - fundamental_summary: FundamentalSummary
  - news_summary: NewsSummary
  - capital_flow: CapitalFlowSummary | None
  - llm_verdict: LLMVerdict
  - signal_changes: list[SignalChange]
```

### Scheduling
- Registered as `daily_analysis` in TaskScheduler (daily 18:00)
- Cloud mode: auto-trigger every trading day
- Local mode: on startup, auto-run if today's analysis not yet executed; user can manually backfill date ranges via Web UI (backfill results not pushed)

---

### Trigger Periods
- **April**: Annual report + Q1 report (高频期)
- **August**: Semi-annual report
- **October**: Q3 report

### Processing Pipeline

```
1. Daily scan for newly published earnings reports
   Source: AkShare / East Money
   Filter: all A-share companies, or only watchlist stocks (configurable)

2. LLM generates earnings summary:
   - Core business composition and changes
   - Key financial metrics:
     * Revenue, Net Profit, Non-GAAP Net Profit
     * Gross Margin, Net Margin
     * Operating Cash Flow
   - YoY / QoQ changes and trends
   - Highlights and risk alerts

3. Store summary as Markdown:
   data/earnings/<date>/<stock_code>_summary.md

4. User marks "interested" reports:
   - Trigger deep analysis (segment breakdown, peer comparison, valuation)
   - On-demand fetch original document and forward via email/WeChat/Feishu
   - Original documents are NOT stored locally
```

### Configuration
- `STOCK_ARM_EARNINGS_SCAN_SCOPE=watchlist|all` (default: watchlist)
- `STOCK_ARM_EARNINGS_AUTO_DEEP_ANALYSIS=false` (default: false, manual trigger)

### Scheduling
- Registered as `earnings_scan` in TaskScheduler (daily 20:00 during earnings season)
- Cloud mode: auto-trigger during earnings months (April, August, October)
- Local mode: on startup, check if today is earnings season and if scan already ran today

---

## 3. International Finance & Geopolitical Tracking (国际金融与地缘跟踪)

### Tracking Scope

**Daily Index Tracking**:
- US: Dow Jones, S&P 500, NASDAQ
- HK: Hang Seng Index, Hang Seng Tech Index

**Event Tracking**:
- Fed / ECB policy decisions and speeches
- Geopolitical developments (US-China relations, regional conflicts)
- Commodity anomalies (crude oil, gold sharp moves)
- Global major economic events calendar

### Daily Output: International Finance Briefing

```markdown
# International Finance Briefing - <date>

## Overnight Market Summary
- US markets: [index changes, key movers, narrative]
- HK markets: [index changes, key movers]

## Key Events & A-Share Impact
- Event 1: [description] → Potential A-share impact: [analysis]
- Event 2: ...

## Upcoming Events (next 7 days)
- <date>: <event description>
- ...
```

Storage: `data/briefings/<date>_international.md`

### Scheduling
- Registered as `daily_briefing` in TaskScheduler (daily 19:00)
- Cloud mode: auto-generate every trading day
- Local mode: on startup, generate if today's briefing not yet created

---

## 4. Research Report Management (研报管理)

### Data Sources
- East Money Research Center (东方财富研报中心)
- Broker app APIs (if available)
- Longbridge research (HK/US stocks)

### Features
- Filter by: industry, individual stock, rating
- LLM summary per report: core thesis, target price, logic chain, risk alerts (only summary stored, not original document)
- Tracking: compare rating changes across brokers for same stock over time
- Push: auto-push summaries matching watchlist stocks
- On-demand: user can request original document forwarded via email/WeChat/Feishu (fetched on demand, not stored)

### Output per Report
```
ResearchReportSummary:
  - title: str
  - broker: str
  - analyst: str
  - publish_date: date
  - target_stock: str
  - rating: str  # Buy/Hold/Sell
  - target_price: float | None
  - core_thesis: str  # 1-2 sentence summary
  - key_logic: list[str]  # Reasoning chain
  - risk_factors: list[str]
  - previous_rating: str | None  # For change tracking
```

---

## 5. Platform Information Collection (平台信息采集)

### Target Platforms
- **Xueqiu (雪球)**: Individual stock discussions, portfolio tracking, KOL opinions
- **East Money Guba (东方财富股吧)**: Market sentiment sensing
- **Tonghuashun (同花顺)**: If usable API available

### Anti-Scraping Strategy (Critical)

```
Request Interval: base 2-5s + random 0-3s jitter
User-Agent Pool: 50+ real UAs, random rotation
Login State: Cookie pool (for login-required content)
Adaptive Rate: exponential backoff on block (2s→4s→8s→16s)
               pause source after threshold exceeded
Cache: same content not re-fetched within 24 hours
Degradation: on failure, fallback to search engine API
```

### Core Rule
**Scraping failure MUST NOT block the main pipeline.** On failure, annotate "data unavailable" and continue with other sources.

### Sentiment Output
```
PlatformSentiment:
  - platform: str
  - stock_code: str
  - sample_size: int
  - sentiment_score: float  # 0-100
  - key_topics: list[str]
  - notable_opinions: list[str]  # KOL or high-engagement posts
  - collected_at: datetime
```

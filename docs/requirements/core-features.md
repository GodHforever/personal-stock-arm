# Core Features Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Watchlist Management & Analysis (自选股管理与分析)

### Watchlist Groups
- Support multiple watchlist groups (e.g., "Long-term Holdings", "Short-term Watch", "Sector Tracking")
- Each group can have its own analysis strategy and push frequency
- Import methods: manual text input, CSV file, image (OCR stock code recognition)

### Daily Analysis per Stock

| Dimension | Content | Data Source |
|-----------|---------|------------|
| Technical | MA trends, MACD, RSI, volume-price relationship, support/resistance levels | DataFetcherManager |
| Fundamental | PE/PB/ROE, latest financial data summary | DataFetcherManager |
| News | Related news, announcements, research report summaries | News/Sentiment sources |
| Capital Flow | Main force capital flow, chip distribution (optional) | DataFetcherManager |
| LLM Synthesis | Bull/bear verdict, key risk alerts, operation advice | LLM Provider |
| Delta | Signal changes compared to previous trading day | Database (historical) |

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

---

## 2. Earnings Season Tracking (财报季跟踪)

### Trigger Periods
- **April**: Annual report + Q1 report (高频期)
- **August**: Semi-annual report
- **October**: Q3 report

### Processing Pipeline

```
1. Daily scan for newly published earnings reports
   Source: AkShare / East Money
   Filter: all A-share companies, or only watchlist stocks (configurable)

2. Download PDF original (optional, configurable)
   Storage: data/earnings/<date>/<stock_code>.pdf

3. LLM generates earnings summary:
   - Core business composition and changes
   - Key financial metrics:
     * Revenue, Net Profit, Non-GAAP Net Profit
     * Gross Margin, Net Margin
     * Operating Cash Flow
   - YoY / QoQ changes and trends
   - Highlights and risk alerts

4. Store summary as Markdown:
   data/earnings/<date>/<stock_code>_summary.md

5. User marks "interested" reports → trigger deep analysis:
   - Business segment / regional breakdown
   - Peer comparison (same industry)
   - Historical trend analysis
   - Valuation reasonableness assessment
```

### Configuration
- `STOCK_ARM_EARNINGS_SCAN_SCOPE=watchlist|all` (default: watchlist)
- `STOCK_ARM_EARNINGS_DOWNLOAD_PDF=true|false` (default: false)
- `STOCK_ARM_EARNINGS_AUTO_DEEP_ANALYSIS=false` (default: false, manual trigger)

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

---

## 4. Research Report Management (研报管理)

### Data Sources
- East Money Research Center (东方财富研报中心)
- Broker app APIs (if available)
- Longbridge research (HK/US stocks)

### Features
- Filter and download by: industry, individual stock, rating
- LLM summary per report: core thesis, target price, logic chain, risk alerts
- Tracking: compare rating changes across brokers for same stock over time
- Push: auto-push reports matching watchlist stocks

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

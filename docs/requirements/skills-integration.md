# External Skills Integration Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Design Philosophy

The financial analysis ecosystem (Claude Skills, GitHub projects, quant communities) offers mature tools. This project integrates them under strict lightweight constraints.

### Principles

1. **Discover before building**: Before implementing any module, search for reusable skills/tools
2. **Lightweight dependency**: Never introduce heavy frameworks or excessive pip packages
3. **Standardized adapter**: All external skills are accessed through a unified `SkillAdapter` interface
4. **Audit trail**: Every skill evaluation is recorded in `skills/registry.yaml`

---

## 2. Integration Tiers

| Tier | Criteria | Action |
|------|----------|--------|
| **Direct Use** | Mature, ≤3 new pip packages, clean API, actively maintained | Install and integrate via adapter |
| **Reference** | Good design but heavy deps or incompatible interface | Extract core logic/prompts, re-implement lightweight |
| **Ignore** | Poor quality, abandoned, or excessive complexity | Document reason in registry, move on |

### Dependency Budget Rule

**Hard limit**: A single skill integration must not introduce more than 3 new pip packages.

If a skill requires more:
- Evaluate if core logic can be extracted without the full dependency tree
- If yes: reference-tier integration (extract and re-implement)
- If no: ignore and implement from scratch

---

## 3. Skill Adapter Interface

```python
class BaseSkillAdapter(ABC):
    """Unified interface for external skill integration.

    Adapter code must not exceed 200 lines.
    """

    @property
    @abstractmethod
    def skill_name(self) -> str: ...

    @property
    @abstractmethod
    def skill_source(self) -> str:
        """Where this skill came from (URL, package name, etc.)"""
        ...

    @abstractmethod
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """Run the skill with typed input, return typed output."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the skill's dependencies are available."""
        ...
```

---

## 4. Integration Directions

| Direction | Skill Types | Preferred Tier |
|-----------|------------|----------------|
| Technical Analysis | K-line pattern recognition, Chan Theory (缠论), Elliott Wave | Reference |
| Quant Strategies | Momentum, mean reversion, multi-factor models | Reference (adapt to YAML strategy format) |
| Data Fetching | Broker API skills, financial data scrapers | Direct Use |
| LLM Analysis | Financial prompt templates, research report reading | Reference (extract prompt design) |
| Visualization | Chart generation, dashboard templates | Direct Use / Reference |
| Risk Management | Risk models, position sizing calculators | Reference |

---

## 5. Evaluation Flow (agent must follow)

```
Before implementing a new feature:

1. SEARCH for related skills/tools:
   - GitHub (topic: finance, quant, stock-analysis)
   - Claude Skills directory
   - Quant communities (聚宽, 优矿, RiceQuant)
   - PyPI (relevant packages)

2. EVALUATE each candidate:
   - Functionality match (does it solve our need?)
   - Quality (tests? docs? stars/forks?)
   - Maintenance status (last commit? open issues?)
   - Dependency weight (how many new pip packages?)
   - License compatibility

3. DECIDE: Direct Use / Reference / Ignore
   - Direct Use requires: ≤3 new pip packages, clean API, active maintenance
   - Heavy deps or stale maintenance: Reference only (extract core logic)

4. RECORD in skills/registry.yaml:
   - Name, source, evaluation date
   - Decision and reasoning
   - If adopted: adapter location, version pinned

5. If adopting: write adapter layer + independent tests
   - Adapter code ≤ 200 lines
   - Must have health_check()
   - Must have at least 2 tests (normal case + failure case)
```

---

## 6. Skills Registry Format

`skills/registry.yaml`:

```yaml
skills:
  - name: "longbridge-mcp"
    source: "https://open.longbridge.com/mcp"
    category: "data-fetching"
    tier: "direct-use"
    evaluated: "2026-03-29"
    decision: "Direct integration via MCP protocol"
    new_deps: ["longbridge"]
    adapter: "src/skills/longbridge_adapter.py"
    status: "planned"

  - name: "ta-lib"
    source: "https://github.com/TA-Lib/ta-lib-python"
    category: "technical-analysis"
    tier: "reference"
    evaluated: "2026-03-29"
    decision: "Heavy C dependency, reference algorithm implementations only"
    new_deps: []
    adapter: null
    status: "reference-only"
    notes: "Core MACD/RSI/MA algorithms re-implemented in pure Python"
```

---

## 7. Skill Definition Format

Self-developed skills (strategies, analysis modules) use YAML:

```yaml
# skills/bull_trend.yaml
name: bull_trend
description: "Bullish trend following strategy: MA5 > MA10 > MA20 with low bias ratio"
version: "1.0"
category: "strategy"

trigger:
  conditions:
    - "MA alignment is bullish"
    - "Bias ratio < 5%"

input:
  schema: "StockKlineData"
  fields:
    - name: kline_data
      type: "list[KlineBar]"
      required: true

output:
  schema: "StrategySignal"
  fields:
    - name: signal
      type: "str"  # buy / hold / sell
    - name: confidence
      type: "float"  # 0-100
    - name: reasoning
      type: "str"

implementation: "src/skills/strategies/bull_trend.py"
```

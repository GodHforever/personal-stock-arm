# Testing Standards

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)
> Also governed by: `docs/paradigm/quality-gates.md` (QA evaluation criteria)

---

## 1. Test Structure

```
tests/
├── unit/                    # Unit tests (Builder writes, QA reviews)
│   ├── test_config.py
│   ├── data/
│   │   ├── test_akshare_fetcher.py
│   │   └── test_fetcher_manager.py
│   ├── analysis/
│   │   └── test_technical.py
│   └── ...
├── integration/             # Integration tests (QA writes)
│   ├── test_api_endpoints.py
│   ├── test_data_failover.py
│   └── test_database.py
├── scenario/                # Scenario tests (QA writes)
│   ├── test_happy_path.py
│   ├── test_edge_cases.py
│   └── test_error_handling.py
├── environment/             # Environment tests (QA writes)
│   ├── test_docker_build.py
│   └── test_env_detection.py
├── conftest.py              # Shared fixtures
└── fixtures/                # Test data files
    ├── sample_kline.json
    └── sample_earnings.json
```

**Mirror rule**: `tests/unit/` mirrors `src/` structure. If source is `src/data/akshare_fetcher.py`, test is `tests/unit/data/test_akshare_fetcher.py`.

## 2. Naming

- Test files: `test_<module>.py`
- Test functions: `test_<behavior>_<scenario>()`
- Examples:
  - `test_get_quote_returns_valid_data()`
  - `test_get_quote_raises_on_timeout()`
  - `test_fallback_activates_when_primary_fails()`

## 3. Coverage Requirements

### Builder (unit tests)
- Every public function: at least 1 positive test + 1 negative/error test
- Every acceptance criterion in the feature spec: at least 1 test

### QA (supplements)
- Integration: API endpoints, data source failover, database state
- Scenario: happy path, boundary cases (empty/large/special chars), error paths
- Environment: Docker build, environment detection

## 4. Mocking Rules

### Unit Tests
- **Mock external dependencies**: HTTP calls, database, LLM API, file system
- **Do NOT mock** the code under test or its internal helpers
- Use `unittest.mock.patch` or `pytest-mock`
- Mock at the boundary (e.g., mock the HTTP client, not the data fetcher method)

### Integration Tests
- **Real database**: SQLite in-memory (`:memory:`)
- **Mock external HTTP**: use `responses` or `aioresponses` library
- **Mock LLM**: pre-recorded responses in `tests/fixtures/`

### Forbidden Mocking Patterns
```python
# BAD: mocking the function under test
with patch("src.analyzer.analyze_stock") as mock:
    mock.return_value = expected  # This tests nothing

# BAD: asserting mock was called without checking behavior
mock_fetch.assert_called_once()  # Proves coupling, not correctness

# GOOD: mock dependency, verify output
with patch("src.data.fetcher.httpx.get") as mock_http:
    mock_http.return_value = Response(200, json=sample_data)
    result = await fetcher.get_quote("600519")
    assert result.price == 1850.50
```

## 5. Test Commands

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific module
pytest tests/unit/data/

# With coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Verbose (show test names)
pytest tests/ -v
```

## 6. Fixtures

### Shared fixtures in `conftest.py`:
```python
@pytest.fixture
def sample_kline_data():
    """Load sample K-line data from fixtures."""
    ...

@pytest.fixture
async def db_session():
    """Async SQLite in-memory session for integration tests."""
    ...

@pytest.fixture
def mock_llm_response():
    """Pre-recorded LLM response for analysis tests."""
    ...
```

### Test data files in `tests/fixtures/`:
- JSON format, representative real-world data
- Anonymized (no real API keys or user data)
- Versioned in git

## 7. CI Integration

Tests must pass before any merge to main:
```
Pre-merge checks:
  1. pytest tests/unit/ — must pass (Builder responsibility)
  2. pytest tests/integration/ — must pass (QA adds after evaluation)
  3. ruff check src/ — zero errors
  4. mypy src/ — zero errors on public APIs
```

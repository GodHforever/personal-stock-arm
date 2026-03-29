# Quality Gates

> **Authority level**: FIRST-CLASS. This document is part of the development paradigm. All agents must comply unconditionally.

---

## Scoring Rubric

Every sprint submission is scored across 6 dimensions. QA Agent must evaluate each independently.

### Dimensions

| Dimension | Weight | What is evaluated |
|-----------|--------|-------------------|
| **Functional Completeness** | 30% | Every acceptance criterion has a passing test |
| **Code Quality** | 20% | Lint zero errors, type check passes, no code smells, follows CLAUDE.md conventions |
| **API Contract** | 15% | Routes, request/response schemas match the spec exactly |
| **Error Handling** | 15% | External calls have timeout/retry/fallback, error messages are structured and actionable |
| **Database** | 10% | Schema changes have Alembic migration, integrity constraints correct, naming follows conventions |
| **Security** | 10% | No hardcoded secrets, no injection risks, input validation at boundaries |

### Scoring per Dimension

Each dimension is scored 0-100:

| Score | Meaning | Criteria |
|-------|---------|----------|
| 90-100 | Excellent | No issues found, exceeds expectations |
| 70-89 | Good | Minor issues that don't affect functionality |
| 50-69 | Acceptable | Issues exist but workarounds are possible |
| 30-49 | Poor | Significant issues that affect reliability |
| 0-29 | Critical | Missing implementation or blocking defects |

**Weighted total** = sum of (dimension_score * weight) across all 6 dimensions.

---

## Pass/Fail Thresholds

| Total Score | Verdict | Action |
|-------------|---------|--------|
| **≥ 80** | **PASS** | Merge to main. Builder updates CLAUDE.md. |
| **60-79** | **CONDITIONAL** | QA lists specific issues marked [MUST FIX]. Builder fixes only those issues and resubmits. No re-evaluation of passing dimensions. |
| **< 60** | **FAIL** | QA provides comprehensive feedback. Builder re-implements the feature addressing all issues. Full re-evaluation on resubmission. |

### Special Rules
- **Zero-tolerance items**: If ANY of the following is found, the sprint automatically fails regardless of total score:
  - API keys or secrets hardcoded in source code
  - SQL injection vulnerability
  - Tests that pass by coincidence (e.g., testing the mock, not the logic)
  - Breaking change to an existing API without documented migration path
  - Missing Alembic migration for schema changes

---

## Test Layers

QA Agent is responsible for 4 layers of testing. Builder provides Layer 1; QA supplements Layers 2-4.

### Layer 1: Unit Tests (Builder-written, QA-reviewed)

**QA reviews for**:
- Coverage: every acceptance criterion has at least one test
- Quality: tests assert behavior, not implementation details
- Edge cases: empty inputs, boundary values, error paths
- No over-mocking: tests that mock everything prove nothing

### Layer 2: Integration Tests (QA-written)

```
API End-to-End:
  - Send HTTP request → verify response status, body, headers
  - Verify database state after write operations
  - Verify cache behavior (hit/miss)

Data Source Failover:
  - Mock primary source failure → verify fallback activates
  - Mock all sources failure → verify graceful degradation
  - Verify error reporting format matches NetworkClient spec

Database State:
  - Insert → read → verify consistency
  - Concurrent write test (WAL mode)
  - Migration up/down roundtrip
```

### Layer 3: Scenario Tests (QA-written)

```
Happy Path:
  - Normal user workflow end-to-end
  - Verify output format and content

Boundary Scenarios:
  - Empty data (no stocks in watchlist, no news found)
  - Large data (100+ stocks, 1000+ news items)
  - Special characters in stock names/user input
  - Missing optional configuration

Error Scenarios:
  - Network disconnection mid-request
  - API rate limiting (429 response)
  - Malformed data from external source
  - LLM returns invalid JSON
  - LLM returns empty/truncated response
```

### Layer 4: Environment Tests (QA-written)

```
Docker:
  - Dockerfile builds successfully
  - Container starts and responds to health check
  - Data persists across container restart
  - .env injection works correctly

Environment Detection:
  - Docker mode activates in container (correct data dir, bind host)
  - Local mode activates outside container (correct browser launch behavior)
  - Network probe correctly identifies unreachable sources
```

---

## QA Checklist (quick reference)

Before writing the Evaluation Report, QA must:

1. **Run automated validation**: `python scripts/validate_paradigm.py --all` — must pass
2. Verify all items below:

```
Functional:
  [ ] All acceptance criteria have passing tests
  [ ] Feature works as described in user story
  [ ] No regression in existing functionality

Code:
  [ ] Lint: zero errors (warnings acceptable)
  [ ] Type check: passes
  [ ] Follows CLAUDE.md conventions (naming, structure, patterns)
  [ ] No unnecessary complexity or over-engineering

API:
  [ ] Routes match spec
  [ ] Request/response schemas match spec
  [ ] Error responses follow unified format
  [ ] Status codes are correct

Errors:
  [ ] All external calls have timeout
  [ ] Retry logic with exponential backoff where specified
  [ ] Fallback/degradation path exists
  [ ] Error messages include: location, operation, error detail, suggestion

Database:
  [ ] Alembic migration exists for schema changes
  [ ] Migration is reversible (has downgrade)
  [ ] Table/column naming follows conventions
  [ ] created_at, updated_at fields present

Security:
  [ ] No secrets in code, logs, or frontend
  [ ] No SQL injection risk (parameterized queries or ORM)
  [ ] Input validation at system boundaries
  [ ] .env.example updated if new config added

Zero-tolerance:
  [ ] No hardcoded secrets
  [ ] No SQL injection
  [ ] No fake tests
  [ ] No breaking API changes without migration
  [ ] No missing migrations
```

---

## Evaluation Report Storage

QA evaluation reports are stored alongside the feature spec:

```
specs/<module>/
  ├── <feature-name>.md           # Feature spec (Planner)
  ├── <feature-name>.sprint-1.md  # Sprint report round 1 (Builder)
  ├── <feature-name>.qa-1.md      # QA report round 1 (QA)
  ├── <feature-name>.sprint-2.md  # Sprint report round 2 (if needed)
  ├── <feature-name>.qa-2.md      # QA report round 2 (if needed)
  └── ...
```

This creates a complete audit trail for every feature.

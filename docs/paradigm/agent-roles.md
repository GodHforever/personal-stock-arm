# Agent Role Definitions

> **Authority level**: FIRST-CLASS. This document is part of the development paradigm. All agents must comply unconditionally.

---

## Role Hierarchy

```
User (human)
  │
  ├── Planner Agent    → WHAT to build
  ├── Builder Agent    → HOW to build it
  └── QA Agent         → WHETHER it passes
```

Each role has strict boundaries. No agent may assume another agent's responsibilities.

---

## 1. Planner Agent (规划器)

### Identity
- **Scope**: Product design & technical architecture decisions
- **Perspective**: User-facing, business-value oriented
- **Granularity**: Coarse — defines outcomes, not implementations

### Inputs
- User requirement / feature description / bug report
- Current CLAUDE.md (to understand existing modules)
- `skills/registry.yaml` (to know what's already available)

### Outputs
- **Feature Spec** document, written to `specs/<module>/<feature-name>.md`

### Feature Spec Template (mandatory structure)

```markdown
# Feature: <name>

## User Story
As a <role>, I want <capability>, so that <benefit>.

## Acceptance Criteria
- [ ] AC-1: <testable condition>
- [ ] AC-2: <testable condition>
- [ ] ...

## Data Flow
Input: <what data enters the system>
Processing: <high-level transformation steps>
Output: <what the user sees/receives>

## API Contract
- `POST /api/v1/<route>` — <purpose>
  - Request: `{ field: type, ... }`
  - Response: `{ code: 0, data: { ... } }`

## Dependencies
- Requires: <list of modules that must exist>
- Provides: <what this module exposes to others>

## Non-functional Requirements
- Performance: <constraints>
- Security: <requirements>
- Compatibility: <platform considerations>

## Skills Evaluation
- Searched: <what was searched for>
- Found: <relevant skills/tools discovered>
- Decision: <use directly / reference / ignore, with reasoning>
```

### Rules
1. **Only "what" and "why"** — never dictate implementation details (no specific class names, algorithms, or code patterns)
2. **One spec = one deliverable increment** — must be independently deployable and testable
3. **Acceptance criteria must be testable** — each criterion maps to at least one test case
4. **Skills evaluation is mandatory** — before every spec, search for reusable external skills/tools
5. **No orphan specs** — every spec must declare its dependencies and what it provides

---

## 2. Builder Agent (生成器)

### Identity
- **Scope**: Feature implementation within the boundaries of a single feature spec
- **Perspective**: Engineering, code-quality oriented
- **Granularity**: Fine — writes code, tests, and documentation

### Inputs
- Feature spec from Planner (`specs/<module>/<feature-name>.md`)
- CLAUDE.md (coding conventions, existing architecture)
- Existing codebase (for integration context)

### Outputs
- Production code in `src/`
- Unit tests in `tests/unit/`
- Updated CLAUDE.md (Module Checklist)
- Sprint Report (for QA)

### Rules
1. **Read CLAUDE.md first** — understand all conventions before writing any code
2. **Read the spec fully** — confirm understanding of every acceptance criterion
3. **One sprint = one spec** — do not bundle multiple features
4. **Follow existing patterns** — if the codebase has an established pattern, use it; do not introduce new patterns without reason
5. **Self-check before QA submission** — see Self-Check Checklist below
6. **Update CLAUDE.md after merge** — add/update the Module Checklist entry
7. **External skills integration** — if the spec's Skills Evaluation recommends integration, build adapter layers with independent tests; adapter code must not exceed 200 lines

### Self-Check Checklist (all must pass before submitting to QA)

```
[ ] Code follows CLAUDE.md coding conventions
[ ] No hardcoded configuration values (uses config system)
[ ] All acceptance criteria have corresponding tests
[ ] All new dependencies added to requirements.txt / package.json
[ ] External calls have timeout, retry, and error handling
[ ] No security issues (no exposed API keys, no injection risks)
[ ] Lint passes with zero errors
[ ] Type check passes
[ ] All unit tests pass
[ ] If external skills integrated: adapter has independent tests
```

### Sprint Report Format

```markdown
## Sprint Report

- **Feature Spec**: <spec name and path>
- **Files Changed**: <list of new/modified files>
- **New Dependencies**: <list, or "none">
- **Test Coverage**: <passed/total>
- **Self-Check Results**: <pass/fail for each item>
- **Known Limitations**: <any caveats or deferred work>
- **Integrated Skills**: <list, or "none">
```

---

## 3. QA Agent (评估器)

### Identity
- **Scope**: Quality assurance and acceptance testing
- **Perspective**: Adversarial — actively seeks defects and gaps
- **Granularity**: Systematic — evaluates against predefined criteria

### Inputs
- Sprint Report from Builder
- Feature Spec from Planner
- Code diff (changed files)
- CLAUDE.md (conventions to verify against)

### Outputs
- **Evaluation Report** with score and detailed feedback

### Rules
1. **Evaluate against the spec, not personal preference** — acceptance criteria are the authority
2. **Score objectively** — use the scoring rubric defined in `quality-gates.md`
3. **Provide actionable feedback** — every "fail" must include what's wrong and what to fix
4. **Write additional tests** — supplement Builder's tests with integration and scenario tests
5. **Verify CLAUDE.md compliance** — check coding conventions, naming, configuration patterns
6. **Check environmental compatibility** — verify Docker build succeeds, environment detection works

### Evaluation Report Format

```markdown
## QA Evaluation Report

- **Feature Spec**: <spec name>
- **Sprint Round**: <1/2/3>
- **Overall Score**: <X/100>
- **Verdict**: PASS (≥80) / CONDITIONAL (60-79) / FAIL (<60)

### Scoring Breakdown
| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Functional Completeness | 30% | | |
| Code Quality | 20% | | |
| API Contract | 15% | | |
| Error Handling | 15% | | |
| Database | 10% | | |
| Security | 10% | | |

### Issues Found
1. [MUST FIX] <description>
2. [SHOULD FIX] <description>
3. [SUGGESTION] <description>

### Tests Added
- <list of integration/scenario tests added by QA>
```

---

## Inter-Agent Communication

Agents do not communicate directly. Communication flows through artifacts:

```
Planner → [Feature Spec file] → Builder
Builder → [Sprint Report + code] → QA
QA → [Evaluation Report] → Builder (if not passed) / merge (if passed)
```

No agent should modify another agent's output files. Planner writes specs, Builder writes code, QA writes evaluation reports.

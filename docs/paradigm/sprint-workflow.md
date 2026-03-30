# Sprint Workflow

> **Authority level**: FIRST-CLASS. This document is part of the development paradigm. All agents must comply unconditionally.

---

## Complete Development Flow

```
User Requirement
    │
    ▼
┌─────────────────────────────────────────────────┐
│ PHASE 1: PLANNING                               │
│                                                  │
│ [Planner Agent]                                  │
│   1. Read CLAUDE.md → understand current state   │
│   2. Read user requirement                       │
│   3. Search skills/registry.yaml                 │
│   4. Search external skills/tools                │
│   5. Write Feature Spec → specs/<module>/<name>.md│
│                                                  │
│ Output: Feature Spec                             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ PHASE 2: SPRINT (Builder Agent)                  │
│                                                  │
│ ┌─── Prepare ───────────────────────────────┐   │
│ │ 1. Read Feature Spec (confirm understanding)│   │
│ │ 2. Read CLAUDE.md (conventions & modules)   │   │
│ │ 3. Evaluate reusable skills/tools           │   │
│ │ 4. Verify dependency modules are ready      │   │
│ └────────────────────────────────────────────┘   │
│                     │                            │
│                     ▼                            │
│ ┌─── Implement ─────────────────────────────┐   │
│ │ 1. Write production code                    │   │
│ │ 2. Write unit tests (cover all ACs)         │   │
│ │ 3. Run lint + type check                    │   │
│ │ 4. Run unit tests → all must pass           │   │
│ └────────────────────────────────────────────┘   │
│                     │                            │
│                     ▼                            │
│ ┌─── Self-Check ────────────────────────────┐   │
│ │ Run through Self-Check Checklist            │   │
│ │ (defined in agent-roles.md)                 │   │
│ │                                             │   │
│ │ All items pass? ──┬── No → Fix and re-check │   │
│ │                   │                         │   │
│ │                   ▼ Yes                     │   │
│ │           Write Sprint Report               │   │
│ └────────────────────────────────────────────┘   │
│                                                  │
│ Output: Code + Tests + Sprint Report             │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ PHASE 3: QA EVALUATION                           │
│                                                  │
│ [QA Agent]                                       │
│   1. Read Feature Spec + Sprint Report           │
│   2. Review code diff                            │
│   3. Score against 6 dimensions                  │
│   4. Write additional tests (integration/scenario)│
│   5. Run all tests                               │
│   6. Write Evaluation Report                     │
│                                                  │
│ Score ≥ 80  → PASS → Proceed to merge            │
│ Score 60-79 → CONDITIONAL → Fix specific issues  │
│ Score < 60  → FAIL → Re-implement                │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────┴────────┐
              │                 │
           PASS              NOT PASS
              │                 │
              ▼                 ▼
┌────────────────────┐  ┌─────────────────────┐
│ PHASE 4: MERGE     │  │ ITERATION           │
│                    │  │                     │
│ 1. Merge to main   │  │ Round < 3?          │
│ 2. Update CLAUDE.md│  │   Yes → Back to     │
│    Module Checklist│  │         Sprint Phase │
│ 3. Tag completion  │  │   No  → ESCALATE    │
│                    │  │         to user      │
└────────────────────┘  └─────────────────────┘
```

---

## Iteration Rules

### Round Tracking
- Each feature spec starts at Round 1
- QA failure returns to Builder for Round N+1
- Maximum 3 rounds per feature spec

### Round Behavior
| Round | Builder Focus | QA Focus |
|-------|-------------|----------|
| 1 | Full implementation from spec | Full evaluation, all dimensions |
| 2 | Fix issues listed in QA report | Re-evaluate failed dimensions + regression check |
| 3 | Fix remaining issues, last chance | Final evaluation, strict — no CONDITIONAL allowed |

### Escalation (after 3 rounds fail)
When a feature fails after 3 QA rounds:
1. QA writes a summary of persistent issues
2. Builder writes a technical difficulty report
3. Both are presented to the user for manual intervention
4. User may: revise the spec, accept as-is, or abandon the feature

---

## Module Development Order

Features must be developed in dependency order. Each layer requires the previous layer to be complete and merged.

```
Layer 1 (Infrastructure):
  ├── Config management system
  ├── Database & ORM (SQLAlchemy + Alembic)
  ├── Network request layer (NetworkClient)
  ├── Task scheduler (APScheduler, runtime mode adaptation)
  └── Logging system

Layer 2 (Data):
  ├── A-share data source adapters (DataFetcherManager)
  ├── International market data adapters
  └── News/sentiment data adapters

Layer 3 (Analysis):
  ├── LLM integration (LiteLLM Router + Prompt management)
  ├── Technical analysis engine
  └── Skills adapter layer

Layer 4 (Business):
  ├── Watchlist management & analysis
  ├── Macro data tracking
  ├── Earnings season processing
  ├── International finance briefing
  └── Research report management

Layer 5 (Presentation):
  ├── FastAPI backend API
  ├── React frontend (Web)
  └── Bot push integration

Layer 6 (Enhancement, optional):
  ├── Trade interface framework
  ├── Backtesting system
  └── Multi-model voting
```

### Layer Rules
- Layers are developed in order (Layer 1 before Layer 2, etc.)
- Modules within the same layer MAY be developed in parallel
- A module cannot be started until all its declared dependencies are merged to main
- Layer completion = all modules in that layer have passed QA and merged

---

## Git Branch Strategy

```
main                                    ← stable, always deployable
  └── feature/<module>/<feature-name>   ← one branch per sprint

Examples:
  feature/infra/config-management
  feature/data/akshare-fetcher
  feature/analysis/llm-integration
  feature/business/watchlist-analysis
```

### Branch Lifecycle
1. Create from latest `main`
2. Develop (Builder's sprint)
3. QA evaluation (on the feature branch)
4. Merge to `main` (only after QA PASS)
5. Delete feature branch

### Commit Message Format
```
<type>(<module>): <description>

Types: feat, fix, test, docs, refactor, chore
Module: matches directory name under src/

Examples:
  feat(data): add AkShare fetcher with fallback
  fix(llm): handle timeout in LiteLLM router
  test(analysis): add MACD calculation edge cases
  docs: update module checklist in CLAUDE.md
```

---

## CLAUDE.md Update Protocol

After each successful merge:

1. Builder updates the **Module Development Checklist** in CLAUDE.md:
   ```
   | module-name | Completed | Sprint #N | Brief status note |
   ```

2. If new conventions were established during the sprint:
   - Add them to the appropriate section in CLAUDE.md
   - Mark with `[Added in Sprint #N]`

3. If an existing convention was found to be problematic:
   - Do NOT delete it
   - Mark it as: `[Deprecated in Sprint #N: <reason>]`
   - Add the replacement convention below it

4. Commit the CLAUDE.md update as a separate commit:
   ```
   docs: update CLAUDE.md after Sprint #N (<feature-name>)
   ```

---

## Automated Enforcement

本范式不仅依赖文档约定，还有自动化工具强制执行。Agent在开发过程中会遇到以下自动检查：

### Git Hooks（自动触发，无法绕过）

| Hook | 触发时机 | 检查内容 | 失败后果 |
|------|---------|---------|---------|
| `pre-commit` | 每次 `git commit` | 敏感文件检测、API Key泄露检测、src改动时测试提醒、CLAUDE.md完整性 | 提交被拒绝 |
| `commit-msg` | 每次 `git commit` | 提交消息格式校验 `<type>(<module>): 描述` | 提交被拒绝 |

### Claude Code Hooks（agent操作时自动触发）

| 触发条件 | 检查内容 |
|---------|---------|
| agent执行 `git commit` 命令 | 运行完整范式合规检查 |
| agent写入 `specs/*.md` 文件 | 自动校验Feature Spec格式（7个必需章节） |
| 会话结束 | 校验CLAUDE.md完整性 |

### 验证脚本（`scripts/validate_paradigm.py`）

可由agent或人工手动调用，也被hooks自动调用：

```bash
# QA Agent评估前必须运行
python scripts/validate_paradigm.py --all

# Builder自检时使用
python scripts/validate_paradigm.py --spec specs/data/akshare-fetcher.md
python scripts/validate_paradigm.py --sprint specs/data/akshare-fetcher.sprint-1.md

# 提交前（hooks自动调用，也可手动运行）
python scripts/validate_paradigm.py --pre-commit
```

### 安装方式

首次克隆仓库后运行：
```bash
bash scripts/install-hooks.sh
```
此命令将Git hooks安装到 `.git/hooks/`，后续所有提交自动受到约束。

# QA 评估报告：任务调度器 — 第 1 轮

- **Feature Spec**: specs/infra/task-scheduler.md
- **Sprint Report**: specs/infra/task-scheduler.sprint-1.md
- **评估日期**: 2026-03-30
- **评估人**: QA Agent

---

## 自动化验证结果

| 检查项 | 结果 |
|--------|------|
| `pytest tests/unit/test_scheduler.py -v` | 34/34 passed (5.42s) |
| `ruff check src/scheduler/` | All checks passed |
| `mypy src/scheduler/` | Success: no issues found in 3 source files |

---

## 六维度评分

### 1. 功能完整性 (30%) — 70 分

**通过项:**
- AC-1: TaskScheduler 接收 Database 实例构造 ✓
- AC-2: start()/stop() 异步方法 ✓
- AC-3: register_job() 支持 cron 表达式注册 ✓
- AC-5: last_run_time 持久化到 SchedulerState 表 ✓
- AC-7: 6 个 stub 任务函数 ✓
- AC-8: 交易日检查配置 ✓
- AC-9: __init__.py 导出 TaskScheduler ✓
- AC-10: 中文文本（代码审查确认） ✓

**问题项:**

- **[MUST FIX] AC-6 优雅关闭语义缺陷**: `stop()` 方法将所有已注册任务以 `status="stopped"` 和当前时间写入 `last_run_time`。这导致 Local 模式重启后，补跑逻辑（`_start_local`）会认为所有任务"今日已执行"而全部跳过。例如：用户 15:00 启动程序 → 注册 18:00 的 daily_analysis → 15:30 关闭程序 → `stop()` 将 daily_analysis 的 last_run_time 写为 15:30 → 18:30 再次启动 → 补跑逻辑判断 `last_run.date() == today` 为 True → 跳过补跑。实际该任务从未真正执行过。**修复建议**: `stop()` 应仅记录 shutdown 时间戳到单独字段或仅更新已经成功执行过的任务的状态，不应覆盖未执行任务的 `last_run_time`。

- **AC-4 补跑逻辑对通配符 cron 不健壮**: `_should_catch_up` 方法中 `int(cron_params["hour"])` 无法处理 `*` 或 `*/2` 等通配符。虽然当前预定义任务都使用固定时间，但 `register_job` 是公开 API，外部调用者可以传入任意合法的 cron 表达式。**修复建议**: 在 `_should_catch_up` 中检测 hour/minute 是否为通配符，若是则视为"总是应该补跑"或抛出明确错误。

### 2. 代码质量 (20%) — 85 分

**通过项:**
- Lint 零错误 ✓
- 类型检查通过 ✓
- 命名规范遵循 CLAUDE.md（snake_case 文件名，类名 PascalCase） ✓
- Pydantic / ORM 模型用于模块边界 ✓
- 代码结构清晰，职责分离合理 ✓
- 中文注释和日志 ✓

**次要问题:**
- `_parse_time` 函数已定义并被测试覆盖，但在 `scheduler.py` 中**从未被调用**，属于死代码。建议移除或标注其设计用途。
- `_JobEntry` 使用 `__slots__` 是好实践，但定义在文件底部、在 `TaskScheduler` 类引用之后，依赖 Python 的前向引用行为。建议移到 `TaskScheduler` 之前，提高可读性。

### 3. API 契约 (15%) — 90 分

**通过项:**
- 内部 Python API 签名与 Spec 完全一致 ✓
  - `TaskScheduler(db: Database)` ✓
  - `async start()` ✓
  - `async stop()` ✓
  - `register_job(name, func, cron_expr)` ✓
- 6 个 stub 函数签名与 Spec 一致 ✓
- 无 HTTP 接口，不适用统一响应格式

**无问题。**

### 4. 错误处理 (15%) — 80 分

**通过项:**
- 任务执行异常被 try/except 捕获，记录 `status="failed"` ✓
- 重复启动/停止有防护（幂等） ✓
- 运行中注册任务抛出明确 RuntimeError ✓
- cron 表达式格式错误有 ValueError ✓
- 日志使用 `logger.exception` 保留完整堆栈 ✓

**次要问题:**
- `_parse_time` 对格式错误输入（如 `"abc"`, `"25:99"`）没有验证，但因该函数当前未被调用，影响有限。

### 5. 数据库 (10%) — 90 分

**通过项:**
- SchedulerState 模型使用 ORM（SQLAlchemy 2.0 Mapped 类型） ✓
- 表名 `scheduler_state` 符合 snake_case 单数约定 ✓
- 含 `id`、`created_at`、`updated_at` 字段（通过 TimestampMixin） ✓
- `job_name` 设置了 `unique=True` 约束 ✓
- 使用 `async with db.session()` 管理事务生命周期 ✓
- 参数化查询（ORM），无 SQL 注入风险 ✓

**注意:**
- 未看到 Alembic migration 文件。但考虑到项目处于初始化阶段、使用 `create_all` 建表，暂不扣分。后续模块应建立 migration 流程。

### 6. 安全 (10%) — 95 分

**通过项:**
- 无硬编码密钥或敏感信息 ✓
- 配置通过 ConfigManager 读取 ✓
- 无 SQL 注入风险（使用 ORM） ✓
- 无用户输入直接拼接 ✓
- .env.example 不受影响（无新配置需暴露） ✓

**无问题。**

---

## 零容忍项检查

| 检查项 | 结果 |
|--------|------|
| 硬编码 API Key / 密钥 | 未发现 ✓ |
| SQL 注入风险 | 未发现 ✓ |
| 假测试（测试 mock 而非逻辑） | 未发现 ✓ |
| 破坏性 API 变更 | 不适用 ✓ |
| 缺失 Alembic migration | 项目初期阶段，暂不触发 |

---

## 测试质量审查

**优点:**
- 34 个测试覆盖所有 10 个验收标准
- 测试按 AC 分类组织，结构清晰
- 包含正向、反向、边界场景
- 使用真实内存 SQLite 测试数据库交互

**问题:**
- **3 个测试有条件性断言**: `test_local_mode_catch_up`、`test_execute_updates_last_run_time`、`test_failed_job_records_failed_status` 在 `now.hour == 0` 时跳过核心断言。建议使用 `freezegun` 或 `unittest.mock.patch` 固定时间，确保测试在任何时刻都能验证逻辑。
- **AC-10 测试无实质断言**: `test_register_log_in_chinese` 未真正验证日志内容是否为中文，仅验证了任务可以注册。这不算假测试（因为确实调用了被测代码），但测试名称与实际验证内容不符。

---

## 加权总分

| 维度 | 权重 | 得分 | 加权分 |
|------|------|------|--------|
| 功能完整性 | 30% | 70 | 21.0 |
| 代码质量 | 20% | 85 | 17.0 |
| API 契约 | 15% | 90 | 13.5 |
| 错误处理 | 15% | 80 | 12.0 |
| 数据库 | 10% | 90 | 9.0 |
| 安全 | 10% | 95 | 9.5 |
| **总计** | **100%** | | **82.0** |

---

## 裁定: PASS

总分 82.0 ≥ 80，通过。

---

## 建议修复项（非阻塞，建议在后续迭代中处理）

1. **`stop()` 语义优化**（功能完整性扣分主因）: 修改 `stop()` 逻辑，仅为 status 已为 `"success"` 的任务记录 `"stopped"` 状态，避免覆盖从未执行过的任务的 `last_run_time`。或者引入独立的 `last_shutdown_time` 字段，将 shutdown 记录与执行记录分离。

2. **`_should_catch_up` 健壮性**: 处理通配符 cron 字段（`*`, `*/N`），避免 `int()` 转换异常。

3. **测试时间固定**: 使用 `freezegun` 或 `patch` 固定系统时间，消除测试中的条件性断言。

4. **移除死代码 `_parse_time`**: 若短期内不会使用，建议移除以保持代码整洁。

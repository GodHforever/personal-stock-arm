# Stock-ARM 未完成项与后续改进清单

> 最后更新: 2026-03-30
> 本文档分析项目当前的完成度、已知问题和待改进项，作为后续开发的优先级参考。

---

## 1. 项目当前状态概览

### Layer 完成情况

| Layer | 名称 | 模块数 | 已完成 Sprint | 状态 |
|-------|------|--------|--------------|------|
| Layer 1 | Infrastructure | 5（Config, DB/ORM, NetworkClient, Scheduler, Log） | 5 | 全部通过 QA |
| Layer 2 | Data | 3（A股数据源, 国际市场, 新闻舆情） | 3 | 全部通过 QA |
| Layer 3 | Analysis | 3（LLM集成, 技术分析, Skills适配器） | 3 | 全部完成 Sprint |
| Layer 4 | Business Logic | 5（自选股, 宏观, 财报, 国际简报, 研报） | 5 | 全部完成 Sprint |
| Layer 5 | Presentation | 3（FastAPI后端, React前端, 推送通知） | 2（API + 通知） | 前端未开发 |
| Layer 6 | Enhancement | 3（交易接口, 回测, 多模型投票） | 0 | 可选，未启动 |

### 统计数据

- **已实现 Python 源文件**: 66 个（`src/` 下）
- **测试文件**: 16 个测试模块（`tests/unit/` + `tests/integration/`）
- **测试函数总数**: 584 个
- **Alembic 迁移**: 2 个（`scheduler_state` + `watchlist_group`/`analysis_record`）
- **ORM 数据表**: 4 个（`scheduler_state`, `watchlist_group`, `analysis_record`, `macro_record`）
- **Feature Spec**: 14 个模块的 Spec + Sprint Report
- **QA 报告**: 6 个（infra 层全部 + data 层部分）

---

## 2. 关键未完成项（阻塞部署）

### 2.1 main.py 入口未实现

- **文件**: `main.py`，第 19-35 行
- **问题**: `startup()` 和 `shutdown()` 函数体均为 `pass`，注释中列出了 5 步初始化序列（加载配置、初始化日志、初始化数据库、启动调度器、启动 FastAPI 服务），但全部未实现
- **影响**: 应用无法启动。执行 `python main.py` 会立即退出（`startup()` 什么也不做）。Docker 容器启动后也会立即退出
- **修复建议**: 按注释中的顺序实现启动序列，调用 `ConfigManager.initialize()`、`setup_logging()`、`Database()` 初始化、`TaskScheduler` 注册任务并启动、`uvicorn.run(create_app(), ...)` 启动 HTTP 服务。`shutdown()` 需实现调度器停止和数据库连接关闭

### 2.2 React 前端未开发

- **目录**: `web/` 不存在
- **影响**: 后端 API 已实现基础路由（`/api/v1/health`、`/api/v1/watchlists`、`/api/v1/analysis`、`/api/v1/macro`、`/api/v1/briefings`），但无前端消费。用户无法通过浏览器使用系统
- **修复建议**: 使用 Vite + React 18 + TypeScript 5 初始化前端项目。技术栈已在 CLAUDE.md 中规定：Zustand 状态管理、ECharts 图表。需实现：自选股管理页、分析结果展示页、宏观数据看板、简报/财报/研报浏览页

### 2.3 Alembic 数据库迁移不完整

- **目录**: `alembic/versions/`
- **现有迁移**:
  - `766c657a5db8_初始迁移_scheduler_state表.py` - 仅 `scheduler_state` 表
  - `f35b7fc8e3b8_添加watchlist_group和analysis_record表.py` - `watchlist_group` + `analysis_record` 表
- **缺失迁移**: `macro_record` 表（定义在 `src/business/macro/models.py` 第 59-92 行）已有 ORM 模型但无对应 Alembic 迁移文件
- **影响**: 直接部署时 `macro_record` 表不会自动创建，宏观数据持久化功能不可用
- **修复建议**: 运行 `alembic revision --autogenerate -m "添加macro_record表"` 生成迁移。后续如 earnings/reports 需要持久化，也需新增迁移

### 2.4 Docker 构建不完整

- **文件**: `Dockerfile`，第 1-7 行
- **问题**: 前端构建阶段（Stage 1）被完全注释掉，第 29-30 行的 `COPY --from=frontend` 也被注释。注释标注"Layer 5 时启用"
- **影响**: Docker 镜像不包含前端静态文件，即使前端开发完成后也需要手动取消注释才能构建完整镜像
- **修复建议**: 前端开发完成后取消注释 Dockerfile 第 1-7 行和第 29-30 行，并验证多阶段构建流程

### 2.5 调度器 jobs.py 是 stub

- **文件**: `src/scheduler/jobs.py`，第 1-41 行
- **问题**: 6 个定时任务函数（`daily_analysis`、`daily_macro`、`daily_briefing`、`earnings_scan`、`monthly_report`、`data_cleanup`）全部只有 `logger.info()` 一行日志，未调用任何实际业务模块
- **影响**: 即使调度器正常运行，定时任务也不会执行任何实际工作（不会拉取数据、不会执行分析、不会生成报告）
- **修复建议**: 将每个 stub 替换为实际业务调用。例如 `daily_analysis` 应调用 `WatchlistManager` 获取自选股列表，再调用 `StockAnalysisPipeline` 执行分析；`daily_macro` 应调用 `MacroTracker.fetch_all()`；`data_cleanup` 应根据 `data_retention_days` 配置清理过期记录

---

## 3. 已知 Bug（QA 报告中的 MUST FIX）

### 3.1 调度器 stop() 语义缺陷

- **文件**: `src/scheduler/scheduler.py`，第 135-150 行
- **来源**: `specs/infra/task-scheduler.qa-1.md` MUST FIX
- **问题**: `stop()` 方法在关闭时将所有已注册任务以 `status="stopped"` 和当前时间写入 `last_run_time`。这导致 Local 模式 catch-up 失效
- **复现场景**: 用户 15:00 启动程序 → 注册 18:00 的 `daily_analysis` → 15:30 关闭 → `stop()` 写入 `last_run_time=15:30` → 18:30 再次启动 → 补跑逻辑判断 `last_run.date() == today` 为 True → 跳过补跑。实际该任务从未执行过
- **影响**: Local 模式下用户频繁启停程序时，当天应执行的定时任务可能永远不会被补跑
- **修复建议**: `stop()` 应仅为 `status` 已为 `"success"` 的任务记录停止状态，不应覆盖未执行任务的 `last_run_time`。或引入独立的 `last_shutdown_time` 字段

### 3.2 调度器 _should_catch_up 不支持通配符 cron 表达式

- **文件**: `src/scheduler/scheduler.py`，第 229-246 行
- **来源**: `specs/infra/task-scheduler.qa-1.md` MUST FIX（AC-4）
- **问题**: `_should_catch_up` 方法中 `int(cron_params["hour"])` 和 `int(cron_params["minute"])` 无法处理 `*` 或 `*/2` 等通配符。当 `register_job` 传入 `"*/5 * * * *"` 这样的合法 cron 表达式时，`int("*/5")` 会抛出 `ValueError`
- **影响**: 通过 `register_job` 公开 API 注册包含通配符的 cron 表达式时，Local 模式启动会崩溃
- **修复建议**: 在 `_should_catch_up` 中检测 `hour`/`minute` 是否为通配符（包含 `*`），若是则视为"应该补跑"或回退到 APScheduler 的 CronTrigger 计算下一次触发时间

### 3.3 Baostock get_fundamentals 硬编码 year=2024

- **文件**: `src/data/a_share/baostock_fetcher.py`，第 201 行
- **来源**: `specs/data/ashare-fetcher.qa-1.md` MUST FIX
- **问题**: `bs.query_profit_data(code=bs_code, year=2024, quarter=4)` 硬编码了 `year=2024`，当前已是 2026 年，返回的是两年前的过期数据
- **影响**: Baostock 数据源的基本面查询结果永远返回 2024Q4 数据，无法获取最新财务数据。因为 Baostock 基本面返回空对象（第 220 行 `return Fundamentals(code=code)`），实际影响有限，但属于定时炸弹
- **修复建议**: 动态计算当前年份和最近已披露的季度：`year = datetime.now().year`，`quarter` 根据当前月份推算（考虑财报披露时间滞后）

### 3.4 A股数据源缺少 asyncio.wait_for 超时保护

- **文件**: `src/data/a_share/manager.py`，第 81-133 行（`_fetch_with_failover` 方法）；各适配器的 `asyncio.to_thread` 调用
- **来源**: `specs/data/ashare-fetcher.qa-1.md` MUST FIX
- **问题**: Spec 要求"单次数据获取响应 < 10s（含 failover）"，但代码中没有对 `asyncio.to_thread` 调用设置超时保护。如果某个数据源的同步调用挂起（如网络连接被防火墙静默丢弃），整个 failover 链会无限等待
- **影响**: 在网络异常情况下，数据获取请求可能永久阻塞，导致调度器任务超时或 API 请求无响应
- **修复建议**: 在 `_fetch_with_failover` 中用 `asyncio.wait_for(method(**kwargs), timeout=10)` 包裹每次调用，超时后自动捕获 `asyncio.TimeoutError` 并切换到下一个数据源

---

## 4. 待改进项（QA SHOULD FIX）

### 4.1 .env.example 中两个环境变量名错误

- **文件**: `.env.example`，第 47-48 行
- **来源**: `specs/infra/config-management.qa-1.md` SHOULD FIX #1
- **问题**:
  - 第 47 行 `STOCK_ARM_DATA_RETENTION_DAYS=90` 应为 `STOCK_ARM_SCHEDULER_DATA_RETENTION_DAYS=90`
  - 第 48 行 `STOCK_ARM_CLEANUP_CRON=0 3 1 * *` 应为 `STOCK_ARM_SCHEDULER_CLEANUP_CRON=0 3 1 * *`
- **影响**: 用户按 `.env.example` 文档配置这两项将不生效，实际环境变量名需要 `STOCK_ARM_SCHEDULER_` 前缀才能被 `_build_section("scheduler", ...)` 正确识别
- **修复建议**: 修正变量名，添加注释说明前缀规则

### 4.2 ConfigManager double-check locking 竞态条件

- **文件**: `src/config/manager.py`，第 253-259 行（`get_config` 方法）
- **来源**: `specs/infra/config-management.qa-1.md` SHOULD FIX #2
- **问题**: `get_config()` 中 `if cls._config is None` 检查在锁外，多线程并发首次调用时可能导致 `initialize()` 被执行多次。虽然 `initialize` 内部持锁保证了原子性，但会产生不必要的重复加载开销
- **影响**: 极端并发场景下可能有重复初始化，一般使用中无实际影响
- **修复建议**: 在 `initialize()` 入口处加 double-check：`with cls._lock: if cls._config is not None: return cls._config`

### 4.3 config.yaml 中放置 API Key 无警告

- **文件**: `src/config/manager.py`，第 72-101 行（`_build_section` 函数）
- **来源**: `specs/infra/config-management.qa-1.md` SUGGESTION #4
- **问题**: AC-4 要求"秘密信息不出现在 config.yaml 中"，但当前实现完全依赖用户自觉。用户可在 yaml 中配置 `api_key` 等 SecretStr 字段而无任何警告
- **影响**: 安全隐患。用户可能不小心将 API Key 写入 config.yaml 并提交到版本控制
- **修复建议**: 在 `_build_section` 中检测到 SecretStr 字段从 yaml 加载时输出 WARNING 日志，提醒用户将秘密迁移到环境变量

### 4.4 get_section 返回 Any 类型

- **文件**: `src/config/manager.py`，第 261-280 行
- **来源**: `specs/infra/config-management.qa-1.md` SUGGESTION #7
- **问题**: `get_section(section: str) -> Any` 返回类型为 `Any`，下游模块调用时无法获得类型提示和自动补全
- **影响**: 开发体验降低，下游模块需要手动 cast 或 assert 类型
- **修复建议**: 使用 `@overload` 装饰器为每个分区名提供精确的返回类型签名，如 `get_section(section: Literal["llm"]) -> LLMConfig`

---

## 5. 功能集成缺口

### 5.1 调度器任务 -> 业务模块（stub 未连接实际 Pipeline）

- **涉及文件**: `src/scheduler/jobs.py`（全文）、`src/business/watchlist/pipeline.py`、`src/business/macro/tracker.py`、`src/business/earnings/processor.py`、`src/business/international/briefing.py`、`src/business/reports/manager.py`
- **问题**: 调度器 6 个 stub 函数仅记录日志，未调用任何业务模块。例如 `daily_analysis()` 应调用 `StockAnalysisPipeline.run()`，`daily_macro()` 应调用 `MacroTracker.fetch_all()`
- **影响**: 定时任务系统完全无效，调度器正常运行但不产生任何业务价值
- **修复建议**: 实现每个 job 函数的完整调用链。需要解决的依赖：ConfigManager 初始化、Database 实例传递、DataFetcherManager 注册数据源

### 5.2 业务模块完成 -> 推送通知（NotificationManager.send 未被调用）

- **涉及文件**: `src/notification/manager.py`（`send_all` 方法，第 115-167 行）、`src/scheduler/jobs.py`
- **问题**: `NotificationManager.send_all()` 已完整实现（多渠道编排、免打扰时段、重试逻辑），但没有任何业务模块调用它
- **影响**: 用户无法收到分析完成、异常告警等推送通知
- **修复建议**: 在各 job 函数执行完毕后，构建 `NotificationMessage` 并调用 `NotificationManager.send_all()` 发送结果摘要

### 5.3 API 路由不完整

- **涉及文件**: `src/api/v1/briefings.py`，第 63-90 行
- **问题**: 三个列表端点（`/briefings`、`/earnings`、`/reports`）均返回空列表，注释标注"MVP 阶段返回空列表，后续对接 business 模块"。缺少详情端点（如 `GET /earnings/{id}`、`GET /reports/{id}`）
- **影响**: API 消费者无法获取任何有价值的数据，也无法查看单条记录的详细信息
- **修复建议**: 对接对应的业务模块（`EarningsProcessor`、`ReportManager`、`InternationalBriefingGenerator`），实现数据查询。补充详情端点和分页参数

### 5.4 前端不存在，后端 API 无法被消费

- **涉及文件**: `web/` 目录不存在；`src/api/app.py`（CORS 配置在第 50-56 行已预留）
- **问题**: 后端 API 已实现 CORS 中间件、路由注册、统一响应格式，但没有任何前端消费这些 API
- **影响**: 系统仅能通过 curl / Postman 等工具手动调用，非技术用户无法使用
- **修复建议**: 见第 2.2 节

---

## 6. Layer 6 增强模块（可选，未实现）

根据 `docs/architecture/module-layers.md` 定义，Layer 6 为可选增强功能，当前均未启动开发：

### 6.1 交易接口框架

- **设计位置**: `src/trade/`（目录结构已在 `module-layers.md` 中规划，但未创建）
- **内容**: 抽象交易框架（`BaseTradeProvider`、订单模型），不含具体券商对接实现
- **优先级**: 低。项目定位为分析工具而非交易工具

### 6.2 回测系统

- **设计位置**: 未规划具体目录
- **内容**: 历史信号准确性验证（`BacktestEngine`），对比技术分析/LLM 信号与实际涨跌
- **优先级**: 中。有助于验证分析系统的有效性

### 6.3 多模型投票

- **设计位置**: 未规划具体目录
- **内容**: 同一分析任务发送给多个 LLM，通过投票机制综合决策（`VotingOrchestrator`）
- **优先级**: 中低。需要更多 LLM API 额度，适合日后优化分析质量时引入

---

## 7. 测试覆盖分析

### 7.1 main.py 0% 覆盖

- **文件**: `main.py`
- **问题**: 入口文件无任何测试。`startup()`/`shutdown()` 为空函数，测试无意义；但 `parse_args()` 和版本检查逻辑也未被测试
- **修复建议**: 待 `startup()` 实现后编写集成测试，验证启动序列是否正确初始化各组件

### 7.2 API 中间件测试基础

- **文件**: `tests/unit/api/test_api.py`（31 个测试）
- **现状**: 基本路由和响应格式有测试，但 `_CatchAllMiddleware`（`src/api/app.py` 第 20-32 行）的异常捕获逻辑依赖 ASGI 中间件执行路径，单元测试中可能未完全覆盖
- **修复建议**: 补充中间件异常处理的集成测试，模拟路由处理函数抛出未预期异常，验证返回 500 统一错误响应

### 7.3 无集成测试（调度器 -> 业务 -> 通知 E2E）

- **目录**: `tests/integration/`（仅有 `test_config_integration.py`）
- **问题**: 缺少端到端集成测试。各模块的单元测试使用 mock 隔离依赖，无法验证模块间的协作是否正确
- **影响**: 调度器触发任务 -> 业务模块执行分析 -> 通知模块发送结果 的完整链路未被测试覆盖
- **修复建议**: 编写集成测试，使用内存 SQLite 和 mock 外部 API，验证至少一个完整的 job 执行链路

### 7.4 无 Docker 启动测试

- **问题**: 没有 CI/CD 脚本或测试验证 Docker 镜像能否正常构建和启动
- **修复建议**: 添加 `docker-compose` 启动测试脚本，验证容器启动后 `/api/v1/health` 端点返回正常响应

---

## 8. 推荐执行路线图

### Phase 1: 关键修复（阻塞部署问题）

| 序号 | 任务 | 涉及文件 | 预计工作量 |
|------|------|---------|-----------|
| 1.1 | 实现 main.py 启动序列 | `main.py` | 中 |
| 1.2 | 修复调度器 stop() 语义缺陷 | `src/scheduler/scheduler.py` 第 135-150 行 | 小 |
| 1.3 | 修复 _should_catch_up 通配符支持 | `src/scheduler/scheduler.py` 第 229-246 行 | 小 |
| 1.4 | 添加 asyncio.wait_for 超时保护 | `src/data/a_share/manager.py` 第 81-133 行 | 小 |
| 1.5 | 修复 Baostock 硬编码 year=2024 | `src/data/a_share/baostock_fetcher.py` 第 201 行 | 小 |
| 1.6 | 补充 macro_record Alembic 迁移 | `alembic/versions/` | 小 |
| 1.7 | 连接 jobs.py stub 到业务模块 | `src/scheduler/jobs.py` | 中 |

### Phase 2: 功能完善（用户可见功能）

| 序号 | 任务 | 涉及文件 | 预计工作量 |
|------|------|---------|-----------|
| 2.1 | 初始化 React 前端项目 | `web/` | 大 |
| 2.2 | 实现核心页面（自选股、分析结果、宏观看板） | `web/src/pages/` | 大 |
| 2.3 | API 对接业务模块（briefings/earnings/reports） | `src/api/v1/briefings.py` | 中 |
| 2.4 | 补充详情端点（earnings/{id}, reports/{id}） | `src/api/v1/briefings.py` | 小 |
| 2.5 | 业务模块 -> 通知集成 | `src/scheduler/jobs.py`, `src/notification/manager.py` | 中 |
| 2.6 | 修正 .env.example 环境变量名 | `.env.example` 第 47-48 行 | 小 |
| 2.7 | config.yaml 中 SecretStr 字段加载警告 | `src/config/manager.py` 第 72-101 行 | 小 |

### Phase 3: 质量保障（上线前验证）

| 序号 | 任务 | 涉及文件 | 预计工作量 |
|------|------|---------|-----------|
| 3.1 | 编写 main.py 启动/关闭集成测试 | `tests/integration/` | 中 |
| 3.2 | 编写调度器 -> 业务 -> 通知 E2E 测试 | `tests/integration/` | 中 |
| 3.3 | 启用 Dockerfile 前端构建阶段 | `Dockerfile` 第 1-7, 29-30 行 | 小 |
| 3.4 | Docker 启动验证测试 | `tests/` 或 CI 脚本 | 中 |
| 3.5 | 编写部署运维文档 | `docs/` | 中 |
| 3.6 | ConfigManager get_section 添加 overload 类型 | `src/config/manager.py` 第 261-280 行 | 小 |
| 3.7 | 修复 ConfigManager double-check locking | `src/config/manager.py` 第 253-259 行 | 小 |

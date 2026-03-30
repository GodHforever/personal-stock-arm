# Feature: 任务调度器

## User Story
As a Stock-ARM 用户，I want 一个基于 APScheduler 的统一任务调度器，能根据运行模式（Cloud/Docker 持续调度 vs Local 补跑+实时调度）自动适配行为，记录每个任务的最近运行时间，并在程序关闭时优雅停止，so that 无论我以何种方式部署，定时分析、宏观数据跟踪、财报扫描等任务都能按时执行，不会因为程序重启或非持续运行而遗漏。

## Acceptance Criteria
- [ ] AC-1: 提供 TaskScheduler 类，基于 APScheduler 3.x AsyncIOScheduler，接收 Database 实例作为依赖注入
- [ ] AC-2: 提供 `start()` 异步方法启动调度器，`stop()` 异步方法停止调度器
- [ ] AC-3: 提供 `register_job(name, func, cron_expr)` 方法，支持注册 cron 表达式定义的定时任务
- [ ] AC-4: 运行模式自适应 — Cloud/Docker 模式下持续调度，Local 模式下启动时检查 last_run_time，补跑当天遗漏任务，然后注册剩余今日任务
- [ ] AC-5: last_run_time 持久化到 SchedulerState 表，每次任务执行完成后更新
- [ ] AC-6: stop() 时记录所有已注册任务的 last_run_time，实现优雅关闭
- [ ] AC-7: 预定义 6 个 stub 任务函数（daily_analysis、daily_macro、daily_briefing、earnings_scan、monthly_report、data_cleanup），每个为 async def，仅记录日志
- [ ] AC-8: 支持交易日检查配置 — 当 STOCK_ARM_TRADING_DAY_CHECK=true 时，daily 类任务在非交易日自动跳过
- [ ] AC-9: 模块提供清晰的公开接口（TaskScheduler），通过 `src/scheduler/__init__.py` 导出
- [ ] AC-10: 所有人类可读文本（日志、注释、错误消息）使用中文

## Data Flow
Input: ConfigManager 提供的 SchedulerConfig（任务时间、交易日检查开关）、RuntimeMode（运行模式）、Database 实例（读写 SchedulerState）
Processing:
  1. 从 ConfigManager 获取 SchedulerConfig 和 RuntimeMode
  2. 创建 AsyncIOScheduler 实例
  3. 根据配置注册预定义任务（解析时间字符串为 cron 表达式）
  4. Cloud/Docker 模式：直接启动调度器持续运行
  5. Local 模式：查询 SchedulerState 表获取 last_run_time，判断当天任务是否已执行，补跑遗漏任务，注册未来任务
  6. 任务执行后：更新 SchedulerState 表的 last_run_time 和 status
  7. stop() 调用时：停止调度器，记录所有任务的最终 last_run_time
Output: 按配置时间自动触发的任务执行，持久化的运行状态记录

## API Contract
- 内部 Python API（非 HTTP 接口）：
  - `TaskScheduler(db: Database)`: 构造函数，接收数据库实例
  - `async start()`: 启动调度器，根据运行模式执行补跑逻辑
  - `async stop()`: 停止调度器，记录 last_run_time
  - `register_job(name: str, func: Callable, cron_expr: str)`: 注册定时任务
- Stub 任务函数（`src/scheduler/jobs.py`）：
  - `async daily_analysis()`: 每日个股分析（18:00）
  - `async daily_macro()`: 每日宏观数据（18:30）
  - `async daily_briefing()`: 每日简报（19:00）
  - `async earnings_scan()`: 财报扫描（20:00，财报季）
  - `async monthly_report()`: 月度报告（每月1号 09:00）
  - `async data_cleanup()`: 数据清理（每月1号 03:00）

## Dependencies
- Requires:
  - Config 模块（ConfigManager、SchedulerConfig、RuntimeMode）— 提供调度配置和运行模式
  - Log 模块（get_logger）— 提供日志记录
  - Database 模块（Database、SchedulerState）— 持久化任务运行状态
- Provides:
  - 统一的任务调度框架，供 Layer 4 业务模块注册具体任务实现
  - 运行模式自适应的调度行为（持续/补跑）
  - 任务执行状态追踪

## Non-functional Requirements
- Performance: 调度器启动和补跑检查为启动时一次性操作；任务注册为轻量级操作；last_run_time 更新为异步数据库写入
- Security: 不存储敏感信息；任务函数不直接处理用户数据；配置通过 ConfigManager 读取
- Compatibility: APScheduler 3.x 兼容所有目标平台；AsyncIOScheduler 与 asyncio 事件循环集成；SQLite 后端通过已有 Database 模块访问

## Skills Evaluation
- Searched: Python 任务调度库、APScheduler asyncio 集成、cron 表达式解析
- Found:
  - **APScheduler 3.x**: 成熟的 Python 调度库，原生支持 AsyncIOScheduler 和 CronTrigger
  - **croniter**: cron 表达式解析库，可用于判断任务是否应执行
- Decision: 直接使用 APScheduler 3.x（direct-use），已在 requirements.txt 中声明为项目依赖。croniter 不需要额外引入，APScheduler 内置 CronTrigger 已能满足需求

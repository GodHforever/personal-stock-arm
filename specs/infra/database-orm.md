# Feature: 数据库与ORM基础设施

## User Story
As a Stock-ARM 开发者，I want 一个基于 SQLAlchemy 2.0+ 的异步数据库层，包含 WAL 模式的 SQLite 引擎、统一的模型基类、以及 Alembic 迁移管理，so that 上层业务模块可以安全、高效地持久化用户配置、分析结果、调度器状态和 LLM 日志等不可重新获取的数据。

## Acceptance Criteria
- [ ] AC-1: 提供异步数据库引擎，基于 SQLAlchemy 2.0+ async API 和 aiosqlite 驱动，从 ConfigManager 读取数据库连接配置
- [ ] AC-2: 数据库初始化时自动启用 SQLite WAL 模式，提高并发读写性能
- [ ] AC-3: 提供异步 session 工厂，支持通过异步上下文管理器获取数据库会话，自动处理提交和回滚
- [ ] AC-4: 提供统一模型基类（DeclarativeBase），包含 TimestampMixin，自动提供 id（主键）、created_at、updated_at 三个字段
- [ ] AC-5: 提供初始数据模型 SchedulerState，包含 job_name（任务名称）、last_run_time（最近运行时间）、status（运行状态）字段
- [ ] AC-6: 集成 Alembic 异步迁移管理，支持自动生成和执行数据库迁移脚本
- [ ] AC-7: 提供初始迁移脚本，创建 scheduler_state 表，迁移可正向执行和回滚
- [ ] AC-8: 数据库文件路径根据 ConfigManager 的 data_dir 配置动态解析，支持不同部署环境
- [ ] AC-9: 数据库模块提供清晰的公开接口（Database 类、Base 基类、get_session 函数），供上层模块直接导入使用
- [ ] AC-10: 所有表命名遵循 snake_case 单数形式，符合项目数据库命名规范

## Data Flow
Input: ConfigManager 提供的数据库配置（连接URL、echo开关）和数据目录配置
Processing:
  1. 从 ConfigManager 获取 DatabaseConfig（url、echo）和 data_dir
  2. 解析数据库文件路径，确保数据目录存在
  3. 创建异步引擎（AsyncEngine），配置连接池参数
  4. 执行 WAL 模式设置（PRAGMA journal_mode=WAL）
  5. 提供 AsyncSession 工厂，封装事务管理
  6. 通过 Alembic 管理 schema 变更和迁移历史
Output: 就绪的数据库连接、可用的 ORM 会话、版本化的数据库 schema

## API Contract
- 内部 Python API（非 HTTP 接口）：
  - `Database` 类：管理异步引擎生命周期，提供初始化（含 WAL 设置）和关闭方法
  - `get_session()`: 异步上下文管理器，返回 AsyncSession 实例
  - `Base`: SQLAlchemy DeclarativeBase，所有模型继承此基类
  - `SchedulerState` 模型：job_name (str, unique), last_run_time (datetime, nullable), status (str)

## Dependencies
- Requires:
  - Config 模块（ConfigManager、DatabaseConfig）— 提供数据库连接配置
  - Log 模块（get_logger）— 提供日志记录
- Provides:
  - 异步数据库引擎和会话管理，供所有需要持久化的上层模块使用
  - ORM 模型基类和 TimestampMixin，供业务模块定义数据模型
  - Alembic 迁移框架，供后续 schema 变更使用

## Non-functional Requirements
- Performance: 数据库初始化为启动时一次性操作；WAL 模式确保读写不互阻塞；session 获取为轻量级操作
- Security: 数据库文件路径从配置系统读取，不硬编码；不存储可重新获取的原始数据（行情、新闻原文等）
- Compatibility: 支持 SQLite 3.x（所有目标平台内置）；异步驱动依赖 aiosqlite；Alembic 迁移脚本跨平台兼容

## Skills Evaluation
- Searched: SQLAlchemy 异步数据库管理、SQLite WAL 配置、Alembic 异步迁移
- Found:
  - **SQLAlchemy 2.0+ async**: 官方异步支持，提供 AsyncEngine、AsyncSession、DeclarativeBase
  - **aiosqlite**: SQLite 异步驱动，与 SQLAlchemy async 配合使用
  - **Alembic**: SQLAlchemy 官方迁移工具，支持异步环境配置
- Decision: 直接使用 SQLAlchemy 2.0+ async API + aiosqlite + Alembic（direct-use），这是项目 tech stack 指定的技术选型，生态成熟，文档完善

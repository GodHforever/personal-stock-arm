# Feature: 日志系统

## User Story
As a Stock-ARM 开发者或运维人员，I want 一个统一的日志系统，能够根据运行模式（本地/云端/Docker）自动配置日志输出目标和格式，so that 我可以在开发时通过日志文件排查问题，在云端部署时同时通过 stdout 和文件查看运行状态。

## Acceptance Criteria
- [ ] AC-1: 提供 `setup_logging(config)` 函数，接受 AppConfig 并根据运行模式配置日志系统
- [ ] AC-2: Cloud/Docker 模式下同时输出到文件和 stdout（RotatingFileHandler + StreamHandler）
- [ ] AC-3: Local 模式下仅输出到文件（RotatingFileHandler）
- [ ] AC-4: RotatingFileHandler 配置为单文件 10MB，保留 5 个备份文件
- [ ] AC-5: 默认日志级别 INFO，可通过 AppConfig.log_level（来源于环境变量 STOCK_ARM_LOG_LEVEL）配置
- [ ] AC-6: 提供 `get_logger(name)` 函数，返回指定名称的 Logger 实例
- [ ] AC-7: 日志格式包含时间戳、级别、模块名、消息内容
- [ ] AC-8: 日志文件存放在 `{data_dir}/logs/` 目录下，目录不存在时自动创建
- [ ] AC-9: 模块目录命名为 `src/log/`，避免遮蔽 Python 标准库 `logging`

## Data Flow
Input: AppConfig 配置对象（包含 runtime_env、log_level、log_to_stdout、data_dir 等字段）
Processing:
  1. 从 AppConfig 读取运行模式和日志配置
  2. 确定日志输出目标：Cloud/Docker → 文件 + stdout；Local → 仅文件
  3. 创建日志目录（如不存在）
  4. 配置 RotatingFileHandler（10MB/文件，5 个备份）
  5. 根据模式决定是否添加 StreamHandler
  6. 设置统一日志格式（时间戳 + 级别 + 模块 + 消息）
  7. 应用到 root logger
Output: 配置完成的 Python logging 系统，各模块通过 `get_logger(name)` 获取命名 logger

## API Contract
- 内部 Python API（非 HTTP 接口）：
  - `setup_logging(config: AppConfig) -> None` — 初始化日志系统，应用启动时调用一次
  - `get_logger(name: str) -> logging.Logger` — 获取命名 logger，各模块使用此函数获取自己的 logger

## Dependencies
- Requires:
  - `src/config` 模块（Layer 1，已合并）— 提供 AppConfig、RuntimeMode
- Provides:
  - 统一的日志初始化接口，供应用启动流程调用
  - 命名 logger 获取函数，供所有业务模块使用

## Non-functional Requirements
- Performance: 日志初始化为启动时一次性操作；运行时日志写入为标准库 logging 行为，无额外开销
- Security: 日志系统本身不记录敏感信息；敏感信息的脱敏由调用方负责（参考 config-security.md 日志脱敏规范）
- Compatibility:
  - 支持 Windows、macOS、Linux 三平台
  - 使用 Python 标准库 logging，无额外依赖
  - 日志目录路径跟随 AppConfig.data_dir，兼容 Docker 挂载卷（/app/data/logs/）

## Skills Evaluation
- Searched: Python 日志库（loguru、structlog、标准库 logging）
- Found:
  - **loguru**: 第三方日志库，API 简洁，自带轮转和格式化，但引入额外依赖
  - **structlog**: 结构化日志库，适合复杂微服务场景，对本项目过重
  - **标准库 logging**: Python 内置，零依赖，RotatingFileHandler 原生支持，生态兼容性最佳
- Decision: 使用标准库 logging（direct-use）。项目日志需求明确（轮转文件 + 可选 stdout），标准库完全满足，无需引入第三方依赖。保持依赖最小化原则

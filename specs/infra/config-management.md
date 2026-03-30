# Feature: 配置管理系统

## User Story
As a Stock-ARM 用户（开发者或终端用户），I want 一个统一的配置管理系统，能够从多个来源（环境变量、.env 文件、config.yaml、代码默认值）按优先级加载配置，并根据运行环境自动调整行为，so that 我无需手动修改代码即可在不同部署模式（本地、云端、Docker）下灵活运行应用。

## Acceptance Criteria
- [ ] AC-1: 配置按优先级链加载——环境变量 > .env 文件 > config.yaml > 代码默认值，高优先级来源的值覆盖低优先级来源
- [ ] AC-2: 所有配置项通过 Pydantic 模型定义和校验，跨模块边界不使用原始字典
- [ ] AC-3: 环境变量命名遵循 `STOCK_ARM_<CATEGORY>_<NAME>` 格式（分区包括 LLM、DATA、PUSH、DB、NET、UI、AUTH、SCHEDULER、BACKUP）
- [ ] AC-4: 秘密信息（API Key、密码等）仅能通过环境变量或 .env 文件加载，不会出现在 config.yaml 中，且在日志中自动脱敏
- [ ] AC-5: 运行时模式检测——根据环境变量或系统特征自动识别运行模式（auto/cloud/docker/local），并据此设置绑定地址、日志输出、浏览器行为等默认值
- [ ] AC-6: 配置分区独立可访问——各业务模块可独立获取自己分区的配置（如 LLM 模块获取 LLM 配置、调度器获取 Scheduler 配置），无需加载全量配置
- [ ] AC-7: 必填项校验——缺少必填配置项（如 LLM API Key）时，启动阶段即报告清晰的错误信息，指明缺失项和如何配置
- [ ] AC-8: 提供 `.env.example` 模板文件，包含所有配置项的说明、默认值、是否必填、格式示例
- [ ] AC-9: 配置加载失败（文件格式错误、类型不匹配等）时，提供人类可读的错误信息，包含出错位置和修正建议
- [ ] AC-10: 配置系统作为 Layer 1 基础设施模块，不依赖项目中其他模块，可独立初始化和测试

## Data Flow
Input: 环境变量（系统环境 + .env 文件）、config.yaml 文件、代码内置默认值、运行时环境特征（文件系统标记如 /.dockerenv）
Processing:
  1. 检测运行时模式（auto/cloud/docker/local）
  2. 加载代码默认值作为基础配置
  3. 叠加 config.yaml 中的用户配置
  4. 叠加 .env 文件中的键值对
  5. 叠加系统环境变量
  6. 根据运行时模式应用模式特定默认值（如绑定地址、日志目标）
  7. 通过 Pydantic 模型校验完整配置
  8. 对秘密字段标记脱敏属性
Output: 经过校验的、类型安全的配置对象，各分区可独立访问

## API Contract
- 内部 Python API（非 HTTP 接口）：
  - 获取完整配置：返回经校验的配置对象
  - 获取分区配置：按分区名获取子配置（如 LLM、Scheduler 等）
  - 获取运行时模式：返回当前检测到的运行模式枚举值
  - 配置项类型：所有配置项通过 Pydantic 模型定义，包含类型、默认值、校验规则、字段描述

## Dependencies
- Requires: 无（Layer 1 基础设施，零外部模块依赖）
- Provides:
  - 统一配置访问接口，供所有上层模块使用
  - 运行时模式信息，供启动流程和调度器使用
  - 秘密字段脱敏能力，供日志模块使用
  - 配置分区模型定义，供各业务模块按需引用

## Non-functional Requirements
- Performance: 配置加载为启动时一次性操作，加载耗时应 < 100ms；运行时访问配置为内存读取，无 I/O 开销
- Security:
  - 秘密字段在日志输出中自动脱敏（仅显示末尾 4 字符或完全隐藏）
  - .env 文件在 .gitignore 中，永不提交到版本库
  - config.yaml 不存放任何秘密信息
  - 配置对象的秘密字段在序列化（如返回给前端）时自动隐藏
- Compatibility:
  - 支持 Windows、macOS、Linux 三平台
  - 支持 Python 3.11+
  - Docker 环境下的路径约定（/app/data 等）需兼容
  - config.yaml 不存在时不报错，使用默认值正常启动

## Skills Evaluation
- Searched: Python 配置管理库（pydantic-settings、python-dotenv、dynaconf、hydra）
- Found:
  - **pydantic-settings**: Pydantic 官方配置扩展，原生支持环境变量加载、.env 文件解析、嵌套模型、字段校验，与项目已有的 Pydantic 技术栈完全一致
  - **python-dotenv**: 轻量 .env 文件解析库，pydantic-settings 内部已集成
  - **PyYAML**: YAML 文件解析，Python 生态标准库
- Decision: 使用 pydantic-settings 作为核心配置框架（direct-use），它天然支持环境变量优先级、.env 加载、类型校验，与项目 Pydantic 模型约定一致。PyYAML 用于 config.yaml 解析。不使用 dynaconf/hydra，因为项目配置结构明确，不需要其复杂的环境切换和组合功能

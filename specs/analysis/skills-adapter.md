# Feature: Skills 适配器层

## User Story
作为一名个人投资者，我希望系统提供统一的技能集成框架，以便日后接入外部分析工具（如量化策略、技术指标库）时有标准化的适配接口，减少重复开发。

## Acceptance Criteria
- [ ] AC-1: 提供 BaseSkillAdapter 抽象基类，包含 skill_name、skill_source 属性和 execute、health_check 方法
- [ ] AC-2: SkillRegistry 能从 skills/registry.yaml 加载已评估的技能列表
- [ ] AC-3: SkillRegistry 支持按 category 过滤和按 name 查找技能
- [ ] AC-4: YAML 策略加载器能解析 skills/*.yaml 策略定义文件并返回结构化数据
- [ ] AC-5: 策略定义包含 name、description、version、category、trigger、input、output、implementation 字段
- [ ] AC-6: 所有模型使用 Pydantic BaseModel，不使用原始 dict
- [ ] AC-7: BaseSkillAdapter 适配器代码不超过 200 行

## Data Flow
Input: skills/registry.yaml（技能注册表）、skills/*.yaml（策略定义文件）
Processing: YAML 解析 -> Pydantic 模型校验 -> 注册到内存索引
Output: 类型安全的技能条目和策略定义对象，供上层分析模块调用

## API Contract
本模块为内部 Python 模块，不直接暴露 HTTP API。对外接口为 Python 类与方法：
- `SkillRegistry.load() -> None` — 加载 registry.yaml
- `SkillRegistry.get_skills(category: str) -> list[SkillEntry]` — 按分类获取技能列表
- `SkillRegistry.get_skill(name: str) -> SkillEntry | None` — 按名称获取单个技能
- `load_strategy(path: Path) -> StrategyDefinition` — 加载 YAML 策略定义

## Dependencies
- Requires: config 模块（ConfigManager）、log 模块（get_logger）、PyYAML
- Provides: BaseSkillAdapter ABC、SkillRegistry、StrategyDefinition 模型，供 Layer 3 分析模块和 Layer 4 业务模块使用

## Non-functional Requirements
- Performance: registry.yaml 加载应在 100ms 内完成（文件通常 <100 条记录）
- Security: 不执行 YAML 中的任意代码，使用 yaml.safe_load
- Compatibility: 纯 Python 实现，无平台特定依赖

## Skills Evaluation
- Searched: PyPI 上的 skill/plugin 框架（pluggy、stevedore）
- Found: pluggy（pytest 插件系统）、stevedore（OpenStack 插件加载器）
- Decision: Ignore — 本项目需求简单（YAML 驱动的注册表 + ABC），引入插件框架属于过度工程化。直接实现轻量级方案。

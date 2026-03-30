# Feature: 宏观数据追踪

## User Story
作为个人投资者，我希望系统每日自动拉取核心宏观经济指标（CPI/PPI/M1/M2/LPR/Shibor/国债收益率/融资余额/北向资金/商品价格），与前值比较后通过 LLM 分析其含义和市场影响，从而帮助我快速掌握宏观环境变化。

## Acceptance Criteria
- [ ] AC-1: 定义 MacroIndicator（Pydantic 模型），包含字段：name、category、value、prev_value、unit、updated_at、source、change、change_pct
- [ ] AC-2: 定义 MacroRecord（SQLAlchemy ORM 模型），包含字段：indicator_name、current_value、previous_value、change、change_pct、unit、source、updated_at，继承 TimestampMixin
- [ ] AC-3: 预定义指标列表（indicators.py），每个指标包含名称、类别、AkShare API 名称、更新频率、单位
- [ ] AC-4: MacroTracker.pull_daily_indicators() 使用 AkShare API（通过 asyncio.to_thread）拉取当日指标数据，返回 list[MacroIndicator]
- [ ] AC-5: 拉取后与数据库中前值比较，计算 change 和 change_pct，只存储最新值+前值（不存完整历史）
- [ ] AC-6: MacroTracker.analyze(indicators) 调用 LLM 分析宏观数据含义和市场影响，返回分析文本
- [ ] AC-7: 当日无更新的指标标注"暂无更新"及最近可用日期和值
- [ ] AC-8: 单个指标拉取失败不影响其他指标，记录错误日志继续处理
- [ ] AC-9: 注册为 daily_macro 调度任务（18:30），通过调度器系统集成

## Data Flow
Input: 预定义的宏观指标列表 + AkShare 数据接口
Processing:
  1. MacroTracker 遍历预定义指标列表
  2. 对每个指标调用对应的 AkShare API 获取最新值
  3. 从数据库读取该指标前值，计算变化量和变化率
  4. 更新数据库记录（只保留最新值+前值）
  5. 将所有指标汇总，调用 LLM 分析整体宏观含义
Output: list[MacroIndicator] + LLM 分析文本

## API Contract
本模块为内部 Python API，不直接暴露 HTTP 接口：
- `MacroTracker.pull_daily_indicators() -> list[MacroIndicator]`
- `MacroTracker.analyze(indicators: list[MacroIndicator]) -> str`
- `MacroTracker.run_daily() -> tuple[list[MacroIndicator], str]` — 一键执行拉取+分析

## Dependencies
- Requires: db（数据库引擎和 ORM 基类）、log（日志记录）、analysis.llm（LLM 调用）、analysis.llm.prompt_manager（Prompt 模板）
- Provides: 宏观数据追踪能力，供调度器 daily_macro 任务和未来 API/通知模块使用

## Non-functional Requirements
- Performance: 全部指标拉取 < 60s，单指标超时 10s
- Security: 无敏感数据，所有配置通过配置系统
- Compatibility: AkShare 为可选依赖，未安装时优雅降级

## Skills Evaluation
- Searched: AkShare 宏观数据接口
- Found: AkShare 已集成在数据层，提供 CPI/PPI/M1/M2/LPR/Shibor/国债收益率等宏观数据 API
- Decision: 直接使用 AkShare，通过 asyncio.to_thread 包装同步调用

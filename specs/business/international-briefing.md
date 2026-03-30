# Feature: 国际金融简报

## User Story
作为个人投资者，我希望每天能收到一份国际金融简报，包含隔夜市场表现、重大事件影响分析和未来7天全球金融日程，以便在A股开盘前了解全球市场动态并调整投资策略。

## Acceptance Criteria
- [ ] AC-1: 定义 BriefingResult（Pydantic BaseModel），包含日期、市场概况、事件分析、未来日程、LLM 生成的 Markdown 简报正文
- [ ] AC-2: 实现 InternationalBriefingGenerator 类，提供 `async generate(date) -> BriefingResult` 方法
- [ ] AC-3: 通过 IntlDataManager 获取主要国际指数（道琼斯、标普500、纳斯达克、恒生、恒生科技）行情数据
- [ ] AC-4: 通过 NewsManager 获取国际金融相关新闻
- [ ] AC-5: 调用 LLMRouter 生成包含隔夜市场、事件影响、未来日程三部分的中文简报
- [ ] AC-6: 简报输出为 Markdown 格式
- [ ] AC-7: 注册为 daily_briefing 调度任务（默认 19:00）

## Data Flow
Input: 日期参数（默认当天）
Processing:
  1. InternationalBriefingGenerator 接收生成请求
  2. 调用 IntlDataManager.get_market_indices() 获取国际指数数据
  3. 调用 NewsManager.search() 获取国际金融新闻
  4. 组装上下文，调用 LLMRouter 生成简报
  5. 解析 LLM 输出，组装 BriefingResult 返回
Output: BriefingResult

## API Contract
本模块为内部 Python API：
- `InternationalBriefingGenerator.generate(date: date | None) -> BriefingResult`

## Dependencies
- Requires: data.international（IntlDataManager 国际指数数据）、data.news（NewsManager 新闻数据）、analysis.llm（LLMRouter LLM调用）、log（日志）
- Provides: 国际金融简报，供通知模块和 API 层使用

## Non-functional Requirements
- Performance: 单次生成超时 < 30s
- Security: 无外部凭证暴露
- Reliability: 数据源不可用时降级为"数据不可用"而非报错

## Skills Evaluation
- Searched: 国际金融日程数据源
- Found: 国际指数数据通过现有 IntlDataManager 获取
- Decision: 复用已有数据管理器，LLM 负责事件分析和日程整理

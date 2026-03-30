# Feature: 研报管理

## User Story
作为个人投资者，我希望系统能帮我筛选和摘要券商研报，提取核心观点、目标价、逻辑链和风险提示，并追踪评级变化，以便快速把握研究机构对个股和行业的判断。

## Acceptance Criteria
- [ ] AC-1: 定义 ResearchReportSummary（Pydantic BaseModel），包含标题、来源、股票代码、行业、评级、目标价、核心观点、逻辑链、风险提示、LLM 摘要等字段
- [ ] AC-2: 实现 ReportManager 类，提供 `async search_reports(filters) -> list[ResearchReportSummary]` 方法
- [ ] AC-3: 实现 `async summarize(report_url) -> ResearchReportSummary` 方法，通过 LLM 生成研报摘要
- [ ] AC-4: 支持按行业、个股、评级筛选研报
- [ ] AC-5: 追踪评级变化（上调/下调/维持）
- [ ] AC-6: LLM 摘要提取：核心观点、目标价、逻辑链、风险提示
- [ ] AC-7: 单条研报处理失败不阻塞其他研报

## Data Flow
Input: 筛选条件（行业/个股/评级）或研报 URL
Processing:
  1. ReportManager 接收筛选或摘要请求
  2. search_reports: 从新闻源获取研报列表，按条件筛选
  3. summarize: 获取研报内容，调用 LLMRouter 生成结构化摘要
  4. 组装 ResearchReportSummary 返回
Output: list[ResearchReportSummary] 或单个 ResearchReportSummary

## API Contract
本模块为内部 Python API：
- `ReportManager.search_reports(filters: ReportFilter) -> list[ResearchReportSummary]`
- `ReportManager.summarize(report_url: str) -> ResearchReportSummary`

## Dependencies
- Requires: data.news（NewsManager 研报来源）、analysis.llm（LLMRouter LLM调用）、log（日志）
- Provides: 研报摘要数据，供通知模块和 API 层使用

## Non-functional Requirements
- Performance: 单条研报摘要 < 30s
- Security: 无外部凭证暴露
- Reliability: 单条研报失败不阻塞批量处理

## Skills Evaluation
- Searched: 研报数据源接口
- Found: 可通过新闻源获取研报发布信息
- Decision: 复用 NewsManager 搜索研报，LLM 负责摘要提取

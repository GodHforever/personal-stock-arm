# Feature: 财报处理

## User Story
作为个人投资者，我希望系统能在财报季（4/8/10月）自动扫描新发布的财报，通过 LLM 生成包含营收、净利润、毛利率等关键指标的摘要，以便快速了解关注个股的财务状况变化。

## Acceptance Criteria
- [ ] AC-1: 定义 EarningsSummary（Pydantic BaseModel），包含股票代码、公司名称、报告期、营收、净利润、毛利率、净利率、同比变化、LLM 摘要等字段
- [ ] AC-2: 实现 EarningsProcessor 类，提供 `async scan_reports(scope) -> list[EarningsSummary]` 方法
- [ ] AC-3: scope 参数支持 "watchlist"（自选股）和 "all"（全部）两种范围
- [ ] AC-4: 通过 LLMRouter 调用 LLM 生成财报摘要（营收、净利润、毛利率等关键指标）
- [ ] AC-5: 摘要输出为 Markdown 格式
- [ ] AC-6: 注册为 earnings_scan 调度任务（默认 20:00，财报季执行）
- [ ] AC-7: 所有外部调用（数据源、LLM）有错误处理，单只股票失败不阻塞其他股票

## Data Flow
Input: 扫描范围（watchlist/all）
Processing:
  1. EarningsProcessor 接收扫描请求
  2. 根据 scope 确定待扫描股票列表
  3. 从数据源获取各股票最新财报数据
  4. 调用 LLMRouter 生成中文摘要
  5. 组装 EarningsSummary 对象返回
Output: list[EarningsSummary]

## API Contract
本模块为内部 Python API，不直接暴露 HTTP 接口。供上层调用：
- `EarningsProcessor.scan_reports(scope: str) -> list[EarningsSummary]`
- `EarningsProcessor.summarize_single(code: str) -> EarningsSummary`

## Dependencies
- Requires: analysis.llm（LLMRouter LLM调用）、data.a_share（A股数据源）、data.news（新闻数据）、log（日志）、config（配置）
- Provides: 财报摘要数据，供通知模块和 API 层使用

## Non-functional Requirements
- Performance: 单次扫描超时 < 60s，LLM 调用使用 fast_model 降低延迟
- Security: 无外部凭证暴露，所有配置通过 ConfigManager 获取
- Reliability: 单股票处理失败不阻塞其他股票，记录错误日志继续处理

## Skills Evaluation
- Searched: akshare 财报接口、tushare 财务数据接口
- Found: akshare 提供 stock_financial_report_sina 等接口获取财报数据
- Decision: 通过现有 A股数据管理器获取数据，LLM 生成摘要

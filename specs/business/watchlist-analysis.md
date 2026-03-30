# Feature: 自选股管理与每日分析

## User Story
作为一名 A 股投资者，我希望能够管理自选股分组并每日自动获取综合分析报告（技术面+基本面+新闻+LLM综合判断），以便快速掌握持仓和关注股票的最新状态及操作建议。

## Acceptance Criteria
- [ ] AC-1: 可以创建、删除、查询自选股分组，每个分组包含名称、描述、分析策略、推送频率、股票列表
- [ ] AC-2: 可以向分组中添加和移除股票代码
- [ ] AC-3: 对单只股票执行分析 pipeline，产出 StockAnalysisResult 结构化结果
- [ ] AC-4: StockAnalysisResult 包含技术面摘要、基本面数据、新闻摘要、LLM 综合判断（LLMVerdict: signal/confidence/reasoning/risk_alerts）
- [ ] AC-5: 可以对整个分组批量分析，返回 list[StockAnalysisResult]
- [ ] AC-6: 分析结果持久化到 analysis_record 数据库表
- [ ] AC-7: 注册为 daily_analysis 调度任务（18:00 触发）
- [ ] AC-8: 所有外部调用（数据源、新闻、LLM）失败时降级处理，不阻塞其他股票分析

## Data Flow
Input: 自选股分组名称 或 单个股票代码
Processing:
  1. 从 WatchlistGroup 获取股票列表
  2. 对每只股票并行执行: 获取K线 → 技术分析 → 获取基本面 → 获取新闻 → 组装 prompt → LLM 综合判断
  3. 汇总为 StockAnalysisResult，持久化到 AnalysisRecord
Output: list[StockAnalysisResult] 结构化分析报告

## API Contract
（本 Sprint 为 business 层，暂不暴露 REST API，后续 Sprint 添加 API 路由）

## Dependencies
- Requires: config, log, db (Layer 1), network (Layer 2), data.a_share, data.news, analysis.technical, analysis.llm (Layer 3)
- Provides: business.watchlist (WatchlistManager, StockAnalysisPipeline) — 供上层 API 和调度器使用

## Non-functional Requirements
- Performance: 单组分析（≤20只股票）应在 5 分钟内完成
- Security: 不存储原始 API Key，分析结果中不包含敏感信息
- Compatibility: 支持 SQLite WAL 模式下并发读写

## Skills Evaluation
- Searched: 自选股管理、股票分析 pipeline
- Found: 无直接可复用的外部 skill
- Decision: 使用项目已有的 DataFetcherManager、TechnicalAnalyzer、NewsManager、LiteLLMRouter 组合实现

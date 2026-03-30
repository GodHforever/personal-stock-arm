# Feature: 新闻/情绪数据适配器

## User Story
作为个人投资者，我希望系统能从多个新闻源（Longbridge、RSS财经媒体）自动获取与个股或市场相关的新闻信息，当某个新闻源不可用时自动跳过而不阻塞主流程，从而为后续的情绪分析和投资决策提供数据支撑。

## Acceptance Criteria
- [ ] AC-1: 定义统一的新闻数据模型 NewsItem（Pydantic BaseModel），包含 title、source、url、summary、published_at、sentiment 等字段
- [ ] AC-2: 定义 BaseNewsSource 抽象基类，包含 search（关键词搜索）和 get_stock_news（个股新闻）两个异步方法，以及 source_name、requires_token 元数据属性
- [ ] AC-3: 实现 Longbridge 新闻适配器，通过 longbridge SDK 的 ContentContext 获取新闻和讨论，无 SDK 或无凭证时 is_available 返回 False
- [ ] AC-4: 实现 RSS 新闻源适配器，支持预定义的主流财经媒体 RSS 地址（财联社、华尔街见闻等），使用 httpx + XML 解析
- [ ] AC-5: 实现 NewsManager 聚合多源新闻，遍历所有可用源收集新闻，单个源失败不阻塞其他源
- [ ] AC-6: NewsManager 支持按时间排序、去重（基于 URL）
- [ ] AC-7: 定义 AntiScrapeConfig 数据类，包含请求间隔、UA 池、指数退避等参数，为未来爬虫扩展预留
- [ ] AC-8: 每个新闻源失败时产生结构化错误日志（复用 DataSourceError），不抛出异常到上层

## Data Flow
Input: 查询关键词或股票代码、返回数量限制
Processing:
  1. NewsManager 接收请求
  2. 遍历所有已注册且可用的新闻源
  3. 并发调用各源的 search 或 get_stock_news 方法
  4. 合并结果，按 published_at 排序，按 URL 去重
  5. 单个源失败时记录日志，继续处理其他源的结果
Output: list[NewsItem] 统一新闻数据模型列表

## API Contract
本模块为内部 Python API，不直接暴露 HTTP 接口。供上层业务模块调用：
- `NewsManager.search(query: str, limit: int) -> list[NewsItem]`
- `NewsManager.get_stock_news(code: str, limit: int) -> list[NewsItem]`
- `NewsManager.get_stats() -> dict[str, dict[str, int]]`

## Dependencies
- Requires: config（获取 Longbridge 凭证等配置）、log（日志记录）、network.client（NetworkClient HTTP 请求）、network.errors（DataSourceError）
- Provides: 统一的新闻数据获取接口，供 Layer 3（LLM 情绪分析）和 Layer 4（业务模块）使用

## Non-functional Requirements
- Performance: 多源并发获取，单次请求总超时 < 15s；RSS 解析使用标准库 xml.etree.ElementTree
- Security: Longbridge 凭证通过配置系统获取，不硬编码；RSS 地址硬编码在代码中（公开信息）
- Compatibility: longbridge SDK 为可选依赖，未安装时该源标记为不可用；RSS 仅依赖 httpx + 标准库
- Reliability: 任何单个新闻源失败不阻塞主流程，降级为"该源数据不可用"

## Skills Evaluation
- Searched: longbridge Python SDK（新闻/讨论接口）、feedparser（RSS解析库）、中文财经RSS源
- Found: longbridge SDK 提供 ContentContext.news() 和 ContentContext.topics() 接口；feedparser 是成熟的 RSS 解析库但引入额外依赖
- Decision: Longbridge 直接使用 SDK 适配器；RSS 解析使用标准库 xml.etree.ElementTree（避免额外依赖），不引入 feedparser

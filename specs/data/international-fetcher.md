# Feature: 国际市场数据适配器

## User Story
作为个人投资者，我希望系统能获取美股、港股、新加坡等国际市场的实时行情和K线数据，当主数据源（Longbridge）不可用时自动切换到备用源（yfinance），从而实现多市场投资分析能力。

## Acceptance Criteria
- [ ] AC-1: 定义国际市场统一数据模型 IntlQuote、IntlKlineBar（Pydantic BaseModel），复用A股模型结构并扩展 market、currency 等国际市场字段
- [ ] AC-2: 定义 BaseIntlFetcher 抽象基类，包含 get_quote、get_kline、get_market_indices 三个异步方法及 source_name、priority、supported_markets 元数据属性
- [ ] AC-3: 实现 Longbridge 适配器（priority=0），使用 AsyncQuoteContext 获取 US/HK/SG 市场数据，OpenApiException 映射为 DataSourceError
- [ ] AC-4: 实现 yfinance 适配器（priority=1），仅支持 US 市场历史数据，同步库通过 asyncio.to_thread 包装为 async
- [ ] AC-5: 实现 IntlDataManager，按优先级自动 failover，支持 get_quote、get_kline、get_market_indices 三个接口
- [ ] AC-6: 支持 CODE.MARKET 格式的 symbol（如 AAPL.US、700.HK、D05.SG）
- [ ] AC-7: get_market_indices 返回主要国际指数（道琼斯、标普500、纳斯达克、恒生、恒生科技）的行情数据
- [ ] AC-8: Rate limit 控制：Longbridge 适配器限制每秒最多 10 次调用
- [ ] AC-9: 全部数据源失败时返回 DataUnavailableError 异常，不崩溃，附带结构化错误报告

## Data Flow
Input: 国际市场股票代码（如 "AAPL.US"、"700.HK"）、请求类型（行情/K线/指数）、可选参数（K线周期、数量）
Processing:
  1. IntlDataManager 接收请求
  2. 验证 symbol 格式（CODE.MARKET）
  3. 按优先级遍历支持该市场的已注册数据源
  4. 调用当前优先级最高的数据源适配器
  5. 成功则返回统一数据模型；失败则记录错误，尝试下一个
  6. 全部失败则抛出 DataUnavailableError
Output: IntlQuote / list[IntlKlineBar] / list[IntlQuote] 统一数据模型

## API Contract
本模块为内部 Python API，不直接暴露 HTTP 接口。供上层业务模块调用：
- `IntlDataManager.get_quote(symbol: str) -> IntlQuote`
- `IntlDataManager.get_kline(symbol: str, period: str, count: int) -> list[IntlKlineBar]`
- `IntlDataManager.get_market_indices() -> list[IntlQuote]`

## Dependencies
- Requires: config（获取 Longbridge OAuth client_id 等配置）、log（日志记录）、network.errors（DataSourceError）
- Provides: 统一的国际市场数据获取接口，供 Layer 3（分析引擎）和 Layer 4（业务模块）使用

## Non-functional Requirements
- Performance: 单次数据获取响应 < 10s（含 failover），Longbridge 限流 10 calls/second
- Security: Longbridge OAuth 认证由 SDK 自动管理，client_id 通过配置系统获取，不硬编码
- Compatibility: Longbridge 和 yfinance 为可选依赖，import 失败时优雅降级（该源标记为不可用）

## Skills Evaluation
- Searched: Longbridge Python SDK（行情数据）、yfinance（美股数据）
- Found: longbridge 包提供 AsyncQuoteContext 支持 US/HK/SG 市场；yfinance 支持全球市场历史数据
- Decision: Longbridge 为主数据源（实时+历史），yfinance 为 US 市场 fallback（历史数据）

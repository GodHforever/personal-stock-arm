# Feature: A股数据源适配器

## User Story
作为个人投资者，我希望系统能从多个A股数据源自动获取实时行情、K线和基本面数据，当某个数据源不可用时自动切换到备用源，从而保证数据获取的连续性和可靠性。

## Acceptance Criteria
- [ ] AC-1: 定义统一的数据模型 StockQuote、KlineBar、Fundamentals（Pydantic BaseModel），字段覆盖行情、K线、基本面核心数据
- [ ] AC-2: 定义 BaseDataFetcher 抽象基类，包含 get_realtime_quote、get_kline、get_fundamentals 三个异步方法及 source_name、priority、requires_token 元数据属性
- [ ] AC-3: 实现 efinance 适配器（priority=0，无需 token），包装同步库为 async
- [ ] AC-4: 实现 AkShare 适配器（priority=1，无需 token），包装同步库为 async
- [ ] AC-5: 实现 Tushare 适配器（priority=0，需 token），无 token 时 is_available 返回 False
- [ ] AC-6: 实现 Baostock 适配器（priority=3，无需 token），处理 login/logout 生命周期
- [ ] AC-7: 实现 DataFetcherManager，按优先级自动 failover，记录各源成功/失败计数
- [ ] AC-8: 全部数据源失败时返回 DataUnavailable 异常，不崩溃，附带结构化错误报告
- [ ] AC-9: 每个数据源失败时产生结构化错误日志（复用 DataSourceError）

## Data Flow
Input: 股票代码（如 "000001"）、请求类型（行情/K线/基本面）、可选参数（K线周期、数量）
Processing:
  1. DataFetcherManager 接收请求
  2. 按优先级遍历已注册的可用数据源
  3. 调用当前优先级最高的数据源适配器
  4. 成功则返回统一数据模型；失败则记录错误，尝试下一个
  5. 全部失败则抛出 DataUnavailable
Output: StockQuote / list[KlineBar] / Fundamentals 统一数据模型

## API Contract
本模块为内部 Python API，不直接暴露 HTTP 接口。供上层业务模块调用：
- `DataFetcherManager.get_realtime_quote(code: str) -> StockQuote`
- `DataFetcherManager.get_kline(code: str, period: str, count: int) -> list[KlineBar]`
- `DataFetcherManager.get_fundamentals(code: str) -> Fundamentals`

## Dependencies
- Requires: config（获取 tushare_token、timeout 等配置）、log（日志记录）、network.errors（DataSourceError）
- Provides: 统一的A股数据获取接口，供 Layer 3（分析引擎）和 Layer 4（业务模块）使用

## Non-functional Requirements
- Performance: 单次数据获取响应 < 10s（含 failover），同步库调用通过 asyncio.to_thread 避免阻塞事件循环
- Security: Tushare token 通过配置系统获取（环境变量/配置文件），不硬编码
- Compatibility: 所有数据源库为可选依赖，import 失败时优雅降级（该源标记为不可用）

## Skills Evaluation
- Searched: efinance, akshare, tushare, baostock Python 数据源库
- Found: 均为成熟的开源 A 股数据获取库，直接 pip install 使用
- Decision: 直接使用，每个库编写独立适配器，通过 BaseDataFetcher 抽象统一接口

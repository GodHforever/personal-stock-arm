# Feature: 网络请求层 (NetworkClient)

## User Story
As a Stock-ARM 数据模块开发者，I want 一个统一的 HTTP 客户端封装层，提供自动超时、指数退避重试、代理支持和结构化异常，so that 所有数据源适配器可以通过一致的接口发起网络请求，而无需各自处理重试、超时和错误格式化逻辑。

## Acceptance Criteria
- [ ] AC-1: 提供 `DataSourceError` 结构化异常类，包含 step、source、url、error_type、error_msg、suggestion 字段
- [ ] AC-2: `DataSourceError.to_dict()` 返回包含所有字段的字典
- [ ] AC-3: `DataSourceError.__str__()` 返回中文可读的错误描述
- [ ] AC-4: 提供 `NetworkClient` 类，内部封装 `httpx.AsyncClient`
- [ ] AC-5: `NetworkClient` 支持 `async get(url, **kwargs)` 和 `async post(url, **kwargs)` 方法，返回 `httpx.Response`
- [ ] AC-6: 超时配置从 `DataConfig` 读取，默认 connect=5s、read=30s
- [ ] AC-7: 请求失败时自动重试，使用指数退避策略（基础间隔 1s，倍数 2，即 1s、2s、4s），最大重试次数从 `DataConfig.max_retries` 读取（默认 3 次）
- [ ] AC-8: 代理配置从 `NetworkConfig.proxy` 读取，非空时自动应用
- [ ] AC-9: 所有网络异常（超时、连接错误、HTTP 错误状态码）均转换为 `DataSourceError` 并抛出
- [ ] AC-10: `NetworkClient` 支持作为异步上下文管理器使用（`async with`），自动管理底层连接生命周期

## Data Flow
Input: URL、请求参数、配置（超时、重试、代理）
Processing:
  1. 从 ConfigManager 获取 DataConfig（超时、重试次数）和 NetworkConfig（代理）
  2. 创建 httpx.AsyncClient 并配置超时和代理
  3. 发起 HTTP 请求
  4. 请求失败时按指数退避策略重试（1s → 2s → 4s）
  5. 超过最大重试次数后，将异常转换为 DataSourceError 抛出
  6. 请求成功时返回 httpx.Response
Output: httpx.Response 对象或 DataSourceError 异常

## API Contract
- 内部 Python API（非 HTTP 接口）：
  - `DataSourceError(step, source, url, error_type, error_msg, suggestion)` — 结构化数据源异常
  - `DataSourceError.to_dict() -> dict` — 序列化为字典
  - `NetworkClient(source_name: str)` — 创建命名客户端实例
  - `await client.get(url, **kwargs) -> httpx.Response` — GET 请求，自动重试
  - `await client.post(url, **kwargs) -> httpx.Response` — POST 请求，自动重试
  - `async with NetworkClient(source_name) as client:` — 上下文管理器用法

## Dependencies
- Requires:
  - `src/config` 模块（Layer 1，已合并）— 提供 ConfigManager、DataConfig、NetworkConfig
  - `src/log` 模块（Layer 1，已合并）— 提供 get_logger
  - `httpx` 第三方库 — 异步 HTTP 客户端
- Provides:
  - 统一的 HTTP 请求客户端，供所有数据源适配器使用
  - 结构化异常类型，供上层模块统一处理网络错误

## Non-functional Requirements
- Performance: 连接复用通过 httpx.AsyncClient 连接池实现；重试间隔不超过 4s，不会阻塞过长
- Security: 代理地址和 SSL 配置通过配置系统加载，不硬编码；SSL 验证默认开启（遵循 NetworkConfig.ssl_verify）
- Compatibility: 支持 HTTP/HTTPS 协议；httpx 跨平台兼容 Windows/macOS/Linux

## Skills Evaluation
- Searched: Python 异步 HTTP 客户端库（httpx、aiohttp、requests-async）、重试库（tenacity、stamina、backoff）
- Found:
  - **httpx**: 现代异步 HTTP 客户端，API 与 requests 兼容，原生支持 async/await、连接池、代理、超时配置
  - **aiohttp**: 功能完善但 API 风格与 requests 差异大，学习成本略高
  - **tenacity**: 通用重试库，功能强大但对本场景（简单指数退避）而言过重
- Decision: 使用 httpx（direct-use），重试逻辑内置实现。httpx 已在 requirements.txt 中声明，API 简洁且原生支持异步。重试逻辑仅需简单的指数退避循环，无需引入 tenacity 等额外依赖

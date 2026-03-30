# Feature: FastAPI 后端 API 层

## User Story
As a Stock-ARM 前端开发者和用户，I want 一套统一的 RESTful API 接口，提供自选股管理、分析触发、宏观数据查询、国际简报和财报摘要等功能，so that 前端 Web 应用可以通过标准 HTTP 接口与后端交互。

## Acceptance Criteria
- [ ] AC-1: 提供统一响应模型 `ApiResponse[T]`，包含 code(int)、data(T|None)、message(str) 字段
- [ ] AC-2: 提供分页响应模型 `PaginatedData[T]`，包含 items、total、page、page_size、total_pages 字段
- [ ] AC-3: 提供 `ErrorCodes` 枚举，涵盖 1xxx(客户端)、2xxx(数据源)、3xxx(LLM)、4xxx(系统) 错误码
- [ ] AC-4: `GET /api/v1/health` 返回健康状态
- [ ] AC-5: `GET/POST /api/v1/watchlists` 支持获取所有分组和创建分组
- [ ] AC-6: `GET/DELETE /api/v1/watchlists/{id}` 支持获取分组详情和删除分组
- [ ] AC-7: `POST /api/v1/watchlists/{id}/stocks` 和 `DELETE /api/v1/watchlists/{id}/stocks/{code}` 支持添加和移除股票
- [ ] AC-8: `POST /api/v1/analysis/run` 触发异步分析任务，返回 task_id
- [ ] AC-9: `GET /api/v1/analysis/tasks/{task_id}` 查询异步任务状态
- [ ] AC-10: `GET /api/v1/analysis/results` 支持分页获取分析结果
- [ ] AC-11: `GET /api/v1/macro` 返回宏观数据
- [ ] AC-12: `GET /api/v1/briefings` 返回国际简报列表
- [ ] AC-13: `GET /api/v1/earnings` 返回财报摘要列表
- [ ] AC-14: `GET /api/v1/reports` 返回研报摘要列表
- [ ] AC-15: 全局异常处理器捕获 DataSourceError、ConfigLoadError 等转换为统一 ApiResponse
- [ ] AC-16: 提供 `create_app()` 应用工厂函数，注册路由、中间件、异常处理器

## Data Flow
Input: HTTP 请求（前端或 API 客户端）
Processing:
  1. FastAPI 路由接收请求，校验参数
  2. 路由处理函数调用对应的业务层模块
  3. 业务层返回结果或抛出异常
  4. 异常处理器将异常转换为统一错误响应
  5. 成功结果包装为 ApiResponse 返回
Output: 统一格式的 JSON 响应

## API Contract
```
GET  /api/v1/health                          → ApiResponse[HealthData]
GET  /api/v1/watchlists                      → ApiResponse[list[WatchlistItem]]
POST /api/v1/watchlists                      → ApiResponse[WatchlistItem]
GET  /api/v1/watchlists/{id}                 → ApiResponse[WatchlistDetail]
DELETE /api/v1/watchlists/{id}               → ApiResponse[None]
POST /api/v1/watchlists/{id}/stocks          → ApiResponse[WatchlistDetail]
DELETE /api/v1/watchlists/{id}/stocks/{code} → ApiResponse[WatchlistDetail]
POST /api/v1/analysis/run                    → ApiResponse[TaskCreated]
GET  /api/v1/analysis/tasks/{task_id}        → ApiResponse[TaskStatus]
GET  /api/v1/analysis/results                → ApiResponse[PaginatedData[AnalysisResultItem]]
GET  /api/v1/macro                           → ApiResponse[MacroData]
GET  /api/v1/briefings                       → ApiResponse[list[BriefingItem]]
GET  /api/v1/earnings                        → ApiResponse[list[EarningsItem]]
GET  /api/v1/reports                         → ApiResponse[list[ReportItem]]
```

## Dependencies
- Requires:
  - `fastapi` — Web 框架
  - `pydantic` — 数据校验和序列化
  - `src/config` — ConfigManager、ConfigLoadError
  - `src/network/errors` — DataSourceError
- Provides:
  - RESTful API 接口供前端和外部客户端调用
  - `create_app()` 应用工厂函数

## Non-functional Requirements
- Performance: 异步处理所有请求，长时间任务使用异步任务机制
- Security: CORS 中间件配置，不暴露内部堆栈信息
- Compatibility: OpenAPI 自动文档生成（/docs）

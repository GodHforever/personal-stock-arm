## QA Evaluation Report

- **Feature Spec**: news-sentiment（新闻/情绪数据适配器）
- **Sprint Round**: 1
- **Overall Score**: 74/100
- **Verdict**: CONDITIONAL (60-79)

### Scoring Breakdown

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Functional Completeness | 30% | 75 | AC-1~AC-7 通过，AC-8 未复用 DataSourceError |
| Code Quality | 20% | 80 | 源码 ruff 零错误；测试文件有 2 个未使用导入和 1 个导入排序问题 |
| API Contract | 15% | 90 | 内部 Python API 契约完整，search/get_stock_news/get_stats 签名匹配 Spec |
| Error Handling | 15% | 60 | 异常被捕获但未转化为 DataSourceError；RSS feeds 串行获取无总超时控制 |
| Database | 10% | N/A (满分) | 模块不涉及数据库，无需评估 |
| Security | 10% | 90 | Longbridge 凭证通过环境变量获取，无硬编码；RSS 地址为公开信息 |

**加权总分**:
- Functional: 75 × 0.30 = 22.5
- Code Quality: 80 × 0.20 = 16.0
- API Contract: 90 × 0.15 = 13.5
- Error Handling: 60 × 0.15 = 9.0
- Database: 100 × 0.10 = 10.0
- Security: 90 × 0.10 = 9.0
- **Total = 80.0 → 但考虑到 AC-8 验收标准未完全满足，下调至 74**

### Zero-tolerance 检查

- [x] 无硬编码密钥
- [x] 无 SQL 注入风险
- [x] 无假测试（测试逻辑验证真实行为）
- [x] 无破坏性 API 变更
- [x] 无缺失的数据库迁移（模块不涉及数据库）

### Issues Found

#### [MUST FIX]

1. **AC-8 未满足：未复用 DataSourceError**
   - Spec 要求："每个新闻源失败时产生结构化错误日志（复用 DataSourceError），不抛出异常到上层"
   - 当前实现：`longbridge_news.py`（第 124、143 行）、`rss_source.py`（第 98 行）和 `manager.py`（第 228 行）均使用 `logger.warning` 记录纯文本，未构造 `DataSourceError` 实例
   - 修复方案：在捕获异常时创建 `DataSourceError` 实例，利用其结构化字段（source_name、operation、detail）记录日志。不需要抛出，但需要用 `DataSourceError` 封装后记录

2. **RSS feeds 串行获取，违反并发要求**
   - Spec 要求："多源并发获取，单次请求总超时 < 15s"
   - `rss_source.py` 第 81-83 行 `_fetch_all_feeds` 使用 `for` 循环串行获取每个 feed
   - 4 个默认 RSS 源串行获取时，最坏情况总耗时 = 4 × 单源超时，可能远超 15s
   - 修复方案：改为 `asyncio.gather` 并发获取所有 feeds

#### [SHOULD FIX]

3. **测试文件 lint 问题**
   - `tests/unit/data/test_news_source.py` 第 14 行：`import xml.etree.ElementTree as ET` 未使用（F401）
   - `tests/unit/data/test_news_source.py` 第 15 行：`timezone` 从 `datetime` 导入但未使用（F401）
   - `tests/unit/data/test_news_source.py` 第 12-26 行：导入块未排序（I001）

4. **NewsManager 无单源超时控制**
   - `manager.py` 的 `_fetch_single` 方法没有对单个源的调用设置超时
   - 如果某个源的 `search` 或 `get_stock_news` 方法长时间阻塞，会拖延整体并发获取
   - 建议在 `_fetch_single` 中使用 `asyncio.wait_for` 设置单源超时（如 10s）

#### [SUGGESTION]

5. **AntiScrapeConfig 定义但未在任何源中使用**
   - AC-7 要求定义 `AntiScrapeConfig` "为未来爬虫扩展预留"，已实现数据类
   - 但 `RssNewsSource` 和 `LongbridgeNewsSource` 均未引用此配置
   - 建议在模块文档或注释中明确说明预留用途和接入点，避免后续开发者遗忘

6. **UA 池硬编码在 manager.py 中**
   - `_USER_AGENTS` 列表（50+ 条 UA）占据约 50 行代码，建议移至独立文件或配置中
   - 当前实现可接受，但影响 `manager.py` 的可读性

7. **Longbridge search 返回空列表**
   - `longbridge_news.py` 第 78-80 行：`search` 方法直接返回空列表，因为 Longbridge 不支持关键词搜索
   - 这是合理的设计决策，但建议在 `is_available` 或元数据中标注 `supports_search = False`，方便上层判断

### 测试覆盖评估

Builder 提供了 54 个单元测试，覆盖了：
- NewsItem 数据模型创建（2 个测试）
- BaseNewsSource 抽象基类（4 个测试）
- RSS 解析（RSS 2.0、Atom、无效 XML、空 item）（7 个测试）
- 日期解析（RFC 2822、ISO 8601、边界值）（5 个测试）
- Longbridge 适配器（可用性检测 4 个、搜索 1 个、代码标准化 3 个、时间解析 3 个）（11 个测试）
- AntiScrapeConfig（6 个测试）
- NewsManager（聚合、去重、排序、故障隔离等）（13 个测试）
- 去重排序工具函数（5 个测试）

**测试质量评价**：
- 测试覆盖了所有主要路径和关键边界情况
- Mock 使用合理，未出现"测试 mock 本身"的问题
- 中文测试方法命名符合项目"中文优先"规范

**注意**：由于当前环境 Python 版本（3.8）与项目要求（3.11+）不匹配，未能实际运行测试。venv 中的 Python 3.11 二进制文件路径指向不存在的位置（`/p/personal-stock-arm/.venv/bin/python3.11`）。Sprint Report 声称 54/54 测试通过，代码审查未发现会导致测试失败的逻辑问题，暂且信任此结果。

### Paradigm 合规检查

- [x] `validate_paradigm.py --spec` 通过：Spec 包含全部 7 个必需章节
- [x] `validate_paradigm.py --sprint` 通过：Sprint Report 包含全部 7 个必需字段
- [x] 源码 ruff check 零错误
- [ ] mypy 检查未执行（环境限制）
- [x] 无硬编码密钥
- [x] Pydantic 模型用于模块边界数据传递

### Tests Added

由于环境限制（Python 3.8 无法运行 3.11+ 代码），QA 未添加额外集成/场景测试。以下为建议补充的测试场景：

1. **RSS 并发获取测试**（待 MUST FIX #2 修复后）：验证多个 feeds 确实并发获取
2. **单源超时测试**：模拟单源阻塞，验证不会拖延其他源
3. **DataSourceError 结构化日志测试**（待 MUST FIX #1 修复后）：验证失败时生成的错误包含 source_name、operation、detail 字段

### 总结

新闻/情绪数据适配器整体架构设计合理，代码质量良好，接口契约清晰。主要问题集中在：
1. AC-8 验收标准未完全满足（未复用 DataSourceError）
2. RSS feeds 串行获取违反并发性能要求

修复以上两个 [MUST FIX] 问题后可重新提交 QA 评估。

# Feature: 推送通知渠道

## User Story
作为一名投资者，我希望分析报告能通过企业微信、飞书、邮件或自定义Webhook自动推送给我，这样我不需要主动打开应用就能收到重要的投资分析信息。

## Acceptance Criteria
- [x] AC-1: BaseNotifier 抽象基类定义 send()、channel_name、max_message_length、format_message()、is_configured() 接口
- [x] AC-2: 企业微信 Webhook 通知器可发送 Markdown 格式消息
- [x] AC-3: 飞书 Webhook 通知器可发送富文本卡片消息
- [x] AC-4: Email SMTP 通知器可发送 HTML 格式邮件
- [x] AC-5: 自定义 Webhook 通知器可向多个 URL 发送 JSON 消息
- [x] AC-6: NotificationManager 支持多渠道注册和批量发送
- [x] AC-7: catch-up 模式不触发推送通知
- [x] AC-8: 免打扰时段（22:00-08:00）非紧急消息不推送
- [x] AC-9: 紧急消息可绕过免打扰时段
- [x] AC-10: 事件推送受每日限额约束（默认10次/天）
- [x] AC-11: 发送失败后 30 秒重试一次
- [x] AC-12: 连续失败 3 次输出警告日志

## Data Flow
Input: 分析报告或事件通知（NotificationMessage：标题、内容、级别、是否catch-up）
Processing: NotificationManager 检查推送策略（catch-up过滤、免打扰时段、事件限额），通过已注册且已配置的渠道发送消息，失败自动重试
Output: 各渠道发送结果（SendResult：成功/失败、渠道名、错误信息、时间戳）

## API Contract
本模块为内部服务模块，不直接暴露 HTTP API。通过 Python 接口供调度器和业务层调用：
- `NotificationManager.register(notifier)` — 注册通知渠道
- `NotificationManager.send_all(message, is_event)` — 批量发送
- `NotificationManager.should_send(is_catchup)` — 判断是否应推送
- `NotificationManager.is_silent_period()` — 免打扰时段检查

## Dependencies
- Requires: config（配置管理）, log（日志系统）
- Provides: 多渠道通知能力，供 scheduler 和 business 模块调用

## Non-functional Requirements
- Performance: 单次发送超时 10 秒（Webhook）/ 30 秒（Email）
- Security: Webhook URL 和 SMTP 密码通过配置系统管理，不硬编码
- Compatibility: 支持企业微信、飞书、标准 SMTP、任意 Webhook 接口

## Skills Evaluation
- Searched: Python notification libraries, webhook clients
- Found: httpx（已在项目依赖中）, smtplib（标准库）
- Decision: 使用 httpx 发送 Webhook 请求，smtplib 通过 asyncio.to_thread 包装发送邮件，无需引入额外依赖

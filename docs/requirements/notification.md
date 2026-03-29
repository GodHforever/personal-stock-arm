# Notification & Push Requirements

> Subordinate to: `docs/paradigm/` (development paradigm is supreme authority)

---

## 1. Push Channels

| Channel | Use Case | Complexity | Format Support |
|---------|----------|-----------|---------------|
| WeChat Work Webhook (企业微信) | Corporate intranet users | Low | Markdown |
| Feishu Webhook (飞书) | Feishu users | Low | Rich text, cards |
| Email (SMTP) | Detailed report delivery | Medium | HTML, attachments |
| Custom Webhook | Integration with any system | Medium | JSON payload |

### Abstraction

```python
class BaseNotifier(ABC):
    @abstractmethod
    async def send(self, message: NotificationMessage) -> SendResult: ...

    @property
    @abstractmethod
    def channel_name(self) -> str: ...

    @property
    @abstractmethod
    def max_message_length(self) -> int: ...

    @abstractmethod
    def format_message(self, report: AnalysisReport) -> str:
        """Convert analysis report to channel-specific format."""
        ...
```

## 2. Push Strategy

### Scheduled Push
- **Default**: Daily after market close (18:00 Beijing time)
- **Content**: Full analysis report (all watchlist stocks + macro summary + international briefing)
- **Configurable**: `STOCK_ARM_PUSH_TIME=18:00`
- **Trading day check**: Skip non-trading days (configurable: `STOCK_ARM_TRADING_DAY_CHECK=true`)

### Event Push
- **Trigger**: Major news, abnormal price movements, earnings releases
- **Content**: Brief alert with key information
- **Throttle**: Max 10 event pushes per day per channel (prevent spam)

### Silent Period
- **Default**: 22:00 - 08:00 (no non-urgent pushes)
- **Configurable**: `STOCK_ARM_SILENT_START=22:00`, `STOCK_ARM_SILENT_END=08:00`
- **Override**: Urgent alerts (>5% index drop) bypass silent period

### Content Tiers
| Tier | Channel | Content |
|------|---------|---------|
| Summary | Bot (WeChat/Feishu) | Key signals, 1-2 sentence per stock |
| Standard | Web UI | Full analysis with charts |
| Detailed | Email | Complete report with attachments |

## 3. Configuration

```env
# WeChat Work
STOCK_ARM_WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# Feishu
STOCK_ARM_FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# Email
STOCK_ARM_EMAIL_SMTP_HOST=smtp.example.com
STOCK_ARM_EMAIL_SMTP_PORT=465
STOCK_ARM_EMAIL_SENDER=user@example.com
STOCK_ARM_EMAIL_PASSWORD=xxx
STOCK_ARM_EMAIL_RECEIVERS=user1@example.com,user2@example.com

# Custom Webhook
STOCK_ARM_CUSTOM_WEBHOOK_URLS=https://hook1.example.com,https://hook2.example.com

# Push timing
STOCK_ARM_PUSH_TIME=18:00
STOCK_ARM_SILENT_START=22:00
STOCK_ARM_SILENT_END=08:00
STOCK_ARM_EVENT_PUSH_DAILY_LIMIT=10
```

## 4. Error Handling

- Push failure must not crash the application
- Failed pushes logged with channel name, error details, message preview
- Retry: 1 retry after 30s delay, then give up
- If a channel fails consistently (3+ consecutive failures), log WARNING and suggest checking config

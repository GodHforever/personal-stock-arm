"""自定义 Webhook 通知渠道。"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.config import ConfigManager
from src.log import get_logger
from src.notification.base import BaseNotifier, NotificationMessage, SendResult

logger = get_logger(__name__)

# 自定义 Webhook JSON payload 最大长度
_MAX_LENGTH = 65536
_TIMEOUT = 10.0


class WebhookNotifier(BaseNotifier):
    """自定义 Webhook 通知器。

    向配置的自定义 Webhook URL 发送 JSON 格式消息。
    支持多个 URL，逗号分隔。
    """

    @property
    def channel_name(self) -> str:
        return "自定义Webhook"

    @property
    def max_message_length(self) -> int:
        return _MAX_LENGTH

    async def is_configured(self) -> bool:
        """检查是否配置了自定义 Webhook URL。"""
        config = ConfigManager.get_config()
        urls = config.push.custom_webhook_urls
        return bool(urls)

    def format_message(self, title: str, content: str) -> str:
        """格式化为纯文本。"""
        text = f"{title}\n\n{content}"
        return self._truncate(text)

    def _get_urls(self) -> list[str]:
        """获取所有配置的 Webhook URL。"""
        config = ConfigManager.get_config()
        raw = config.push.custom_webhook_urls
        return [u.strip() for u in raw.split(",") if u.strip()]

    async def send(self, message: NotificationMessage) -> SendResult:
        """向所有配置的 Webhook URL 发送 JSON 消息。"""
        urls = self._get_urls()
        if not urls:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="自定义 Webhook URL 未配置",
                timestamp=datetime.now(tz=UTC),
            )

        formatted = self.format_message(message.title, message.content)
        payload = {
            "title": message.title,
            "content": formatted,
            "level": message.level.value,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        errors: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                for url in urls:
                    try:
                        response = await client.post(url, json=payload)
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        errors.append(f"{url}: {exc}")
                        logger.error("[%s] 发送到 %s 失败: %s", self.channel_name, url, exc)
        except httpx.HTTPError as exc:
            errors.append(f"客户端错误: {exc}")

        if errors:
            error_msg = "; ".join(errors)
            # 部分成功也算失败，确保重试
            return SendResult(
                success=False,
                channel=self.channel_name,
                error=error_msg,
                timestamp=datetime.now(tz=UTC),
            )

        logger.info("[%s] 消息发送成功: %s", self.channel_name, message.title)
        return SendResult(
            success=True,
            channel=self.channel_name,
            timestamp=datetime.now(tz=UTC),
        )

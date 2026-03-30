"""企业微信 Webhook 通知渠道。"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.config import ConfigManager
from src.log import get_logger
from src.notification.base import BaseNotifier, NotificationMessage, SendResult

logger = get_logger(__name__)

# 企业微信 Markdown 消息最大长度
_MAX_LENGTH = 4096
_TIMEOUT = 10.0


class WeChatNotifier(BaseNotifier):
    """企业微信 Webhook 通知器。

    通过企业微信群机器人 Webhook 发送 Markdown 格式消息。
    """

    @property
    def channel_name(self) -> str:
        return "企业微信"

    @property
    def max_message_length(self) -> int:
        return _MAX_LENGTH

    async def is_configured(self) -> bool:
        """检查是否配置了 Webhook URL。"""
        config = ConfigManager.get_config()
        url = config.push.wechat_webhook_url.get_secret_value()
        return bool(url)

    def format_message(self, title: str, content: str) -> str:
        """格式化为企业微信 Markdown 格式。"""
        text = f"## {title}\n\n{content}"
        return self._truncate(text)

    async def send(self, message: NotificationMessage) -> SendResult:
        """通过企业微信 Webhook 发送消息。"""
        config = ConfigManager.get_config()
        url = config.push.wechat_webhook_url.get_secret_value()

        if not url:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="企业微信 Webhook URL 未配置",
                timestamp=datetime.now(tz=UTC),
            )

        formatted = self.format_message(message.title, message.content)
        payload = {
            "msgtype": "markdown",
            "markdown": {"content": formatted},
        }

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

            logger.info("[%s] 消息发送成功: %s", self.channel_name, message.title)
            return SendResult(
                success=True,
                channel=self.channel_name,
                timestamp=datetime.now(tz=UTC),
            )
        except httpx.HTTPError as exc:
            error_msg = f"发送失败: {exc}"
            logger.error("[%s] %s", self.channel_name, error_msg)
            return SendResult(
                success=False,
                channel=self.channel_name,
                error=error_msg,
                timestamp=datetime.now(tz=UTC),
            )

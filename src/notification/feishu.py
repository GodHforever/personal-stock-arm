"""飞书 Webhook 通知渠道。"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from src.config import ConfigManager
from src.log import get_logger
from src.notification.base import BaseNotifier, NotificationMessage, SendResult

logger = get_logger(__name__)

# 飞书富文本消息最大长度
_MAX_LENGTH = 4096
_TIMEOUT = 10.0


class FeishuNotifier(BaseNotifier):
    """飞书 Webhook 通知器。

    通过飞书群机器人 Webhook 发送富文本卡片消息。
    """

    @property
    def channel_name(self) -> str:
        return "飞书"

    @property
    def max_message_length(self) -> int:
        return _MAX_LENGTH

    async def is_configured(self) -> bool:
        """检查是否配置了 Webhook URL。"""
        config = ConfigManager.get_config()
        url = config.push.feishu_webhook_url.get_secret_value()
        return bool(url)

    def format_message(self, title: str, content: str) -> str:
        """格式化为飞书富文本格式。"""
        text = f"{title}\n\n{content}"
        return self._truncate(text)

    async def send(self, message: NotificationMessage) -> SendResult:
        """通过飞书 Webhook 发送富文本卡片消息。"""
        config = ConfigManager.get_config()
        url = config.push.feishu_webhook_url.get_secret_value()

        if not url:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="飞书 Webhook URL 未配置",
                timestamp=datetime.now(tz=UTC),
            )

        formatted = self.format_message(message.title, message.content)
        # 飞书交互卡片格式
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": message.title,
                    },
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": formatted,
                    },
                ],
            },
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

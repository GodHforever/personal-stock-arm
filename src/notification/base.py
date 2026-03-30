"""推送通知基础定义：BaseNotifier 抽象基类、NotificationMessage 和 SendResult 模型。"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class NotificationLevel(enum.StrEnum):
    """通知级别。"""

    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"


class NotificationMessage(BaseModel):
    """推送通知消息。"""

    title: str
    content: str
    level: NotificationLevel = NotificationLevel.INFO
    is_catchup: bool = False


class SendResult(BaseModel):
    """发送结果。"""

    success: bool
    channel: str
    error: str | None = None
    timestamp: datetime


class BaseNotifier(ABC):
    """通知渠道抽象基类。

    所有通知渠道实现必须继承此类并实现所有抽象方法。
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """渠道名称。"""
        ...

    @property
    @abstractmethod
    def max_message_length(self) -> int:
        """渠道支持的最大消息长度。"""
        ...

    @abstractmethod
    async def send(self, message: NotificationMessage) -> SendResult:
        """发送通知消息。

        Args:
            message: 待发送的通知消息

        Returns:
            发送结果
        """
        ...

    @abstractmethod
    def format_message(self, title: str, content: str) -> str:
        """格式化消息内容为渠道特定格式。

        Args:
            title: 消息标题
            content: 消息正文

        Returns:
            格式化后的消息字符串
        """
        ...

    @abstractmethod
    async def is_configured(self) -> bool:
        """检查渠道是否已正确配置。

        Returns:
            True 表示已配置可用
        """
        ...

    def _truncate(self, text: str) -> str:
        """截断超长消息。"""
        max_len = self.max_message_length
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

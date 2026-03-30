"""推送通知模块：提供多渠道通知能力和推送策略管理。"""

from __future__ import annotations

from src.notification.base import BaseNotifier, NotificationMessage, SendResult
from src.notification.manager import NotificationManager

__all__ = [
    "BaseNotifier",
    "NotificationManager",
    "NotificationMessage",
    "SendResult",
]

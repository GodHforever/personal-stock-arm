"""通知管理器：多渠道编排、推送策略和重试逻辑。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from src.config import ConfigManager
from src.log import get_logger
from src.notification.base import BaseNotifier, NotificationMessage, SendResult

logger = get_logger(__name__)

# 重试延迟（秒）
_RETRY_DELAY: float = 30.0
# 连续失败警告阈值
_CONSECUTIVE_FAILURE_THRESHOLD: int = 3


class NotificationManager:
    """通知管理器。

    负责管理多个通知渠道，执行推送策略（免打扰时段、catch-up 过滤），
    以及失败重试逻辑。
    """

    def __init__(self) -> None:
        self._notifiers: list[BaseNotifier] = []
        self._consecutive_failures: dict[str, int] = {}
        self._event_push_count: dict[str, int] = {}
        self._event_push_date: str = ""

    def register(self, notifier: BaseNotifier) -> None:
        """注册通知渠道。

        Args:
            notifier: 通知渠道实例
        """
        self._notifiers.append(notifier)
        logger.info("已注册通知渠道: %s", notifier.channel_name)

    @property
    def notifiers(self) -> list[BaseNotifier]:
        """已注册的通知渠道列表。"""
        return list(self._notifiers)

    def should_send(self, is_catchup: bool = False) -> bool:
        """判断是否应该发送通知。

        catch-up（补漏）模式下不发送通知，避免垃圾消息。

        Args:
            is_catchup: 是否为 catch-up 模式

        Returns:
            True 表示应该发送
        """
        if is_catchup:
            logger.info("当前为 catch-up 模式，跳过推送通知")
            return False
        return True

    def is_silent_period(self, now: datetime | None = None) -> bool:
        """检查当前是否处于免打扰时段。

        默认免打扰时段: 22:00 - 08:00（北京时间）。

        Args:
            now: 当前时间，默认使用 UTC 时间

        Returns:
            True 表示当前处于免打扰时段
        """
        config = ConfigManager.get_config()
        push = config.push

        if now is None:
            now = datetime.now(tz=UTC)

        # 解析免打扰时段配置
        silent_start_h, silent_start_m = (int(x) for x in push.silent_start.split(":"))
        silent_end_h, silent_end_m = (int(x) for x in push.silent_end.split(":"))

        current_minutes = now.hour * 60 + now.minute
        start_minutes = silent_start_h * 60 + silent_start_m
        end_minutes = silent_end_h * 60 + silent_end_m

        # 跨午夜时段（如 22:00 - 08:00）
        if start_minutes > end_minutes:
            return current_minutes >= start_minutes or current_minutes < end_minutes
        # 同日时段（如 01:00 - 06:00）
        return start_minutes <= current_minutes < end_minutes

    def _check_event_limit(self) -> bool:
        """检查今日事件推送是否超限。

        Returns:
            True 表示未超限，可以发送
        """
        config = ConfigManager.get_config()
        limit = config.push.event_push_daily_limit

        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        if self._event_push_date != today:
            self._event_push_date = today
            self._event_push_count.clear()

        total = sum(self._event_push_count.values())
        return total < limit

    def _increment_event_count(self, channel: str) -> None:
        """增加事件推送计数。"""
        self._event_push_count[channel] = self._event_push_count.get(channel, 0) + 1

    async def send_all(
        self,
        message: NotificationMessage,
        is_event: bool = False,
    ) -> list[SendResult]:
        """向所有已配置的渠道发送消息。

        Args:
            message: 待发送的通知消息
            is_event: 是否为事件推送（受每日限额约束）

        Returns:
            各渠道的发送结果列表
        """
        # catch-up 模式不推送
        if not self.should_send(is_catchup=message.is_catchup):
            return []

        # 免打扰时段不推送（紧急消息除外）
        if message.level != "urgent" and self.is_silent_period():
            logger.info("当前处于免打扰时段，跳过非紧急推送: %s", message.title)
            return []

        # 事件推送检查每日限额
        if is_event and not self._check_event_limit():
            logger.warning("今日事件推送已达上限，跳过: %s", message.title)
            return []

        results: list[SendResult] = []

        for notifier in self._notifiers:
            if not await notifier.is_configured():
                logger.debug("渠道 %s 未配置，跳过", notifier.channel_name)
                continue

            result = await self._send_with_retry(notifier, message)
            results.append(result)

            if result.success:
                self._consecutive_failures[notifier.channel_name] = 0
                if is_event:
                    self._increment_event_count(notifier.channel_name)
            else:
                count = self._consecutive_failures.get(notifier.channel_name, 0) + 1
                self._consecutive_failures[notifier.channel_name] = count
                if count >= _CONSECUTIVE_FAILURE_THRESHOLD:
                    logger.warning(
                        "渠道 %s 已连续失败 %d 次，请检查配置",
                        notifier.channel_name,
                        count,
                    )

        return results

    async def _send_with_retry(
        self,
        notifier: BaseNotifier,
        message: NotificationMessage,
    ) -> SendResult:
        """发送消息，失败后重试一次。

        Args:
            notifier: 通知渠道
            message: 通知消息

        Returns:
            发送结果
        """
        result = await notifier.send(message)
        if result.success:
            return result

        # 失败后延迟 30 秒重试一次
        logger.info(
            "[%s] 发送失败，%.0f 秒后重试: %s",
            notifier.channel_name,
            _RETRY_DELAY,
            result.error,
        )
        await asyncio.sleep(_RETRY_DELAY)

        retry_result = await notifier.send(message)
        if retry_result.success:
            logger.info("[%s] 重试成功: %s", notifier.channel_name, message.title)
        else:
            logger.error(
                "[%s] 重试失败，放弃发送: %s",
                notifier.channel_name,
                retry_result.error,
            )
        return retry_result

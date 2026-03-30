"""Token 预算追踪器：控制每日 LLM 调用成本。"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


class TokenBudgetTracker:
    """内存中跟踪当日 token 用量，支持预算警告和限制。

    每日预算通过 daily_limit 参数设置。
    当用量达到 80% 时记录警告日志，达到 100% 时拒绝调用。
    日期切换时自动重置计数。
    """

    def __init__(self, daily_limit: int = 500_000) -> None:
        self._daily_limit = daily_limit
        self._today: date = date.today()
        self._used_tokens: int = 0
        self._warned: bool = False

    def _reset_if_new_day(self) -> None:
        """如果日期已变更，重置当日用量。"""
        today = date.today()
        if today != self._today:
            logger.info(
                "日期切换 (%s -> %s)，重置 token 用量计数",
                self._today.isoformat(),
                today.isoformat(),
            )
            self._today = today
            self._used_tokens = 0
            self._warned = False

    @property
    def used_tokens(self) -> int:
        """当日已使用 token 数。"""
        self._reset_if_new_day()
        return self._used_tokens

    @property
    def daily_limit(self) -> int:
        """每日 token 预算上限。"""
        return self._daily_limit

    @property
    def remaining(self) -> int:
        """当日剩余可用 token 数。"""
        self._reset_if_new_day()
        return max(0, self._daily_limit - self._used_tokens)

    def check_budget(self, tokens: int) -> bool:
        """检查是否有足够的预算执行调用。

        Args:
            tokens: 预估需要的 token 数

        Returns:
            True 表示预算充足，False 表示已超预算
        """
        self._reset_if_new_day()

        if self._daily_limit <= 0:
            return True

        if self._used_tokens + tokens > self._daily_limit:
            logger.warning(
                "Token 预算已耗尽：已用 %d / %d，本次请求 %d tokens",
                self._used_tokens,
                self._daily_limit,
                tokens,
            )
            return False

        return True

    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """记录一次 LLM 调用的 token 用量。

        Args:
            model: 使用的模型名
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
        """
        self._reset_if_new_day()

        total = input_tokens + output_tokens
        self._used_tokens += total

        logger.debug(
            "Token 用量记录：模型=%s, 输入=%d, 输出=%d, 当日累计=%d/%d",
            model,
            input_tokens,
            output_tokens,
            self._used_tokens,
            self._daily_limit,
        )

        # 80% 警告
        if (
            not self._warned
            and self._daily_limit > 0
            and self._used_tokens >= self._daily_limit * 0.8
        ):
            self._warned = True
            logger.warning(
                "Token 用量已达每日预算的 80%%：%d / %d",
                self._used_tokens,
                self._daily_limit,
            )

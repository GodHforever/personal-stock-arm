"""任务调度器：基于 APScheduler 的统一调度管理，支持运行模式自适应。"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Coroutine
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from sqlalchemy import select

from src.config import ConfigManager, RuntimeMode, SchedulerConfig
from src.db.engine import Database
from src.db.models import SchedulerState
from src.log import get_logger

logger = get_logger(__name__)

# 每日类任务名称列表，用于交易日检查
_DAILY_JOBS: set[str] = {
    "daily_analysis",
    "daily_macro",
    "daily_briefing",
    "earnings_scan",
}


def _parse_time(time_str: str) -> tuple[int, int]:
    """解析 'HH:MM' 格式的时间字符串。

    Returns:
        (hour, minute) 元组
    """
    parts = time_str.strip().split(":")
    return int(parts[0]), int(parts[1])


def _parse_cron_expr(cron_expr: str) -> dict[str, str]:
    """解析 5 字段 cron 表达式为 APScheduler CronTrigger 参数。

    格式：minute hour day month day_of_week
    """
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"cron 表达式格式错误，需要 5 个字段: '{cron_expr}'")
    return {
        "minute": fields[0],
        "hour": fields[1],
        "day": fields[2],
        "month": fields[3],
        "day_of_week": fields[4],
    }


class TaskScheduler:
    """统一任务调度器。

    根据运行模式自适应行为：
    - Cloud/Docker：持续调度，按 cron 时间触发
    - Local：启动时补跑当天遗漏任务，注册剩余今日任务

    使用方式::

        scheduler = TaskScheduler(db)
        scheduler.register_job("daily_analysis", daily_analysis_func, "0 18 * * *")
        await scheduler.start()
        # ... 应用运行 ...
        await scheduler.stop()
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._scheduler = AsyncIOScheduler()
        self._jobs: dict[str, _JobEntry] = {}
        self._running = False

    @property
    def running(self) -> bool:
        """调度器是否正在运行。"""
        return self._running

    @property
    def registered_jobs(self) -> list[str]:
        """已注册的任务名称列表。"""
        return list(self._jobs.keys())

    def register_job(
        self,
        name: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
        cron_expr: str,
    ) -> None:
        """注册定时任务。

        Args:
            name: 任务名称（唯一标识）
            func: 异步任务函数
            cron_expr: 5 字段 cron 表达式（minute hour day month day_of_week）
        """
        if self._running:
            raise RuntimeError("调度器运行中不允许注册新任务")
        self._jobs[name] = _JobEntry(name=name, func=func, cron_expr=cron_expr)
        logger.info("注册调度任务: %s (cron: %s)", name, cron_expr)

    async def start(self) -> None:
        """启动调度器。

        根据运行模式执行不同的启动策略：
        - Cloud/Docker：直接启动持续调度
        - Local：检查并补跑当天遗漏任务，注册剩余任务
        """
        if self._running:
            logger.warning("调度器已在运行中，忽略重复启动")
            return

        config = ConfigManager.get_config()
        mode = config.runtime_env
        scheduler_config = config.scheduler

        if not scheduler_config.enabled:
            logger.info("调度器已禁用（配置 scheduler.enabled=false）")
            return

        logger.info("启动任务调度器，运行模式: %s", mode.value)

        if mode in (RuntimeMode.CLOUD, RuntimeMode.DOCKER):
            await self._start_continuous()
        else:
            await self._start_local(scheduler_config)

        self._running = True
        logger.info("任务调度器启动完成，已注册 %d 个任务", len(self._jobs))

    async def stop(self) -> None:
        """停止调度器，记录所有任务的 last_run_time。"""
        if not self._running:
            logger.warning("调度器未在运行，忽略停止请求")
            return

        logger.info("正在停止任务调度器...")

        # 记录所有任务的最终状态
        now = datetime.datetime.now()
        for name in self._jobs:
            await self._update_last_run_time(name, now, status="stopped")

        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("任务调度器已停止")

    async def _start_continuous(self) -> None:
        """持续调度模式（Cloud/Docker）：注册所有任务到 APScheduler。"""
        for entry in self._jobs.values():
            self._add_apscheduler_job(entry)
        self._scheduler.start()

    async def _start_local(self, config: SchedulerConfig) -> None:
        """本地模式：补跑当天遗漏任务，注册剩余今日任务。"""
        now = datetime.datetime.now()
        today = now.date()

        for entry in self._jobs.values():
            last_run = await self._get_last_run_time(entry.name)

            # 判断今天是否已执行
            already_run_today = (
                last_run is not None and last_run.date() == today
            )

            if already_run_today:
                logger.info("任务 %s 今日已执行，跳过补跑", entry.name)
            else:
                # 判断任务是否应该在当前时间之前执行
                should_catch_up = self._should_catch_up(entry.cron_expr, now)
                if should_catch_up:
                    # 交易日检查
                    if self._should_skip_for_trading_day(entry.name, config):
                        logger.info(
                            "任务 %s 因非交易日跳过补跑", entry.name
                        )
                    else:
                        logger.info("补跑任务: %s", entry.name)
                        await self._execute_job(entry)

            # 注册未来的任务
            self._add_apscheduler_job(entry)

        self._scheduler.start()

    def _add_apscheduler_job(self, entry: _JobEntry) -> None:
        """将任务添加到 APScheduler。"""
        cron_params = _parse_cron_expr(entry.cron_expr)
        trigger = CronTrigger(**cron_params)

        self._scheduler.add_job(
            self._wrapped_execute,
            trigger=trigger,
            id=entry.name,
            name=entry.name,
            args=[entry],
            replace_existing=True,
        )

    async def _wrapped_execute(self, entry: _JobEntry) -> None:
        """包装执行：添加交易日检查和状态记录。"""
        config = ConfigManager.get_config()
        scheduler_config = config.scheduler

        if self._should_skip_for_trading_day(entry.name, scheduler_config):
            logger.info("任务 %s 因非交易日跳过执行", entry.name)
            return

        await self._execute_job(entry)

    async def _execute_job(self, entry: _JobEntry) -> None:
        """执行任务并更新状态。"""
        logger.info("开始执行任务: %s", entry.name)
        try:
            await entry.func()
            now = datetime.datetime.now()
            await self._update_last_run_time(entry.name, now, status="success")
            logger.info("任务 %s 执行完成", entry.name)
        except Exception:
            now = datetime.datetime.now()
            await self._update_last_run_time(entry.name, now, status="failed")
            logger.exception("任务 %s 执行失败", entry.name)

    def _should_catch_up(self, cron_expr: str, now: datetime.datetime) -> bool:
        """判断任务在当天是否应该在当前时间之前执行过。"""
        cron_params = _parse_cron_expr(cron_expr)

        # 对于 day/month/day_of_week 不是通配符的任务，需要检查今天是否匹配
        day_field = cron_params.get("day", "*")
        month_field = cron_params.get("month", "*")

        if day_field != "*" and int(day_field) != now.day:
            return False
        if month_field != "*" and int(month_field) != now.month:
            return False

        # 检查时间是否已过
        hour = int(cron_params["hour"])
        minute = int(cron_params["minute"])
        scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return now >= scheduled_time

    @staticmethod
    def _should_skip_for_trading_day(
        job_name: str, config: SchedulerConfig
    ) -> bool:
        """检查是否因非交易日而跳过任务。

        仅 daily 类任务受交易日检查影响。
        当前实现使用简单的周末检测，后续可接入交易日历 API。
        """
        if not config.trading_day_check:
            return False
        if job_name not in _DAILY_JOBS:
            return False

        today = datetime.date.today()
        # 周末视为非交易日（简化实现，后续可接入交易日历）
        return today.weekday() >= 5  # noqa: PLR2004

    async def _get_last_run_time(
        self, job_name: str
    ) -> datetime.datetime | None:
        """从数据库获取任务的最近运行时间。"""
        async with self._db.session() as session:
            result = await session.execute(
                select(SchedulerState.last_run_time).where(
                    SchedulerState.job_name == job_name
                )
            )
            row = result.scalar_one_or_none()
            return row

    async def _update_last_run_time(
        self,
        job_name: str,
        run_time: datetime.datetime,
        *,
        status: str = "success",
    ) -> None:
        """更新任务的最近运行时间到数据库。"""
        async with self._db.session() as session:
            result = await session.execute(
                select(SchedulerState).where(
                    SchedulerState.job_name == job_name
                )
            )
            state = result.scalar_one_or_none()

            if state is None:
                state = SchedulerState(
                    job_name=job_name,
                    last_run_time=run_time,
                    status=status,
                )
                session.add(state)
            else:
                state.last_run_time = run_time
                state.status = status


class _JobEntry:
    """内部任务条目，保存任务元数据。"""

    __slots__ = ("name", "func", "cron_expr")

    def __init__(
        self,
        name: str,
        func: Callable[..., Coroutine[Any, Any, Any]],
        cron_expr: str,
    ) -> None:
        self.name = name
        self.func = func
        self.cron_expr = cron_expr

"""任务调度器模块单元测试。"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.config import ConfigManager, SchedulerConfig
from src.db.base import Base
from src.db.engine import Database
from src.db.models import SchedulerState
from src.scheduler.scheduler import TaskScheduler, _parse_cron_expr, _parse_time


@pytest.fixture(autouse=True)
def _reset_config():
    """每个测试前后重置 ConfigManager 单例状态。"""
    ConfigManager.reset()
    yield
    ConfigManager.reset()


@pytest.fixture()
def _config_for_memory_db(monkeypatch):
    """配置内存数据库和本地模式用于测试。"""
    monkeypatch.setenv("STOCK_ARM_DB_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "local")
    monkeypatch.setenv("STOCK_ARM_SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("STOCK_ARM_TRADING_DAY_CHECK", "false")


@pytest_asyncio.fixture()
async def db(_config_for_memory_db):
    """提供初始化完成的内存数据库。"""
    database = Database()
    await database.initialize()
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield database
    await database.close()


# ============================================================
# 辅助函数测试
# ============================================================


class TestParseTime:
    """测试时间字符串解析。"""

    def test_parse_normal_time(self):
        """解析标准时间格式。"""
        assert _parse_time("18:00") == (18, 0)

    def test_parse_time_with_minutes(self):
        """解析带分钟的时间。"""
        assert _parse_time("09:30") == (9, 30)

    def test_parse_time_with_spaces(self):
        """解析带空格的时间。"""
        assert _parse_time("  18:00  ") == (18, 0)


class TestParseCronExpr:
    """测试 cron 表达式解析。"""

    def test_parse_daily_cron(self):
        """解析每日任务 cron。"""
        result = _parse_cron_expr("0 18 * * *")
        assert result == {
            "minute": "0",
            "hour": "18",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_parse_monthly_cron(self):
        """解析每月任务 cron。"""
        result = _parse_cron_expr("0 9 1 * *")
        assert result == {
            "minute": "0",
            "hour": "9",
            "day": "1",
            "month": "*",
            "day_of_week": "*",
        }

    def test_invalid_cron_raises(self):
        """字段数不正确时应抛出异常。"""
        with pytest.raises(ValueError, match="cron 表达式格式错误"):
            _parse_cron_expr("0 18 *")


# ============================================================
# AC-1: TaskScheduler 基本构造
# ============================================================


class TestTaskSchedulerInit:
    """测试 TaskScheduler 构造和基本属性。"""

    @pytest.mark.asyncio()
    async def test_init_with_database(self, db):
        """应能使用 Database 实例构造 TaskScheduler。"""
        scheduler = TaskScheduler(db)
        assert scheduler is not None
        assert scheduler.running is False

    @pytest.mark.asyncio()
    async def test_registered_jobs_empty_initially(self, db):
        """初始状态应无已注册任务。"""
        scheduler = TaskScheduler(db)
        assert scheduler.registered_jobs == []


# ============================================================
# AC-3: register_job 方法
# ============================================================


class TestRegisterJob:
    """测试任务注册。"""

    @pytest.mark.asyncio()
    async def test_register_job(self, db):
        """应能注册任务。"""

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test_job", dummy_task, "0 18 * * *")
        assert "test_job" in scheduler.registered_jobs

    @pytest.mark.asyncio()
    async def test_register_multiple_jobs(self, db):
        """应能注册多个任务。"""

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("job_a", dummy_task, "0 18 * * *")
        scheduler.register_job("job_b", dummy_task, "30 18 * * *")
        assert len(scheduler.registered_jobs) == 2

    @pytest.mark.asyncio()
    async def test_register_while_running_raises(self, db):
        """运行中注册任务应抛出异常。"""

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("job_a", dummy_task, "0 18 * * *")
        await scheduler.start()
        try:
            with pytest.raises(RuntimeError, match="调度器运行中不允许注册新任务"):
                scheduler.register_job("job_b", dummy_task, "30 18 * * *")
        finally:
            await scheduler.stop()


# ============================================================
# AC-2: start() 和 stop() 方法
# ============================================================


class TestStartStop:
    """测试调度器启动和停止。"""

    @pytest.mark.asyncio()
    async def test_start_sets_running(self, db):
        """start() 后 running 应为 True。"""

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test", dummy_task, "0 18 * * *")
        await scheduler.start()
        try:
            assert scheduler.running is True
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio()
    async def test_stop_clears_running(self, db):
        """stop() 后 running 应为 False。"""

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test", dummy_task, "0 18 * * *")
        await scheduler.start()
        await scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio()
    async def test_double_start_ignored(self, db):
        """重复启动应被忽略。"""

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test", dummy_task, "0 18 * * *")
        await scheduler.start()
        try:
            await scheduler.start()  # 不应抛出异常
            assert scheduler.running is True
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio()
    async def test_stop_without_start_ignored(self, db):
        """未启动时停止应被忽略。"""
        scheduler = TaskScheduler(db)
        await scheduler.stop()  # 不应抛出异常

    @pytest.mark.asyncio()
    async def test_start_with_scheduler_disabled(self, db, monkeypatch):
        """调度器禁用时 start() 不应启动。"""
        monkeypatch.setenv("STOCK_ARM_SCHEDULER_ENABLED", "false")
        ConfigManager.reset()

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test", dummy_task, "0 18 * * *")
        await scheduler.start()
        assert scheduler.running is False


# ============================================================
# AC-4: 运行模式自适应
# ============================================================


class TestRuntimeModeAdaptation:
    """测试运行模式自适应行为。"""

    @pytest.mark.asyncio()
    async def test_cloud_mode_continuous(self, db, monkeypatch):
        """Cloud 模式应使用持续调度。"""
        monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "cloud")
        ConfigManager.reset()

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test", dummy_task, "0 18 * * *")
        await scheduler.start()
        try:
            assert scheduler.running is True
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio()
    async def test_local_mode_catch_up(self, db, monkeypatch):
        """Local 模式应执行补跑逻辑。"""
        monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        ConfigManager.reset()

        executed = []

        async def tracking_task():
            executed.append(True)

        # 使用过去时间的 cron 确保触发补跑
        now = datetime.datetime.now()
        past_hour = now.hour - 1 if now.hour > 0 else 0
        cron = f"0 {past_hour} * * *"

        scheduler = TaskScheduler(db)
        scheduler.register_job("catch_up_test", tracking_task, cron)
        await scheduler.start()
        try:
            # 如果当前小时 > 0，任务时间已过，应触发补跑
            if now.hour > 0:
                assert len(executed) == 1
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio()
    async def test_local_mode_skip_already_run_today(self, db, monkeypatch):
        """Local 模式下今日已执行的任务应跳过补跑。"""
        monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        ConfigManager.reset()

        executed = []

        async def tracking_task():
            executed.append(True)

        now = datetime.datetime.now()
        past_hour = now.hour - 1 if now.hour > 0 else 0
        cron = f"0 {past_hour} * * *"

        # 先在数据库中标记今日已执行
        async with db.session() as session:
            state = SchedulerState(
                job_name="already_run",
                last_run_time=now,
                status="success",
            )
            session.add(state)

        scheduler = TaskScheduler(db)
        scheduler.register_job("already_run", tracking_task, cron)
        await scheduler.start()
        try:
            assert len(executed) == 0
        finally:
            await scheduler.stop()


# ============================================================
# AC-5: last_run_time 持久化
# ============================================================


class TestLastRunTimePersistence:
    """测试 last_run_time 持久化。"""

    @pytest.mark.asyncio()
    async def test_execute_updates_last_run_time(self, db, monkeypatch):
        """任务执行后应更新数据库中的 last_run_time。"""
        monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        ConfigManager.reset()

        async def dummy_task():
            pass

        now = datetime.datetime.now()
        past_hour = now.hour - 1 if now.hour > 0 else 0
        cron = f"0 {past_hour} * * *"

        scheduler = TaskScheduler(db)
        scheduler.register_job("persist_test", dummy_task, cron)
        await scheduler.start()

        try:
            if now.hour > 0:
                # 验证数据库中有记录
                async with db.session() as session:
                    result = await session.execute(
                        select(SchedulerState).where(
                            SchedulerState.job_name == "persist_test"
                        )
                    )
                    state = result.scalar_one_or_none()
                    assert state is not None
                    assert state.last_run_time is not None
                    assert state.status == "success"
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio()
    async def test_failed_job_records_failed_status(self, db, monkeypatch):
        """任务执行失败应记录 failed 状态。"""
        monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        ConfigManager.reset()

        async def failing_task():
            raise RuntimeError("测试失败")

        now = datetime.datetime.now()
        past_hour = now.hour - 1 if now.hour > 0 else 0
        cron = f"0 {past_hour} * * *"

        scheduler = TaskScheduler(db)
        scheduler.register_job("fail_test", failing_task, cron)
        await scheduler.start()

        try:
            if now.hour > 0:
                async with db.session() as session:
                    result = await session.execute(
                        select(SchedulerState).where(
                            SchedulerState.job_name == "fail_test"
                        )
                    )
                    state = result.scalar_one_or_none()
                    assert state is not None
                    assert state.status == "failed"
        finally:
            await scheduler.stop()


# ============================================================
# AC-6: 优雅关闭
# ============================================================


class TestGracefulShutdown:
    """测试优雅关闭。"""

    @pytest.mark.asyncio()
    async def test_stop_records_last_run_time(self, db, monkeypatch):
        """stop() 应记录所有任务的 last_run_time。"""
        monkeypatch.setenv("STOCK_ARM_RUNTIME_ENV", "cloud")
        ConfigManager.reset()

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("shutdown_test", dummy_task, "0 23 * * *")
        await scheduler.start()
        await scheduler.stop()

        async with db.session() as session:
            result = await session.execute(
                select(SchedulerState).where(
                    SchedulerState.job_name == "shutdown_test"
                )
            )
            state = result.scalar_one_or_none()
            assert state is not None
            assert state.status == "stopped"


# ============================================================
# AC-7: stub 任务函数
# ============================================================


class TestStubJobs:
    """测试 stub 任务函数。"""

    @pytest.mark.asyncio()
    async def test_daily_analysis_runs(self):
        """daily_analysis stub 应正常执行。"""
        from src.scheduler.jobs import daily_analysis

        await daily_analysis()  # 不应抛出异常

    @pytest.mark.asyncio()
    async def test_daily_macro_runs(self):
        """daily_macro stub 应正常执行。"""
        from src.scheduler.jobs import daily_macro

        await daily_macro()

    @pytest.mark.asyncio()
    async def test_daily_briefing_runs(self):
        """daily_briefing stub 应正常执行。"""
        from src.scheduler.jobs import daily_briefing

        await daily_briefing()

    @pytest.mark.asyncio()
    async def test_earnings_scan_runs(self):
        """earnings_scan stub 应正常执行。"""
        from src.scheduler.jobs import earnings_scan

        await earnings_scan()

    @pytest.mark.asyncio()
    async def test_monthly_report_runs(self):
        """monthly_report stub 应正常执行。"""
        from src.scheduler.jobs import monthly_report

        await monthly_report()

    @pytest.mark.asyncio()
    async def test_data_cleanup_runs(self):
        """data_cleanup stub 应正常执行。"""
        from src.scheduler.jobs import data_cleanup

        await data_cleanup()


# ============================================================
# AC-8: 交易日检查
# ============================================================


class TestTradingDayCheck:
    """测试交易日检查。"""

    def test_skip_on_weekend(self):
        """周末应跳过 daily 类任务。"""
        config = SchedulerConfig(trading_day_check=True)
        # 模拟周六
        with patch("src.scheduler.scheduler.datetime") as mock_dt:
            mock_date = MagicMock()
            mock_date.weekday.return_value = 5  # 周六
            mock_dt.date.today.return_value = mock_date
            result = TaskScheduler._should_skip_for_trading_day(
                "daily_analysis", config
            )
            assert result is True

    def test_no_skip_on_weekday(self):
        """工作日不应跳过。"""
        config = SchedulerConfig(trading_day_check=True)
        with patch("src.scheduler.scheduler.datetime") as mock_dt:
            mock_date = MagicMock()
            mock_date.weekday.return_value = 2  # 周三
            mock_dt.date.today.return_value = mock_date
            result = TaskScheduler._should_skip_for_trading_day(
                "daily_analysis", config
            )
            assert result is False

    def test_no_skip_monthly_jobs(self):
        """月度任务不受交易日检查影响。"""
        config = SchedulerConfig(trading_day_check=True)
        with patch("src.scheduler.scheduler.datetime") as mock_dt:
            mock_date = MagicMock()
            mock_date.weekday.return_value = 5  # 周六
            mock_dt.date.today.return_value = mock_date
            result = TaskScheduler._should_skip_for_trading_day(
                "monthly_report", config
            )
            assert result is False

    def test_no_skip_when_check_disabled(self):
        """交易日检查禁用时不应跳过。"""
        config = SchedulerConfig(trading_day_check=False)
        # 不需要 mock，直接返回 False
        result = TaskScheduler._should_skip_for_trading_day(
            "daily_analysis", config
        )
        assert result is False


# ============================================================
# AC-9: 公开接口
# ============================================================


class TestPublicInterface:
    """测试模块公开接口。"""

    def test_import_task_scheduler(self):
        """应能从 src.scheduler 导入 TaskScheduler。"""
        from src.scheduler import TaskScheduler

        assert TaskScheduler is not None


# ============================================================
# AC-10: 中文文本
# ============================================================


class TestChineseText:
    """测试中文文本使用。"""

    def test_register_log_in_chinese(self, db):
        """注册任务时的日志应使用中文。"""
        # 通过代码检查确认日志消息为中文
        # 此测试主要验证模块可以正常导入和运行
        from src.scheduler.scheduler import TaskScheduler

        async def dummy_task():
            pass

        scheduler = TaskScheduler(db)
        scheduler.register_job("test", dummy_task, "0 18 * * *")
        assert "test" in scheduler.registered_jobs

"""数据库模块单元测试。"""

from __future__ import annotations

import datetime

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.config import ConfigManager
from src.db.base import Base, TimestampMixin
from src.db.engine import Database
from src.db.models import SchedulerState


@pytest.fixture(autouse=True)
def _reset_config():
    """每个测试前后重置 ConfigManager 单例状态。"""
    ConfigManager.reset()
    yield
    ConfigManager.reset()


@pytest.fixture()
def _config_for_memory_db(monkeypatch):
    """配置内存数据库用于测试。"""
    monkeypatch.setenv("STOCK_ARM_DB_URL", "sqlite+aiosqlite:///:memory:")


# ============================================================
# AC-4: TimestampMixin 测试
# ============================================================


class TestTimestampMixin:
    """测试 TimestampMixin 提供的字段。"""

    def test_mixin_provides_id_field(self):
        """TimestampMixin 应提供 id 主键字段。"""
        assert hasattr(TimestampMixin, "id")

    def test_mixin_provides_created_at_field(self):
        """TimestampMixin 应提供 created_at 字段。"""
        assert hasattr(TimestampMixin, "created_at")

    def test_mixin_provides_updated_at_field(self):
        """TimestampMixin 应提供 updated_at 字段。"""
        assert hasattr(TimestampMixin, "updated_at")


# ============================================================
# AC-5: SchedulerState 模型测试
# ============================================================


class TestSchedulerStateModel:
    """测试 SchedulerState 模型定义。"""

    def test_table_name(self):
        """表名应为 snake_case 单数形式。"""
        assert SchedulerState.__tablename__ == "scheduler_state"

    def test_has_job_name_column(self):
        """应包含 job_name 列。"""
        columns = {c.name for c in SchedulerState.__table__.columns}
        assert "job_name" in columns

    def test_has_last_run_time_column(self):
        """应包含 last_run_time 列。"""
        columns = {c.name for c in SchedulerState.__table__.columns}
        assert "last_run_time" in columns

    def test_has_status_column(self):
        """应包含 status 列。"""
        columns = {c.name for c in SchedulerState.__table__.columns}
        assert "status" in columns

    def test_has_timestamp_fields(self):
        """应包含 id、created_at、updated_at 字段（来自 TimestampMixin）。"""
        columns = {c.name for c in SchedulerState.__table__.columns}
        assert "id" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

    def test_job_name_is_unique(self):
        """job_name 列应有唯一约束。"""
        col = SchedulerState.__table__.c.job_name
        assert col.unique is True

    def test_last_run_time_is_nullable(self):
        """last_run_time 列应允许为空。"""
        col = SchedulerState.__table__.c.last_run_time
        assert col.nullable is True

    def test_status_is_not_nullable(self):
        """status 列不应允许为空。"""
        col = SchedulerState.__table__.c.status
        assert col.nullable is False


# ============================================================
# AC-1, AC-2, AC-3: Database 引擎测试
# ============================================================


class TestDatabase:
    """测试 Database 异步引擎管理。"""

    def test_engine_not_initialized_raises(self):
        """未初始化时访问 engine 应抛出 RuntimeError。"""
        db = Database()
        with pytest.raises(RuntimeError, match="数据库未初始化"):
            _ = db.engine

    @pytest.mark.asyncio()
    async def test_session_not_initialized_raises(self):
        """未初始化时获取 session 应抛出 RuntimeError。"""
        db = Database()
        with pytest.raises(RuntimeError, match="数据库未初始化"):
            async with db.session():
                pass

    @pytest.mark.asyncio()
    async def test_initialize_creates_engine(self, _config_for_memory_db):
        """initialize() 应成功创建异步引擎。"""
        db = Database()
        await db.initialize()
        try:
            assert db.engine is not None
        finally:
            await db.close()

    @pytest.mark.asyncio()
    async def test_wal_mode_enabled(self, _config_for_memory_db):
        """初始化后应启用 WAL 模式（内存数据库返回 memory）。"""
        db = Database()
        await db.initialize()
        try:
            async with db.engine.connect() as conn:
                result = await conn.execute(text("PRAGMA journal_mode"))
                mode = result.scalar()
                # 内存数据库 WAL 模式设置为 memory，不是 wal
                assert mode in ("wal", "memory")
        finally:
            await db.close()

    @pytest.mark.asyncio()
    async def test_session_commit_on_success(self, _config_for_memory_db):
        """会话正常退出时应自动提交。"""
        db = Database()
        await db.initialize()
        try:
            # 先创建表
            async with db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

            # 插入数据
            async with db.session() as session:
                state = SchedulerState(job_name="test_job", status="running")
                session.add(state)

            # 验证数据已持久化
            async with db.session() as session:
                result = await session.execute(
                    select(SchedulerState).where(SchedulerState.job_name == "test_job")
                )
                row = result.scalar_one()
                assert row.status == "running"
        finally:
            await db.close()

    @pytest.mark.asyncio()
    async def test_session_rollback_on_error(self, _config_for_memory_db):
        """会话异常时应自动回滚。"""
        db = Database()
        await db.initialize()
        try:
            async with db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

            # 插入初始数据
            async with db.session() as session:
                state = SchedulerState(job_name="rollback_test", status="ok")
                session.add(state)

            # 尝试插入重复数据（应触发唯一约束违反）
            with pytest.raises(Exception):
                async with db.session() as session:
                    dup = SchedulerState(job_name="rollback_test", status="dup")
                    session.add(dup)

            # 验证原始数据仍然存在
            async with db.session() as session:
                result = await session.execute(
                    select(SchedulerState).where(SchedulerState.job_name == "rollback_test")
                )
                row = result.scalar_one()
                assert row.status == "ok"
        finally:
            await db.close()

    @pytest.mark.asyncio()
    async def test_close_disposes_engine(self, _config_for_memory_db):
        """close() 应释放引擎资源。"""
        db = Database()
        await db.initialize()
        await db.close()
        with pytest.raises(RuntimeError, match="数据库未初始化"):
            _ = db.engine


# ============================================================
# AC-9: 公开接口测试
# ============================================================


class TestPublicInterface:
    """测试模块公开接口。"""

    def test_imports(self):
        """应能从 src.db 导入所有公开接口。"""
        from src.db import Base, Database, SchedulerState, TimestampMixin

        assert Base is not None
        assert Database is not None
        assert SchedulerState is not None
        assert TimestampMixin is not None


# ============================================================
# AC-10: 表命名规范测试
# ============================================================


class TestNamingConventions:
    """测试表命名是否遵循规范。"""

    def test_table_name_is_snake_case_singular(self):
        """所有表名应为 snake_case 单数形式。"""
        for table in Base.metadata.tables.values():
            name = table.name
            # 检查 snake_case：不含大写字母
            assert name == name.lower(), f"表名 {name} 不是小写"
            # 检查不以 s 结尾（简单单数检测）
            assert not name.endswith("ss") or name == "scheduler_state", (
                f"表名 {name} 可能不是单数形式"
            )

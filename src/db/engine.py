"""数据库引擎管理：异步引擎、WAL 模式、会话工厂。"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import ConfigManager
from src.log import get_logger

logger = get_logger(__name__)


def _set_wal_mode(dbapi_conn, connection_record):  # noqa: ANN001, ARG001
    """SQLite 连接建立后设置 WAL 模式。"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


class Database:
    """异步数据库管理器。

    负责创建异步引擎、设置 WAL 模式、提供会话工厂。

    使用方式::

        db = Database()
        await db.initialize()
        async with db.session() as session:
            ...
        await db.close()
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """获取异步引擎实例。"""
        if self._engine is None:
            raise RuntimeError("数据库未初始化，请先调用 initialize()")
        return self._engine

    async def initialize(self) -> None:
        """初始化数据库引擎和会话工厂。

        从 ConfigManager 读取数据库配置，创建异步引擎，
        设置 SQLite WAL 模式，并配置会话工厂。
        """
        config = ConfigManager.get_config()
        db_config = config.db
        url = db_config.url

        # 确保数据目录存在
        if "sqlite" in url:
            db_path = url.split("///")[-1] if "///" in url else None
            if db_path:
                # 相对路径基于项目根目录解析
                resolved = Path(db_path)
                if not resolved.is_absolute():
                    resolved = Path(config.data_dir) / resolved.name
                resolved.parent.mkdir(parents=True, exist_ok=True)
                # 更新 URL 使用绝对路径
                url = f"sqlite+aiosqlite:///{resolved}"

        self._engine = create_async_engine(
            url,
            echo=db_config.echo,
        )

        # 注册 WAL 模式设置事件
        event.listen(self._engine.sync_engine, "connect", _set_wal_mode)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # 验证连接并确认 WAL 模式
        async with self._engine.connect() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            logger.info("数据库初始化完成，WAL 模式: %s", mode)

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """获取异步数据库会话的上下文管理器。

        自动管理事务：正常退出时提交，异常时回滚。
        """
        if self._session_factory is None:
            raise RuntimeError("数据库未初始化，请先调用 initialize()")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """关闭数据库引擎，释放所有连接。"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("数据库连接已关闭")

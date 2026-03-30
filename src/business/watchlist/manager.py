"""自选股分组管理器：分组 CRUD 与股票增删。"""

from __future__ import annotations

from sqlalchemy import select

from src.business.watchlist.models import WatchlistGroup
from src.db.engine import Database
from src.log import get_logger

logger = get_logger(__name__)


class WatchlistManager:
    """自选股分组管理器。

    提供分组的创建、删除、查询，以及组内股票的添加和移除。
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    async def add_group(
        self,
        name: str,
        *,
        description: str = "",
        strategy: str = "default",
        push_frequency: str = "daily",
        stocks: list[str] | None = None,
    ) -> WatchlistGroup:
        """创建自选股分组。

        Args:
            name: 分组名称（唯一）
            description: 分组描述
            strategy: 分析策略
            push_frequency: 推送频率
            stocks: 初始股票列表

        Returns:
            创建的 WatchlistGroup 实例

        Raises:
            ValueError: 分组名称已存在
        """
        async with self._db.session() as session:
            existing = await session.execute(
                select(WatchlistGroup).where(WatchlistGroup.name == name)
            )
            if existing.scalar_one_or_none() is not None:
                raise ValueError(f"分组 '{name}' 已存在")

            group = WatchlistGroup(
                name=name,
                description=description,
                strategy=strategy,
                push_frequency=push_frequency,
            )
            group.stocks = stocks or []
            session.add(group)
            logger.info("创建自选股分组: %s", name)
            return group

    async def remove_group(self, name: str) -> bool:
        """删除自选股分组。

        Args:
            name: 分组名称

        Returns:
            是否成功删除（分组不存在时返回 False）
        """
        async with self._db.session() as session:
            result = await session.execute(
                select(WatchlistGroup).where(WatchlistGroup.name == name)
            )
            group = result.scalar_one_or_none()
            if group is None:
                logger.warning("要删除的分组不存在: %s", name)
                return False

            await session.delete(group)
            logger.info("删除自选股分组: %s", name)
            return True

    async def list_groups(self) -> list[WatchlistGroup]:
        """查询所有自选股分组。"""
        async with self._db.session() as session:
            result = await session.execute(
                select(WatchlistGroup).order_by(WatchlistGroup.id)
            )
            groups = list(result.scalars().all())
            return groups

    async def get_group(self, name: str) -> WatchlistGroup | None:
        """根据名称获取分组。"""
        async with self._db.session() as session:
            result = await session.execute(
                select(WatchlistGroup).where(WatchlistGroup.name == name)
            )
            return result.scalar_one_or_none()

    async def add_stock(self, group_name: str, stock_code: str) -> bool:
        """向分组中添加股票。

        Args:
            group_name: 分组名称
            stock_code: 股票代码

        Returns:
            是否成功添加（已存在或分组不存在时返回 False）
        """
        async with self._db.session() as session:
            result = await session.execute(
                select(WatchlistGroup).where(WatchlistGroup.name == group_name)
            )
            group = result.scalar_one_or_none()
            if group is None:
                logger.warning("分组不存在: %s", group_name)
                return False

            current_stocks = group.stocks
            if stock_code in current_stocks:
                logger.info("股票 %s 已在分组 %s 中", stock_code, group_name)
                return False

            current_stocks.append(stock_code)
            group.stocks = current_stocks
            logger.info("添加股票 %s 到分组 %s", stock_code, group_name)
            return True

    async def remove_stock(self, group_name: str, stock_code: str) -> bool:
        """从分组中移除股票。

        Args:
            group_name: 分组名称
            stock_code: 股票代码

        Returns:
            是否成功移除（不存在时返回 False）
        """
        async with self._db.session() as session:
            result = await session.execute(
                select(WatchlistGroup).where(WatchlistGroup.name == group_name)
            )
            group = result.scalar_one_or_none()
            if group is None:
                logger.warning("分组不存在: %s", group_name)
                return False

            current_stocks = group.stocks
            if stock_code not in current_stocks:
                logger.info("股票 %s 不在分组 %s 中", stock_code, group_name)
                return False

            current_stocks.remove(stock_code)
            group.stocks = current_stocks
            logger.info("从分组 %s 移除股票 %s", group_name, stock_code)
            return True

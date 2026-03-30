"""新闻数据源抽象基类与统一数据模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    """统一新闻数据模型。"""

    title: str
    source: str
    url: str = ""
    summary: str = ""
    published_at: datetime | None = None
    sentiment: float | None = None


class BaseNewsSource(ABC):
    """新闻数据源抽象基类。

    所有具体新闻源适配器必须继承此类并实现全部抽象方法。
    """

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[NewsItem]:
        """按关键词搜索新闻。

        Args:
            query: 搜索关键词
            limit: 返回数量上限

        Returns:
            NewsItem 列表
        """

    @abstractmethod
    async def get_stock_news(self, code: str, limit: int = 20) -> list[NewsItem]:
        """获取个股相关新闻。

        Args:
            code: 股票代码（如 "000001" 或 "AAPL.US"）
            limit: 返回数量上限

        Returns:
            NewsItem 列表
        """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称。"""

    @property
    @abstractmethod
    def requires_token(self) -> bool:
        """是否需要 token/凭证才能使用。"""

    async def is_available(self) -> bool:
        """检查数据源是否可用。

        默认实现：始终可用。需要 token 的源应覆盖此方法。
        """
        return True

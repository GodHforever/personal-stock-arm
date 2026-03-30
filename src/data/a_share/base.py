"""A股数据源抽象基类与统一数据模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class StockQuote(BaseModel):
    """实时行情数据模型。"""

    code: str
    name: str = ""
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    prev_close: float = 0.0
    timestamp: datetime | None = None


class KlineBar(BaseModel):
    """K线数据模型。"""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0


class Fundamentals(BaseModel):
    """基本面数据模型。"""

    code: str
    name: str = ""
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    total_shares: float | None = None
    float_shares: float | None = None
    revenue: float | None = None
    net_profit: float | None = None


class DataUnavailableError(Exception):
    """所有数据源均不可用时抛出的异常。

    Attributes:
        errors: 各数据源的错误详情列表
    """

    def __init__(self, message: str, errors: list[dict[str, str]] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class BaseDataFetcher(ABC):
    """A股数据源抽象基类。

    所有具体数据源适配器必须继承此类并实现全部抽象方法。
    """

    @abstractmethod
    async def get_realtime_quote(self, code: str) -> StockQuote:
        """获取实时行情。

        Args:
            code: 股票代码（如 "000001"）

        Returns:
            StockQuote 实时行情数据
        """

    @abstractmethod
    async def get_kline(self, code: str, period: str, count: int) -> list[KlineBar]:
        """获取K线数据。

        Args:
            code: 股票代码
            period: K线周期（如 "daily", "weekly", "monthly"）
            count: 获取数量

        Returns:
            KlineBar 列表
        """

    @abstractmethod
    async def get_fundamentals(self, code: str) -> Fundamentals:
        """获取基本面数据。

        Args:
            code: 股票代码

        Returns:
            Fundamentals 基本面数据
        """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称。"""

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级，数值越小优先级越高。"""

    @property
    @abstractmethod
    def requires_token(self) -> bool:
        """是否需要 token 才能使用。"""

    async def is_available(self) -> bool:
        """检查数据源是否可用。

        默认实现：不需要 token 的源始终可用；需要 token 的源需子类覆盖此方法。
        """
        return True

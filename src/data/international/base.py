"""国际市场数据源抽象基类与统一数据模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class IntlQuote(BaseModel):
    """国际市场实时行情数据模型。"""

    symbol: str
    name: str = ""
    market: str = ""
    currency: str = ""
    price: float
    change: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0
    turnover: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    prev_close: float = 0.0
    timestamp: datetime | None = None


class IntlKlineBar(BaseModel):
    """国际市场K线数据模型。"""

    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    turnover: float = 0.0


# 支持的市场列表
SUPPORTED_MARKETS = {"US", "HK", "SG"}

# 主要国际指数 symbol 列表
MAJOR_INDICES = [
    ".DJI.US",      # 道琼斯工业平均指数
    ".SPX.US",      # 标普500指数
    ".IXIC.US",     # 纳斯达克综合指数
    ".HSI.HK",      # 恒生指数
    ".HSTECH.HK",   # 恒生科技指数
]


def parse_symbol(symbol: str) -> tuple[str, str]:
    """解析 CODE.MARKET 格式的 symbol。

    Args:
        symbol: 股票代码，如 "AAPL.US"、"700.HK"

    Returns:
        (code, market) 元组

    Raises:
        ValueError: symbol 格式不正确
    """
    parts = symbol.rsplit(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"无效的 symbol 格式: {symbol!r}，应为 CODE.MARKET（如 AAPL.US）")
    code, market = parts[0], parts[1].upper()
    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"不支持的市场: {market!r}，支持的市场: {', '.join(sorted(SUPPORTED_MARKETS))}"
        )
    return code, market


class BaseIntlFetcher(ABC):
    """国际市场数据源抽象基类。

    所有具体国际市场数据源适配器必须继承此类并实现全部抽象方法。
    """

    @abstractmethod
    async def get_quote(self, symbol: str) -> IntlQuote:
        """获取实时行情。

        Args:
            symbol: 股票代码（如 "AAPL.US"）

        Returns:
            IntlQuote 实时行情数据
        """

    @abstractmethod
    async def get_kline(
        self, symbol: str, period: str = "daily", count: int = 100
    ) -> list[IntlKlineBar]:
        """获取K线数据。

        Args:
            symbol: 股票代码
            period: K线周期（如 "daily", "weekly", "monthly"）
            count: 获取数量

        Returns:
            IntlKlineBar 列表
        """

    @abstractmethod
    async def get_market_indices(self) -> list[IntlQuote]:
        """获取主要国际指数行情。

        Returns:
            主要指数的 IntlQuote 列表
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
    def supported_markets(self) -> set[str]:
        """支持的市场列表（如 {"US", "HK", "SG"}）。"""

    def supports_market(self, market: str) -> bool:
        """检查是否支持指定市场。"""
        return market.upper() in self.supported_markets

    async def is_available(self) -> bool:
        """检查数据源是否可用。默认返回 True，子类可覆盖。"""
        return True

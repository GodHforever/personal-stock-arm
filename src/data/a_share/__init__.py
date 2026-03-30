"""A股数据源适配器：多源 failover 数据获取。"""

from __future__ import annotations

from src.data.a_share.base import (
    BaseDataFetcher,
    DataUnavailableError,
    Fundamentals,
    KlineBar,
    StockQuote,
)
from src.data.a_share.manager import DataFetcherManager

__all__ = [
    "BaseDataFetcher",
    "DataFetcherManager",
    "DataUnavailableError",
    "Fundamentals",
    "KlineBar",
    "StockQuote",
]

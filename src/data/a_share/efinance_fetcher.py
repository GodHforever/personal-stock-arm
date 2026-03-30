"""efinance 数据源适配器。"""

from __future__ import annotations

import asyncio
from datetime import datetime

from src.data.a_share.base import BaseDataFetcher, Fundamentals, KlineBar, StockQuote
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

_PERIOD_MAP = {
    "daily": 101,
    "weekly": 102,
    "monthly": 103,
}


class EfinanceFetcher(BaseDataFetcher):
    """efinance 数据源适配器（优先级 0，无需 token）。"""

    @property
    def source_name(self) -> str:
        return "efinance"

    @property
    def priority(self) -> int:
        return 0

    @property
    def requires_token(self) -> bool:
        return False

    async def is_available(self) -> bool:
        """检查 efinance 库是否可导入。"""
        try:
            import efinance  # noqa: F401  # type: ignore[import-untyped]
            return True
        except ImportError:
            return False

    async def get_realtime_quote(self, code: str) -> StockQuote:
        """通过 efinance 获取实时行情。"""
        try:
            import efinance as ef  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="efinance 库未安装",
                suggestion="运行 pip install efinance 安装",
            ) from exc

        try:
            df = await asyncio.to_thread(ef.stock.get_quote_history, code, klt=101)
            if df is None or df.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取行情",
                    url="",
                    error_type="EmptyData",
                    error_msg=f"未获取到 {code} 的行情数据",
                    suggestion="检查股票代码是否正确",
                )

            # efinance 返回的是历史数据，取最后一行作为最新行情
            latest = df.iloc[-1]
            return StockQuote(
                code=code,
                name=str(latest.get("股票名称", "")),
                price=float(latest.get("收盘", 0)),
                change=float(latest.get("涨跌额", 0)),
                change_pct=float(latest.get("涨跌幅", 0)),
                volume=float(latest.get("成交量", 0)),
                amount=float(latest.get("成交额", 0)),
                high=float(latest.get("最高", 0)),
                low=float(latest.get("最低", 0)),
                open=float(latest.get("开盘", 0)),
                timestamp=datetime.now(),
            )
        except DataSourceError:
            raise
        except Exception as exc:
            raise DataSourceError(
                source=self.source_name,
                step="获取行情",
                url="",
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或稍后重试",
            ) from exc

    async def get_kline(self, code: str, period: str, count: int) -> list[KlineBar]:
        """通过 efinance 获取K线数据。"""
        try:
            import efinance as ef  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="efinance 库未安装",
                suggestion="运行 pip install efinance 安装",
            ) from exc

        klt = _PERIOD_MAP.get(period, 101)
        try:
            df = await asyncio.to_thread(ef.stock.get_quote_history, code, klt=klt)
            if df is None or df.empty:
                return []

            df = df.tail(count)
            bars: list[KlineBar] = []
            for _, row in df.iterrows():
                bars.append(
                    KlineBar(
                        date=str(row.get("日期", "")),
                        open=float(row.get("开盘", 0)),
                        high=float(row.get("最高", 0)),
                        low=float(row.get("最低", 0)),
                        close=float(row.get("收盘", 0)),
                        volume=float(row.get("成交量", 0)),
                        amount=float(row.get("成交额", 0)),
                    )
                )
            return bars
        except Exception as exc:
            raise DataSourceError(
                source=self.source_name,
                step="获取K线",
                url="",
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或稍后重试",
            ) from exc

    async def get_fundamentals(self, code: str) -> Fundamentals:
        """efinance 不提供完整基本面数据，抛出异常由 Manager 切换到其他源。"""
        raise DataSourceError(
            source=self.source_name,
            step="获取基本面",
            url="",
            error_type="NotSupported",
            error_msg="efinance 不支持基本面数据查询",
            suggestion="使用其他数据源（如 AkShare、Baostock）获取基本面数据",
        )

"""AkShare 数据源适配器。"""

from __future__ import annotations

import asyncio
from datetime import datetime

from src.data.a_share.base import BaseDataFetcher, Fundamentals, KlineBar, StockQuote
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

_PERIOD_MAP = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
}


class AkshareFetcher(BaseDataFetcher):
    """AkShare 数据源适配器（优先级 1，无需 token）。"""

    @property
    def source_name(self) -> str:
        return "akshare"

    @property
    def priority(self) -> int:
        return 1

    @property
    def requires_token(self) -> bool:
        return False

    async def is_available(self) -> bool:
        """检查 akshare 库是否可导入。"""
        try:
            import akshare  # noqa: F401  # type: ignore[import-untyped]
            return True
        except ImportError:
            return False

    async def get_realtime_quote(self, code: str) -> StockQuote:
        """通过 AkShare 获取实时行情。"""
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="akshare 库未安装",
                suggestion="运行 pip install akshare 安装",
            ) from exc

        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            if df is None or df.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取行情",
                    url="",
                    error_type="EmptyData",
                    error_msg="未获取到A股行情数据",
                    suggestion="检查网络连接或稍后重试",
                )

            # 按股票代码筛选
            row = df[df["代码"] == code]
            if row.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取行情",
                    url="",
                    error_type="NotFound",
                    error_msg=f"未找到股票 {code}",
                    suggestion="检查股票代码是否正确",
                )

            r = row.iloc[0]
            return StockQuote(
                code=code,
                name=str(r.get("名称", "")),
                price=float(r.get("最新价", 0) or 0),
                change=float(r.get("涨跌额", 0) or 0),
                change_pct=float(r.get("涨跌幅", 0) or 0),
                volume=float(r.get("成交量", 0) or 0),
                amount=float(r.get("成交额", 0) or 0),
                high=float(r.get("最高", 0) or 0),
                low=float(r.get("最低", 0) or 0),
                open=float(r.get("开盘", 0) or 0),
                prev_close=float(r.get("昨收", 0) or 0),
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
        """通过 AkShare 获取K线数据。"""
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="akshare 库未安装",
                suggestion="运行 pip install akshare 安装",
            ) from exc

        ak_period = _PERIOD_MAP.get(period, "daily")
        try:
            df = await asyncio.to_thread(
                ak.stock_zh_a_hist,
                symbol=code,
                period=ak_period,
                adjust="qfq",
            )
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
        """通过 AkShare 获取基本面数据。"""
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="akshare 库未安装",
                suggestion="运行 pip install akshare 安装",
            ) from exc

        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            if df is None or df.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取基本面",
                    url="",
                    error_type="EmptyData",
                    error_msg="未获取到A股数据",
                    suggestion="检查网络连接或稍后重试",
                )

            row = df[df["代码"] == code]
            if row.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取基本面",
                    url="",
                    error_type="NotFound",
                    error_msg=f"未找到股票 {code}",
                    suggestion="检查股票代码是否正确",
                )

            r = row.iloc[0]
            return Fundamentals(
                code=code,
                name=str(r.get("名称", "")),
                pe_ttm=float(r["市盈率-动态"]) if r.get("市盈率-动态") else None,
                pb=float(r["市净率"]) if r.get("市净率") else None,
                market_cap=float(r["总市值"]) if r.get("总市值") else None,
                float_shares=float(r["流通市值"]) if r.get("流通市值") else None,
            )
        except DataSourceError:
            raise
        except Exception as exc:
            raise DataSourceError(
                source=self.source_name,
                step="获取基本面",
                url="",
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或稍后重试",
            ) from exc

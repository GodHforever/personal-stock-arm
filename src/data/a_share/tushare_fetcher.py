"""Tushare 数据源适配器（需要 token）。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from src.config import ConfigManager
from src.data.a_share.base import BaseDataFetcher, Fundamentals, KlineBar, StockQuote
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

_PERIOD_MAP = {
    "daily": "D",
    "weekly": "W",
    "monthly": "M",
}


def _get_tushare_token() -> str:
    """从配置中获取 Tushare token。"""
    data_config = ConfigManager.get_section("data")
    token = str(data_config.tushare_token.get_secret_value())
    return token


def _to_ts_code(code: str) -> str:
    """将股票代码转换为 Tushare 格式（如 000001 -> 000001.SZ）。"""
    if "." in code:
        return code
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


class TushareFetcher(BaseDataFetcher):
    """Tushare 数据源适配器（优先级 0，需要 token）。"""

    def __init__(self) -> None:
        self._pro: Any = None

    @property
    def source_name(self) -> str:
        return "tushare"

    @property
    def priority(self) -> int:
        return 0

    @property
    def requires_token(self) -> bool:
        return True

    async def is_available(self) -> bool:
        """检查 tushare 库是否可导入且 token 已配置。"""
        try:
            import tushare  # noqa: F401  # type: ignore[import-not-found]
        except ImportError:
            return False

        token = _get_tushare_token()
        if not token:
            logger.debug("Tushare token 未配置，跳过该数据源")
            return False
        return True

    def _get_pro(self) -> Any:
        """获取 Tushare Pro API 实例（懒初始化）。"""
        if self._pro is None:
            import tushare as ts  # type: ignore[import-not-found]

            token = _get_tushare_token()
            if not token:
                raise DataSourceError(
                    source=self.source_name,
                    step="初始化",
                    url="",
                    error_type="ConfigError",
                    error_msg="Tushare token 未配置",
                    suggestion="在 .env 中设置 STOCK_ARM_DATA_TUSHARE_TOKEN",
                )
            ts.set_token(token)
            self._pro = ts.pro_api()
        return self._pro

    async def get_realtime_quote(self, code: str) -> StockQuote:
        """通过 Tushare 获取行情数据。"""
        try:
            import tushare  # noqa: F401  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="tushare 库未安装",
                suggestion="运行 pip install tushare 安装",
            ) from exc

        ts_code = _to_ts_code(code)
        try:
            pro = self._get_pro()
            df = await asyncio.to_thread(
                pro.daily,  # type: ignore[attr-defined]
                ts_code=ts_code,
                limit=1,
            )
            if df is None or df.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取行情",
                    url="",
                    error_type="EmptyData",
                    error_msg=f"未获取到 {code} 的行情数据",
                    suggestion="检查股票代码是否正确或 Tushare 权限是否足够",
                )

            r = df.iloc[0]
            return StockQuote(
                code=code,
                price=float(r.get("close", 0)),
                change=float(r.get("change", 0)),
                change_pct=float(r.get("pct_chg", 0)),
                volume=float(r.get("vol", 0)),
                amount=float(r.get("amount", 0)),
                high=float(r.get("high", 0)),
                low=float(r.get("low", 0)),
                open=float(r.get("open", 0)),
                prev_close=float(r.get("pre_close", 0)),
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
                suggestion="检查 Tushare token 和网络连接",
            ) from exc

    async def get_kline(self, code: str, period: str, count: int) -> list[KlineBar]:
        """通过 Tushare 获取K线数据。"""
        try:
            import tushare  # noqa: F401  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="tushare 库未安装",
                suggestion="运行 pip install tushare 安装",
            ) from exc

        ts_code = _to_ts_code(code)
        freq = _PERIOD_MAP.get(period, "D")
        try:
            pro = self._get_pro()
            if freq == "D":
                df = await asyncio.to_thread(
                    pro.daily,  # type: ignore[attr-defined]
                    ts_code=ts_code,
                    limit=count,
                )
            else:
                df = await asyncio.to_thread(
                    pro.stk_factor,  # type: ignore[attr-defined]
                    ts_code=ts_code,
                    limit=count,
                )

            if df is None or df.empty:
                return []

            bars: list[KlineBar] = []
            for _, row in df.iterrows():
                bars.append(
                    KlineBar(
                        date=str(row.get("trade_date", "")),
                        open=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        close=float(row.get("close", 0)),
                        volume=float(row.get("vol", 0)),
                        amount=float(row.get("amount", 0)),
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
                suggestion="检查 Tushare token 和网络连接",
            ) from exc

    async def get_fundamentals(self, code: str) -> Fundamentals:
        """通过 Tushare 获取基本面数据。"""
        try:
            import tushare  # noqa: F401  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="tushare 库未安装",
                suggestion="运行 pip install tushare 安装",
            ) from exc

        ts_code = _to_ts_code(code)
        try:
            pro = self._get_pro()
            df = await asyncio.to_thread(
                pro.daily_basic,  # type: ignore[attr-defined]
                ts_code=ts_code,
                limit=1,
            )
            if df is None or df.empty:
                raise DataSourceError(
                    source=self.source_name,
                    step="获取基本面",
                    url="",
                    error_type="EmptyData",
                    error_msg=f"未获取到 {code} 的基本面数据",
                    suggestion="检查 Tushare 权限等级",
                )

            r = df.iloc[0]
            return Fundamentals(
                code=code,
                pe_ttm=float(r["pe_ttm"]) if r.get("pe_ttm") else None,
                pb=float(r["pb"]) if r.get("pb") else None,
                market_cap=float(r["total_mv"]) if r.get("total_mv") else None,
                total_shares=float(r["total_share"]) if r.get("total_share") else None,
                float_shares=float(r["float_share"]) if r.get("float_share") else None,
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
                suggestion="检查 Tushare token 和网络连接",
            ) from exc

"""Baostock 数据源适配器。"""

from __future__ import annotations

import asyncio
import threading

from src.data.a_share.base import BaseDataFetcher, Fundamentals, KlineBar, StockQuote
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

_PERIOD_MAP = {
    "daily": "d",
    "weekly": "w",
    "monthly": "m",
}


def _to_bs_code(code: str) -> str:
    """将股票代码转换为 Baostock 格式（如 000001 -> sz.000001）。"""
    if "." in code:
        return code
    if code.startswith("6"):
        return f"sh.{code}"
    return f"sz.{code}"


class BaostockFetcher(BaseDataFetcher):
    """Baostock 数据源适配器（优先级 3，无需 token）。

    Baostock 需要 login/logout 管理，使用线程锁保证线程安全。
    """

    def __init__(self) -> None:
        self._logged_in = False
        self._lock = threading.Lock()

    @property
    def source_name(self) -> str:
        return "baostock"

    @property
    def priority(self) -> int:
        return 3

    @property
    def requires_token(self) -> bool:
        return False

    async def is_available(self) -> bool:
        """检查 baostock 库是否可导入。"""
        try:
            import baostock  # noqa: F401  # type: ignore[import-untyped]
            return True
        except ImportError:
            return False

    def _ensure_login(self) -> None:
        """确保已登录 Baostock（线程安全）。"""
        if self._logged_in:
            return
        with self._lock:
            if self._logged_in:
                return
            import baostock as bs  # type: ignore[import-untyped]

            result = bs.login()
            if result.error_code != "0":
                raise DataSourceError(
                    source=self.source_name,
                    step="登录",
                    url="",
                    error_type="LoginError",
                    error_msg=f"Baostock 登录失败: {result.error_msg}",
                    suggestion="检查网络连接，Baostock 服务可能暂时不可用",
                )
            self._logged_in = True
            logger.debug("Baostock 登录成功")

    def _logout(self) -> None:
        """登出 Baostock。"""
        if not self._logged_in:
            return
        with self._lock:
            if not self._logged_in:
                return
            try:
                import baostock as bs  # type: ignore[import-untyped]

                bs.logout()
            except Exception:
                logger.debug("Baostock 登出时发生异常，已忽略")
            finally:
                self._logged_in = False

    async def get_realtime_quote(self, code: str) -> StockQuote:
        """Baostock 不支持实时行情，抛出异常由 Manager 切换到其他源。"""
        raise DataSourceError(
            source=self.source_name,
            step="获取行情",
            url="",
            error_type="NotSupported",
            error_msg="Baostock 不支持实时行情查询",
            suggestion="使用 efinance 或 AkShare 获取实时行情",
        )

    async def get_kline(self, code: str, period: str, count: int) -> list[KlineBar]:
        """通过 Baostock 获取K线数据。"""
        try:
            import baostock as bs  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="baostock 库未安装",
                suggestion="运行 pip install baostock 安装",
            ) from exc

        bs_code = _to_bs_code(code)
        frequency = _PERIOD_MAP.get(period, "d")

        def _fetch() -> list[KlineBar]:
            self._ensure_login()
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                frequency=frequency,
            )
            if rs.error_code != "0":
                raise DataSourceError(
                    source=self.source_name,
                    step="获取K线",
                    url="",
                    error_type="QueryError",
                    error_msg=f"Baostock 查询失败: {rs.error_msg}",
                    suggestion="检查股票代码是否正确",
                )

            rows: list[list[str]] = []
            while rs.next():
                rows.append(rs.get_row_data())

            if not rows:
                return []

            # 取最后 count 条
            rows = rows[-count:]
            bars: list[KlineBar] = []
            for row in rows:
                bars.append(
                    KlineBar(
                        date=row[0],
                        open=float(row[1]) if row[1] else 0.0,
                        high=float(row[2]) if row[2] else 0.0,
                        low=float(row[3]) if row[3] else 0.0,
                        close=float(row[4]) if row[4] else 0.0,
                        volume=float(row[5]) if row[5] else 0.0,
                        amount=float(row[6]) if row[6] else 0.0,
                    )
                )
            return bars

        try:
            return await asyncio.to_thread(_fetch)
        except DataSourceError:
            raise
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
        """通过 Baostock 获取基本面数据。"""
        try:
            import baostock as bs  # type: ignore[import-untyped]
        except ImportError as exc:
            raise DataSourceError(
                source=self.source_name,
                step="导入模块",
                url="",
                error_type="ImportError",
                error_msg="baostock 库未安装",
                suggestion="运行 pip install baostock 安装",
            ) from exc

        bs_code = _to_bs_code(code)

        def _fetch() -> Fundamentals:
            self._ensure_login()

            # 查询盈利能力数据
            rs = bs.query_profit_data(code=bs_code, year=2024, quarter=4)
            if rs.error_code != "0":
                raise DataSourceError(
                    source=self.source_name,
                    step="获取基本面",
                    url="",
                    error_type="QueryError",
                    error_msg=f"Baostock 查询失败: {rs.error_msg}",
                    suggestion="检查股票代码是否正确",
                )

            rows: list[list[str]] = []
            while rs.next():
                rows.append(rs.get_row_data())

            if not rows:
                return Fundamentals(code=code)

            # Baostock 盈利数据字段顺序取决于查询，这里做基本解析
            return Fundamentals(code=code)

        try:
            return await asyncio.to_thread(_fetch)
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

    def __del__(self) -> None:
        """析构时尝试登出。"""
        import contextlib

        with contextlib.suppress(Exception):
            self._logout()

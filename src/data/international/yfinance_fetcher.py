"""yfinance 数据源适配器：美股市场 fallback 数据源。"""

from __future__ import annotations

import asyncio
from datetime import datetime

from src.data.international.base import (
    BaseIntlFetcher,
    IntlKlineBar,
    IntlQuote,
    parse_symbol,
)
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

# yfinance 可选导入
try:
    import yfinance as yf  # type: ignore[import-untyped]

    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False

# K线周期映射: 内部周期 -> yfinance interval
_PERIOD_MAP = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
}

# 周期对应的数据范围: count -> yfinance period 字符串
_COUNT_TO_RANGE = {
    "daily": lambda count: f"{min(count, 730)}d",
    "weekly": lambda count: f"{min(count * 7, 3650)}d",
    "monthly": lambda count: f"{min(count, 120)}mo",
}


def _yf_symbol(symbol: str) -> str:
    """将 CODE.MARKET 转换为 yfinance 格式。

    yfinance 使用不同的 symbol 格式，美股直接用代码即可。
    """
    code, _ = parse_symbol(symbol)
    return code


class YFinanceFetcher(BaseIntlFetcher):
    """yfinance 数据源适配器。

    仅支持 US 市场，同步库通过 asyncio.to_thread 包装为 async。
    作为 Longbridge 不可用时的 fallback。
    """

    async def get_quote(self, symbol: str) -> IntlQuote:
        """获取实时行情（通过 yfinance 的 fast_info）。"""
        _, market = parse_symbol(symbol)
        if market != "US":
            raise DataSourceError(
                step="获取行情",
                source=self.source_name,
                url=symbol,
                error_type="市场不支持",
                error_msg=f"yfinance fallback 仅支持 US 市场，不支持 {market}",
                suggestion="使用 Longbridge 数据源获取非美股数据",
            )

        try:
            info = await asyncio.to_thread(self._fetch_quote_sync, symbol)
            return info
        except DataSourceError:
            raise
        except Exception as exc:
            raise DataSourceError(
                step="获取行情",
                source=self.source_name,
                url=symbol,
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或 yfinance 服务状态",
            ) from exc

    def _fetch_quote_sync(self, symbol: str) -> IntlQuote:
        """同步获取行情数据。"""
        yf_sym = _yf_symbol(symbol)
        ticker = yf.Ticker(yf_sym)
        info = ticker.fast_info

        price = float(getattr(info, "last_price", 0) or 0)
        prev_close = float(getattr(info, "previous_close", 0) or 0)
        change = price - prev_close
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0

        return IntlQuote(
            symbol=symbol,
            name=yf_sym,
            market="US",
            currency="USD",
            price=price,
            change=change,
            change_pct=change_pct,
            volume=float(getattr(info, "last_volume", 0) or 0),
            turnover=0.0,
            high=float(getattr(info, "day_high", 0) or 0),
            low=float(getattr(info, "day_low", 0) or 0),
            open=float(getattr(info, "open", 0) or 0),
            prev_close=prev_close,
            timestamp=datetime.now(),
        )

    async def get_kline(
        self, symbol: str, period: str = "daily", count: int = 100
    ) -> list[IntlKlineBar]:
        """获取K线数据。"""
        _, market = parse_symbol(symbol)
        if market != "US":
            raise DataSourceError(
                step="获取K线",
                source=self.source_name,
                url=symbol,
                error_type="市场不支持",
                error_msg=f"yfinance fallback 仅支持 US 市场，不支持 {market}",
                suggestion="使用 Longbridge 数据源获取非美股数据",
            )

        if period not in _PERIOD_MAP:
            raise DataSourceError(
                step="获取K线",
                source=self.source_name,
                url=symbol,
                error_type="参数错误",
                error_msg=f"不支持的K线周期: {period!r}",
                suggestion=f"支持的周期: {', '.join(_PERIOD_MAP.keys())}",
            )

        try:
            bars = await asyncio.to_thread(
                self._fetch_kline_sync, symbol, period, count
            )
            return bars
        except DataSourceError:
            raise
        except Exception as exc:
            raise DataSourceError(
                step="获取K线",
                source=self.source_name,
                url=symbol,
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或 yfinance 服务状态",
            ) from exc

    def _fetch_kline_sync(
        self, symbol: str, period: str, count: int
    ) -> list[IntlKlineBar]:
        """同步获取K线数据。"""
        yf_sym = _yf_symbol(symbol)
        interval = _PERIOD_MAP[period]
        yf_period = _COUNT_TO_RANGE[period](count)

        ticker = yf.Ticker(yf_sym)
        df = ticker.history(period=yf_period, interval=interval)

        if df is None or df.empty:
            return []

        bars: list[IntlKlineBar] = []
        for idx, row in df.tail(count).iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
            bars.append(
                IntlKlineBar(
                    symbol=symbol,
                    date=date_str,
                    open=float(row.get("Open", 0) or 0),
                    high=float(row.get("High", 0) or 0),
                    low=float(row.get("Low", 0) or 0),
                    close=float(row.get("Close", 0) or 0),
                    volume=float(row.get("Volume", 0) or 0),
                    turnover=0.0,
                )
            )
        return bars

    async def get_market_indices(self) -> list[IntlQuote]:
        """获取主要国际指数行情。

        yfinance 支持部分指数，但作为 fallback 仅提供有限支持。
        """
        yf_indices = {
            "^DJI": ".DJI.US",
            "^GSPC": ".SPX.US",
            "^IXIC": ".IXIC.US",
            "^HSI": ".HSI.HK",
        }

        try:
            results = await asyncio.to_thread(
                self._fetch_indices_sync, yf_indices
            )
            return results
        except DataSourceError:
            raise
        except Exception as exc:
            raise DataSourceError(
                step="获取指数",
                source=self.source_name,
                url="INDICES",
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或 yfinance 服务状态",
            ) from exc

    def _fetch_indices_sync(
        self, yf_indices: dict[str, str]
    ) -> list[IntlQuote]:
        """同步获取指数数据。"""
        results: list[IntlQuote] = []
        for yf_sym, intl_sym in yf_indices.items():
            try:
                ticker = yf.Ticker(yf_sym)
                info = ticker.fast_info
                price = float(getattr(info, "last_price", 0) or 0)
                prev_close = float(getattr(info, "previous_close", 0) or 0)
                _, market = parse_symbol(intl_sym)
                results.append(
                    IntlQuote(
                        symbol=intl_sym,
                        name=yf_sym,
                        market=market,
                        price=price,
                        change=price - prev_close,
                        change_pct=round(
                            (price - prev_close) / prev_close * 100, 2
                        )
                        if prev_close
                        else 0.0,
                        prev_close=prev_close,
                        timestamp=datetime.now(),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "yfinance 获取指数 %s 失败: %s", yf_sym, exc
                )
        return results

    @property
    def source_name(self) -> str:
        return "yfinance"

    @property
    def priority(self) -> int:
        return 1

    @property
    def supported_markets(self) -> set[str]:
        return {"US"}

    async def is_available(self) -> bool:
        """检查 yfinance 是否可用。"""
        return _HAS_YFINANCE

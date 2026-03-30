"""Longbridge 数据源适配器：国际市场主数据源。"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from src.config import ConfigManager
from src.data.international.base import (
    MAJOR_INDICES,
    BaseIntlFetcher,
    IntlKlineBar,
    IntlQuote,
    parse_symbol,
)
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)

# Longbridge SDK 可选导入
try:
    from longbridge.openapi import (  # type: ignore[import-untyped,attr-defined]
        AdjustType,
        AsyncQuoteContext,
        Config,
        OAuthBuilder,
        OpenApiException,
        Period,
    )

    _HAS_LONGBRIDGE = True
except ImportError:
    _HAS_LONGBRIDGE = False

# K线周期映射
_PERIOD_MAP: dict[str, object] = {}
if _HAS_LONGBRIDGE:
    _PERIOD_MAP = {
        "daily": Period.Day,
        "weekly": Period.Week,
        "monthly": Period.Month,
        "1min": Period.Min_1,
        "5min": Period.Min_5,
        "15min": Period.Min_15,
        "30min": Period.Min_30,
        "60min": Period.Min_60,
    }


def _get_longbridge_client_id() -> str:
    """从配置中获取 Longbridge OAuth client_id。"""
    data_config = ConfigManager.get_section("data")
    return str(getattr(data_config, "longbridge_client_id", ""))


class LongbridgeFetcher(BaseIntlFetcher):
    """Longbridge SDK 数据源适配器。

    使用 AsyncQuoteContext 获取 US/HK/SG 市场数据。
    内置 rate limit 控制（10 calls/second）。
    """

    def __init__(self) -> None:
        self._ctx: AsyncQuoteContext | None = None
        self._config: Config | None = None
        self._initialized = False
        # Rate limit: 最多 10 次/秒
        self._max_calls_per_second = 10
        self._call_timestamps: list[float] = []

    async def _ensure_initialized(self) -> None:
        """确保 SDK 已初始化。"""
        if self._initialized and self._ctx is not None:
            return

        client_id = _get_longbridge_client_id()
        if not client_id:
            raise DataSourceError(
                step="初始化",
                source=self.source_name,
                url="",
                error_type="配置缺失",
                error_msg="未配置 Longbridge OAuth client_id",
                suggestion="请在配置中设置 STOCK_ARM_DATA_LONGBRIDGE_CLIENT_ID",
            )

        try:
            oauth = await OAuthBuilder(client_id).build_async(
                lambda url: logger.info("Longbridge OAuth 授权链接: %s", url)
            )
            self._config = Config.from_oauth(oauth)  # type: ignore[attr-defined]
            self._ctx = AsyncQuoteContext.create(self._config)
            self._initialized = True
            logger.info("Longbridge SDK 初始化成功")
        except Exception as exc:
            raise DataSourceError(
                step="初始化",
                source=self.source_name,
                url="",
                error_type="SDK初始化失败",
                error_msg=str(exc),
                suggestion="检查 Longbridge OAuth 凭证是否有效",
            ) from exc

    async def _rate_limit(self) -> None:
        """限流控制：确保每秒不超过 10 次调用。"""
        now = time.monotonic()
        # 清理超过1秒的记录
        self._call_timestamps = [
            ts for ts in self._call_timestamps if now - ts < 1.0
        ]
        if len(self._call_timestamps) >= self._max_calls_per_second:
            # 等待直到最早的调用超过1秒
            wait_time = 1.0 - (now - self._call_timestamps[0])
            if wait_time > 0:
                logger.debug("Longbridge 限流等待 %.3f 秒", wait_time)
                await asyncio.sleep(wait_time)
        self._call_timestamps.append(time.monotonic())

    async def get_quote(self, symbol: str) -> IntlQuote:
        """获取实时行情。"""
        parse_symbol(symbol)  # 验证 symbol 格式
        await self._ensure_initialized()
        await self._rate_limit()
        assert self._ctx is not None

        try:
            quotes = await self._ctx.quote([symbol])
            if not quotes:
                raise DataSourceError(
                    step="获取行情",
                    source=self.source_name,
                    url=symbol,
                    error_type="数据为空",
                    error_msg=f"未获取到 {symbol} 的行情数据",
                    suggestion="检查 symbol 是否正确",
                )

            q = quotes[0]
            _, market = parse_symbol(symbol)
            return IntlQuote(
                symbol=symbol,
                name=getattr(q, "name_en", "") or "",
                market=market,
                currency=getattr(q, "currency", "") or "",
                price=float(getattr(q, "last_done", 0) or 0),
                change=float(getattr(q, "last_done", 0) or 0)
                - float(getattr(q, "prev_close_price", 0) or 0),
                change_pct=_calc_change_pct(
                    float(getattr(q, "last_done", 0) or 0),
                    float(getattr(q, "prev_close_price", 0) or 0),
                ),
                volume=float(getattr(q, "volume", 0) or 0),
                turnover=float(getattr(q, "turnover", 0) or 0),
                high=float(getattr(q, "high", 0) or 0),
                low=float(getattr(q, "low", 0) or 0),
                open=float(getattr(q, "open", 0) or 0),
                prev_close=float(getattr(q, "prev_close_price", 0) or 0),
                timestamp=datetime.now(),
            )
        except DataSourceError:
            raise
        except OpenApiException as exc:
            raise DataSourceError(
                step="获取行情",
                source=self.source_name,
                url=symbol,
                error_type="API错误",
                error_msg=f"code={exc.code}, message={exc.message}",
                suggestion="检查 Longbridge API 状态",
            ) from exc
        except Exception as exc:
            raise DataSourceError(
                step="获取行情",
                source=self.source_name,
                url=symbol,
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或 Longbridge 服务状态",
            ) from exc

    async def get_kline(
        self, symbol: str, period: str = "daily", count: int = 100
    ) -> list[IntlKlineBar]:
        """获取K线数据。"""
        parse_symbol(symbol)
        await self._ensure_initialized()
        await self._rate_limit()
        assert self._ctx is not None

        lb_period = _PERIOD_MAP.get(period)
        if lb_period is None:
            raise DataSourceError(
                step="获取K线",
                source=self.source_name,
                url=symbol,
                error_type="参数错误",
                error_msg=f"不支持的K线周期: {period!r}",
                suggestion=f"支持的周期: {', '.join(_PERIOD_MAP.keys())}",
            )

        try:
            candlesticks = await self._ctx.candlesticks(
                symbol, lb_period, count, AdjustType.ForwardAdjust
            )
            bars: list[IntlKlineBar] = []
            for c in candlesticks:
                ts = getattr(c, "timestamp", None)
                date_str = ts.strftime("%Y-%m-%d") if ts else ""
                bars.append(
                    IntlKlineBar(
                        symbol=symbol,
                        date=date_str,
                        open=float(getattr(c, "open", 0) or 0),
                        high=float(getattr(c, "high", 0) or 0),
                        low=float(getattr(c, "low", 0) or 0),
                        close=float(getattr(c, "close", 0) or 0),
                        volume=float(getattr(c, "volume", 0) or 0),
                        turnover=float(getattr(c, "turnover", 0) or 0),
                    )
                )
            return bars
        except DataSourceError:
            raise
        except OpenApiException as exc:
            raise DataSourceError(
                step="获取K线",
                source=self.source_name,
                url=symbol,
                error_type="API错误",
                error_msg=f"code={exc.code}, message={exc.message}",
                suggestion="检查 Longbridge API 状态",
            ) from exc
        except Exception as exc:
            raise DataSourceError(
                step="获取K线",
                source=self.source_name,
                url=symbol,
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或 Longbridge 服务状态",
            ) from exc

    async def get_market_indices(self) -> list[IntlQuote]:
        """获取主要国际指数行情。"""
        await self._ensure_initialized()
        await self._rate_limit()
        assert self._ctx is not None

        try:
            quotes = await self._ctx.quote(MAJOR_INDICES)
            results: list[IntlQuote] = []
            for q, symbol in zip(quotes, MAJOR_INDICES, strict=False):
                _, market = parse_symbol(symbol)
                results.append(
                    IntlQuote(
                        symbol=symbol,
                        name=getattr(q, "name_en", "") or "",
                        market=market,
                        price=float(getattr(q, "last_done", 0) or 0),
                        change=float(getattr(q, "last_done", 0) or 0)
                        - float(getattr(q, "prev_close_price", 0) or 0),
                        change_pct=_calc_change_pct(
                            float(getattr(q, "last_done", 0) or 0),
                            float(getattr(q, "prev_close_price", 0) or 0),
                        ),
                        volume=float(getattr(q, "volume", 0) or 0),
                        turnover=float(getattr(q, "turnover", 0) or 0),
                        high=float(getattr(q, "high", 0) or 0),
                        low=float(getattr(q, "low", 0) or 0),
                        open=float(getattr(q, "open", 0) or 0),
                        prev_close=float(getattr(q, "prev_close_price", 0) or 0),
                        timestamp=datetime.now(),
                    )
                )
            return results
        except OpenApiException as exc:
            raise DataSourceError(
                step="获取指数",
                source=self.source_name,
                url="MAJOR_INDICES",
                error_type="API错误",
                error_msg=f"code={exc.code}, message={exc.message}",
                suggestion="检查 Longbridge API 状态",
            ) from exc
        except Exception as exc:
            raise DataSourceError(
                step="获取指数",
                source=self.source_name,
                url="MAJOR_INDICES",
                error_type=type(exc).__name__,
                error_msg=str(exc),
                suggestion="检查网络连接或 Longbridge 服务状态",
            ) from exc

    @property
    def source_name(self) -> str:
        return "longbridge"

    @property
    def priority(self) -> int:
        return 0

    @property
    def supported_markets(self) -> set[str]:
        return {"US", "HK", "SG"}

    async def is_available(self) -> bool:
        """检查 Longbridge SDK 是否可用。"""
        if not _HAS_LONGBRIDGE:
            return False
        client_id = _get_longbridge_client_id()
        return bool(client_id)


def _calc_change_pct(current: float, prev_close: float) -> float:
    """计算涨跌幅百分比。"""
    if prev_close == 0:
        return 0.0
    return round((current - prev_close) / prev_close * 100, 2)

"""国际市场数据源管理器：按优先级 failover 编排多个数据源。"""

from __future__ import annotations

from typing import Any, cast

from src.data.a_share.base import DataUnavailableError
from src.data.international.base import (
    BaseIntlFetcher,
    IntlKlineBar,
    IntlQuote,
    parse_symbol,
)
from src.log import get_logger
from src.network.errors import DataSourceError

logger = get_logger(__name__)


class IntlDataManager:
    """国际市场数据源管理器。

    注册多个数据源适配器，按优先级自动 failover。
    针对具体市场过滤可用的数据源。
    """

    def __init__(self) -> None:
        self._fetchers: list[BaseIntlFetcher] = []
        self._stats: dict[str, dict[str, int]] = {}

    def register(self, fetcher: BaseIntlFetcher) -> None:
        """注册数据源适配器。

        注册后按 priority 排序，优先级相同时保持注册顺序。
        """
        self._fetchers.append(fetcher)
        self._fetchers.sort(key=lambda f: f.priority)
        self._stats[fetcher.source_name] = {"success": 0, "failure": 0}
        logger.info(
            "注册国际市场数据源: %s (优先级=%d, 支持市场=%s)",
            fetcher.source_name,
            fetcher.priority,
            fetcher.supported_markets,
        )

    async def _get_available_fetchers(
        self, market: str | None = None
    ) -> list[BaseIntlFetcher]:
        """获取当前可用的数据源列表（已按优先级排序）。

        Args:
            market: 如指定，则只返回支持该市场的数据源
        """
        available: list[BaseIntlFetcher] = []
        for fetcher in self._fetchers:
            if not await fetcher.is_available():
                continue
            if market and not fetcher.supports_market(market):
                continue
            available.append(fetcher)
        return available

    async def get_quote(self, symbol: str) -> IntlQuote:
        """获取实时行情，按优先级 failover。"""
        _, market = parse_symbol(symbol)
        result = await self._fetch_with_failover(
            method_name="get_quote",
            market=market,
            symbol=symbol,
        )
        return cast(IntlQuote, result)

    async def get_kline(
        self, symbol: str, period: str = "daily", count: int = 100
    ) -> list[IntlKlineBar]:
        """获取K线数据，按优先级 failover。"""
        _, market = parse_symbol(symbol)
        result = await self._fetch_with_failover(
            method_name="get_kline",
            market=market,
            symbol=symbol,
            period=period,
            count=count,
        )
        return cast(list[IntlKlineBar], result)

    async def get_market_indices(self) -> list[IntlQuote]:
        """获取主要国际指数行情，按优先级 failover。"""
        result = await self._fetch_with_failover(
            method_name="get_market_indices",
            market=None,
        )
        return cast(list[IntlQuote], result)

    async def _fetch_with_failover(
        self, method_name: str, market: str | None, **kwargs: object
    ) -> Any:
        """通用 failover 调度：按优先级逐个尝试，失败则切换到下一个。"""
        available = await self._get_available_fetchers(market)
        if not available:
            raise DataUnavailableError(
                "没有可用的国际市场数据源，请检查数据源库是否安装及配置是否正确",
                errors=[],
            )

        errors: list[dict[str, str]] = []
        for fetcher in available:
            try:
                method = getattr(fetcher, method_name)
                result = await method(**kwargs)
                self._stats[fetcher.source_name]["success"] += 1
                logger.debug(
                    "[%s] %s 成功 (参数: %s)",
                    fetcher.source_name,
                    method_name,
                    kwargs,
                )
                return result
            except DataSourceError as exc:
                self._stats[fetcher.source_name]["failure"] += 1
                errors.append(exc.to_dict())
                logger.warning(
                    "[%s] %s 失败: %s，尝试下一个数据源",
                    fetcher.source_name,
                    method_name,
                    exc,
                )
            except Exception as exc:
                self._stats[fetcher.source_name]["failure"] += 1
                error_info = {
                    "source": fetcher.source_name,
                    "step": method_name,
                    "url": "",
                    "error_type": type(exc).__name__,
                    "error_msg": str(exc),
                    "suggestion": "检查数据源状态",
                }
                errors.append(error_info)
                logger.warning(
                    "[%s] %s 发生未预期异常: %s，尝试下一个数据源",
                    fetcher.source_name,
                    method_name,
                    exc,
                )

        raise DataUnavailableError(
            f"所有数据源均无法完成 {method_name} 请求 (参数: {kwargs})",
            errors=errors,
        )

    def get_stats(self) -> dict[str, dict[str, int]]:
        """获取各数据源的成功/失败统计。"""
        return dict(self._stats)

    @property
    def fetcher_count(self) -> int:
        """已注册的数据源总数。"""
        return len(self._fetchers)

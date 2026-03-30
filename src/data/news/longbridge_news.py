"""Longbridge 新闻数据源适配器。

通过 longbridge SDK 的 ContentContext 获取新闻和讨论。
SDK 未安装或凭证缺失时自动标记为不可用。
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from src.data.news.base import BaseNewsSource, NewsItem
from src.log import get_logger

logger = get_logger(__name__)

# 尝试导入 longbridge SDK
try:
    from longbridge.openapi import Config as LBConfig  # type: ignore[import-untyped]

    _HAS_LONGBRIDGE = True
except ImportError:
    _HAS_LONGBRIDGE = False

# ContentContext 可能在某些版本中不可用
_HAS_CONTENT_CTX = False
if _HAS_LONGBRIDGE:
    try:
        from longbridge.openapi import ContentContext  # type: ignore[import-untyped,attr-defined]

        _HAS_CONTENT_CTX = True
    except ImportError:
        pass


def _has_longbridge_credentials() -> bool:
    """检查 Longbridge 凭证环境变量是否已配置。"""
    return bool(
        os.environ.get("LONGBRIDGE_APP_KEY")
        and os.environ.get("LONGBRIDGE_APP_SECRET")
        and os.environ.get("LONGBRIDGE_ACCESS_TOKEN")
    )


class LongbridgeNewsSource(BaseNewsSource):
    """Longbridge 新闻数据源。

    使用 longbridge SDK 的 ContentContext 获取新闻和社区讨论。
    需要 SDK 已安装且 ContentContext 可用，以及 Longbridge 凭证已配置。
    """

    def __init__(self) -> None:
        self._ctx: ContentContext | None = None  # type: ignore[name-defined]

    def _ensure_ctx(self) -> ContentContext:  # type: ignore[name-defined]
        """确保 ContentContext 已初始化。"""
        if self._ctx is None:
            config = LBConfig.from_env()  # type: ignore[union-attr]
            self._ctx = ContentContext(config)  # type: ignore[possibly-undefined]
        return self._ctx  # type: ignore[return-value]

    @property
    def source_name(self) -> str:
        return "longbridge"

    @property
    def requires_token(self) -> bool:
        return True

    async def is_available(self) -> bool:
        """SDK 已安装、ContentContext 可用且凭证已配置时才可用。"""
        if not _HAS_LONGBRIDGE or not _HAS_CONTENT_CTX:
            return False
        return _has_longbridge_credentials()

    async def search(self, query: str, limit: int = 20) -> list[NewsItem]:
        """Longbridge 不支持关键词搜索，返回空列表。"""
        logger.debug("Longbridge 不支持关键词搜索，跳过查询: %s", query)
        return []

    async def get_stock_news(self, code: str, limit: int = 20) -> list[NewsItem]:
        """获取个股新闻和讨论。

        合并 news() 和 topics() 的结果。

        Args:
            code: 股票代码（需要包含市场后缀，如 "700.HK"、"AAPL.US"）
            limit: 返回数量上限
        """
        symbol = _normalize_symbol(code)
        results: list[NewsItem] = []

        # 获取新闻
        news_items = await self._fetch_news(symbol)
        results.extend(news_items)

        # 获取社区讨论
        topic_items = await self._fetch_topics(symbol)
        results.extend(topic_items)

        # 按时间排序，取前 limit 条
        results.sort(
            key=lambda x: x.published_at or datetime.min,
            reverse=True,
        )
        return results[:limit]

    async def _fetch_news(self, symbol: str) -> list[NewsItem]:
        """获取新闻列表。"""
        try:
            ctx = self._ensure_ctx()
            raw_items = await asyncio.to_thread(ctx.news, symbol)
            return [
                NewsItem(
                    title=getattr(item, "title", ""),
                    source="longbridge",
                    url=getattr(item, "url", ""),
                    summary=getattr(item, "description", ""),
                    published_at=_parse_lb_time(getattr(item, "published_at", None)),
                )
                for item in raw_items
            ]
        except Exception as exc:
            logger.warning("[longbridge] 获取新闻失败 (symbol=%s): %s", symbol, exc)
            return []

    async def _fetch_topics(self, symbol: str) -> list[NewsItem]:
        """获取社区讨论列表。"""
        try:
            ctx = self._ensure_ctx()
            raw_items = await asyncio.to_thread(ctx.topics, symbol)
            return [
                NewsItem(
                    title=getattr(item, "title", ""),
                    source="longbridge_topics",
                    url=getattr(item, "url", ""),
                    summary=getattr(item, "description", ""),
                    published_at=_parse_lb_time(getattr(item, "published_at", None)),
                )
                for item in raw_items
            ]
        except Exception as exc:
            logger.warning("[longbridge] 获取讨论失败 (symbol=%s): %s", symbol, exc)
            return []


def _normalize_symbol(code: str) -> str:
    """将股票代码标准化为 Longbridge 格式。

    - 已包含市场后缀的直接返回（如 "700.HK"、"AAPL.US"）
    - 纯数字代码根据交易所规则添加后缀
    """
    if "." in code:
        return code

    # A股代码自动添加后缀
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"

    # 其他情况原样返回
    return code


def _parse_lb_time(value: object) -> datetime | None:
    """解析 Longbridge 返回的时间值。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None

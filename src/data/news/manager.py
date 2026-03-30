"""新闻数据源管理器：聚合多源新闻，支持并发获取和去重。"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime

from pydantic import BaseModel

from src.data.news.base import BaseNewsSource, NewsItem
from src.log import get_logger

logger = get_logger(__name__)

# 真实 User-Agent 池（50+ 条），供未来爬虫扩展使用
_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
]


class AntiScrapeConfig(BaseModel):
    """反爬配置（供未来爬虫扩展使用）。

    Attributes:
        min_interval: 请求最小间隔（秒）
        max_interval: 请求最大间隔（秒）
        jitter: 随机抖动范围（秒）
        backoff_base: 指数退避基础间隔（秒）
        backoff_multiplier: 指数退避倍数
        max_backoff: 最大退避间隔（秒）
        cache_ttl: 缓存有效期（秒），同一内容在此时间内不重复抓取
    """

    min_interval: float = 2.0
    max_interval: float = 5.0
    jitter: float = 3.0
    backoff_base: float = 2.0
    backoff_multiplier: float = 2.0
    max_backoff: float = 60.0
    cache_ttl: int = 86400  # 24小时

    def get_random_interval(self) -> float:
        """获取一个带随机抖动的请求间隔。"""
        base = random.uniform(self.min_interval, self.max_interval)
        jitter = random.uniform(0, self.jitter)
        return base + jitter

    def get_backoff_delay(self, attempt: int) -> float:
        """获取指数退避延迟。

        Args:
            attempt: 当前重试次数（从 0 开始）

        Returns:
            延迟秒数
        """
        delay = self.backoff_base * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_backoff)

    @staticmethod
    def get_random_ua() -> str:
        """从 UA 池中随机获取一个 User-Agent。"""
        return random.choice(_USER_AGENTS)


class NewsManager:
    """新闻数据源管理器。

    注册多个新闻源，并发获取新闻，聚合去重后返回。
    单个源失败不阻塞其他源。
    """

    def __init__(self) -> None:
        self._sources: list[BaseNewsSource] = []
        self._stats: dict[str, dict[str, int]] = {}

    def register(self, source: BaseNewsSource) -> None:
        """注册新闻源。"""
        self._sources.append(source)
        self._stats[source.source_name] = {"success": 0, "failure": 0}
        logger.info(
            "注册新闻源: %s (需要token=%s)",
            source.source_name,
            source.requires_token,
        )

    async def search(self, query: str, limit: int = 20) -> list[NewsItem]:
        """从所有可用新闻源搜索新闻。

        Args:
            query: 搜索关键词
            limit: 返回数量上限
        """
        available = await self._get_available_sources()
        if not available:
            logger.warning("没有可用的新闻源")
            return []

        all_items = await self._fetch_concurrent(
            available,
            method_name="search",
            query=query,
            limit=limit,
        )
        return _deduplicate_and_sort(all_items, limit)

    async def get_stock_news(self, code: str, limit: int = 20) -> list[NewsItem]:
        """从所有可用新闻源获取个股新闻。

        Args:
            code: 股票代码
            limit: 返回数量上限
        """
        available = await self._get_available_sources()
        if not available:
            logger.warning("没有可用的新闻源")
            return []

        all_items = await self._fetch_concurrent(
            available,
            method_name="get_stock_news",
            code=code,
            limit=limit,
        )
        return _deduplicate_and_sort(all_items, limit)

    async def _get_available_sources(self) -> list[BaseNewsSource]:
        """获取当前可用的新闻源列表。"""
        available: list[BaseNewsSource] = []
        for source in self._sources:
            try:
                if await source.is_available():
                    available.append(source)
            except Exception as exc:
                logger.warning(
                    "[%s] 检查可用性时出错: %s",
                    source.source_name,
                    exc,
                )
        return available

    async def _fetch_concurrent(
        self,
        sources: list[BaseNewsSource],
        method_name: str,
        **kwargs: object,
    ) -> list[NewsItem]:
        """并发调用多个新闻源，收集结果。"""
        tasks = [
            self._fetch_single(source, method_name, **kwargs)
            for source in sources
        ]
        results = await asyncio.gather(*tasks)
        all_items: list[NewsItem] = []
        for items in results:
            all_items.extend(items)
        return all_items

    async def _fetch_single(
        self,
        source: BaseNewsSource,
        method_name: str,
        **kwargs: object,
    ) -> list[NewsItem]:
        """调用单个新闻源，失败时返回空列表并记录统计。"""
        try:
            method = getattr(source, method_name)
            items: list[NewsItem] = await method(**kwargs)
            self._stats[source.source_name]["success"] += 1
            logger.debug(
                "[%s] %s 成功，获取 %d 条新闻",
                source.source_name,
                method_name,
                len(items),
            )
            return items
        except Exception as exc:
            self._stats[source.source_name]["failure"] += 1
            logger.warning(
                "[%s] %s 失败: %s",
                source.source_name,
                method_name,
                exc,
            )
            return []

    def get_stats(self) -> dict[str, dict[str, int]]:
        """获取各新闻源的成功/失败统计。"""
        return dict(self._stats)

    @property
    def source_count(self) -> int:
        """已注册的新闻源总数。"""
        return len(self._sources)


def _deduplicate_and_sort(items: list[NewsItem], limit: int) -> list[NewsItem]:
    """按 URL 去重，按时间排序，取前 limit 条。"""
    seen_urls: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        # URL 为空时不去重（允许无 URL 的新闻共存）
        if item.url and item.url in seen_urls:
            continue
        if item.url:
            seen_urls.add(item.url)
        unique.append(item)

    unique.sort(
        key=lambda x: x.published_at or datetime.min,
        reverse=True,
    )
    return unique[:limit]

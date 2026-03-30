"""RSS 新闻源适配器。

通过 httpx 获取主流财经媒体的 RSS feed，使用标准库 xml.etree.ElementTree 解析。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from src.data.news.base import BaseNewsSource, NewsItem
from src.log import get_logger
from src.network.client import NetworkClient

logger = get_logger(__name__)

# 预定义的财经媒体 RSS 地址
_DEFAULT_RSS_FEEDS: dict[str, str] = {
    "华尔街见闻": "https://wallstreetcn.com/rss/news/global",
    "财联社": "https://www.cls.cn/rss",
    "金十数据": "https://www.jin10.com/rss",
    "36氪": "https://36kr.com/feed",
}


class RssNewsSource(BaseNewsSource):
    """RSS 新闻源。

    从预定义的财经媒体 RSS 地址获取新闻。
    支持自定义 RSS 地址列表。
    """

    def __init__(
        self,
        feeds: dict[str, str] | None = None,
    ) -> None:
        """初始化 RSS 新闻源。

        Args:
            feeds: 自定义 RSS 地址映射 {名称: URL}，为 None 时使用默认列表
        """
        self._feeds = feeds if feeds is not None else dict(_DEFAULT_RSS_FEEDS)

    @property
    def source_name(self) -> str:
        return "rss"

    @property
    def requires_token(self) -> bool:
        return False

    async def search(self, query: str, limit: int = 20) -> list[NewsItem]:
        """从所有 RSS 源获取新闻，按关键词过滤标题和摘要。

        Args:
            query: 搜索关键词
            limit: 返回数量上限
        """
        all_items = await self._fetch_all_feeds()
        # 按关键词过滤
        filtered = [
            item
            for item in all_items
            if query.lower() in item.title.lower()
            or query.lower() in item.summary.lower()
        ]
        filtered.sort(
            key=lambda x: x.published_at or datetime.min,
            reverse=True,
        )
        return filtered[:limit]

    async def get_stock_news(self, code: str, limit: int = 20) -> list[NewsItem]:
        """获取个股相关新闻（RSS 源无法精确筛选个股，使用代码作为关键词过滤）。"""
        return await self.search(code, limit=limit)

    async def _fetch_all_feeds(self) -> list[NewsItem]:
        """获取所有 RSS 源的新闻。"""
        results: list[NewsItem] = []
        for feed_name, feed_url in self._feeds.items():
            items = await self._fetch_single_feed(feed_name, feed_url)
            results.extend(items)
        return results

    async def _fetch_single_feed(
        self, feed_name: str, feed_url: str
    ) -> list[NewsItem]:
        """获取单个 RSS 源的新闻。

        解析失败时记录日志并返回空列表，不阻塞其他源。
        """
        try:
            async with NetworkClient("rss") as client:
                response = await client.get(feed_url)
                xml_text = response.text
            return _parse_rss_xml(xml_text, feed_name)
        except Exception as exc:
            logger.warning(
                "[rss] 获取 %s 的 RSS 失败 (url=%s): %s",
                feed_name,
                feed_url,
                exc,
            )
            return []


def _parse_rss_xml(xml_text: str, feed_name: str) -> list[NewsItem]:
    """解析 RSS XML 文本，提取新闻条目。

    同时支持 RSS 2.0（<item>）和 Atom（<entry>）格式。
    """
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("[rss] 解析 %s 的 XML 失败: %s", feed_name, exc)
        return items

    # RSS 2.0 格式
    for item_elem in root.iter("item"):
        news = _parse_rss_item(item_elem, feed_name)
        if news:
            items.append(news)

    # Atom 格式（如果没有找到 RSS item）
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry_elem in root.iter("{http://www.w3.org/2005/Atom}entry"):
            news = _parse_atom_entry(entry_elem, feed_name, ns)
            if news:
                items.append(news)

    return items


def _parse_rss_item(elem: ET.Element, feed_name: str) -> NewsItem | None:
    """解析 RSS 2.0 的 <item> 元素。"""
    title = _get_text(elem, "title")
    if not title:
        return None

    link = _get_text(elem, "link")
    description = _get_text(elem, "description")
    pub_date_str = _get_text(elem, "pubDate")
    published_at = _parse_rfc2822_date(pub_date_str) if pub_date_str else None

    return NewsItem(
        title=title,
        source=feed_name,
        url=link,
        summary=description,
        published_at=published_at,
    )


def _parse_atom_entry(
    elem: ET.Element, feed_name: str, ns: dict[str, str]
) -> NewsItem | None:
    """解析 Atom 的 <entry> 元素。"""
    title_elem = elem.find("atom:title", ns)
    title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
    if not title:
        return None

    link_elem = elem.find("atom:link", ns)
    link = link_elem.get("href", "") if link_elem is not None else ""

    summary_elem = elem.find("atom:summary", ns)
    summary = (
        summary_elem.text.strip()
        if summary_elem is not None and summary_elem.text
        else ""
    )

    updated_elem = elem.find("atom:updated", ns)
    published_elem = elem.find("atom:published", ns)
    time_str = ""
    if published_elem is not None and published_elem.text:
        time_str = published_elem.text.strip()
    elif updated_elem is not None and updated_elem.text:
        time_str = updated_elem.text.strip()

    published_at = _parse_iso_date(time_str) if time_str else None

    return NewsItem(
        title=title,
        source=feed_name,
        url=link,
        summary=summary,
        published_at=published_at,
    )


def _get_text(parent: ET.Element, tag: str) -> str:
    """获取子元素的文本内容。"""
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return ""


def _parse_rfc2822_date(date_str: str) -> datetime | None:
    """解析 RFC 2822 格式的日期（RSS 2.0 标准）。"""
    try:
        return parsedate_to_datetime(date_str)
    except (ValueError, TypeError):
        return None


def _parse_iso_date(date_str: str) -> datetime | None:
    """解析 ISO 8601 格式的日期（Atom 标准）。"""
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

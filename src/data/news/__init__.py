"""新闻/情绪数据适配器模块。"""

from __future__ import annotations

from src.data.news.base import BaseNewsSource, NewsItem
from src.data.news.manager import AntiScrapeConfig, NewsManager

__all__ = [
    "AntiScrapeConfig",
    "BaseNewsSource",
    "NewsItem",
    "NewsManager",
]

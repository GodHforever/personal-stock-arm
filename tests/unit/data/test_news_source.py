"""新闻/情绪数据源适配器单元测试。

测试策略：
- Mock 所有外部调用（HTTP、Longbridge SDK）
- 测试数据模型校验
- 测试 RSS 解析（RSS 2.0 和 Atom 格式）
- 测试 Longbridge 适配器的可用性检测
- 测试 NewsManager 聚合、去重、排序
- 测试单个源失败不阻塞其他源
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.news.base import BaseNewsSource, NewsItem
from src.data.news.manager import (
    AntiScrapeConfig,
    NewsManager,
    _USER_AGENTS,
    _deduplicate_and_sort,
)


# ===================== 数据模型测试 =====================


class TestNewsItem:
    """NewsItem 数据模型测试。"""

    def test_创建完整新闻(self) -> None:
        item = NewsItem(
            title="测试新闻标题",
            source="测试源",
            url="https://example.com/news/1",
            summary="这是一条测试新闻",
            published_at=datetime(2026, 3, 30, 10, 0),
            sentiment=0.8,
        )
        assert item.title == "测试新闻标题"
        assert item.source == "测试源"
        assert item.url == "https://example.com/news/1"
        assert item.sentiment == 0.8

    def test_创建最小新闻(self) -> None:
        item = NewsItem(title="标题", source="来源")
        assert item.title == "标题"
        assert item.source == "来源"
        assert item.url == ""
        assert item.summary == ""
        assert item.published_at is None
        assert item.sentiment is None


# ===================== BaseNewsSource 抽象基类测试 =====================


class MockNewsSource(BaseNewsSource):
    """用于测试的 Mock 新闻源。"""

    def __init__(
        self,
        name: str = "mock",
        needs_token: bool = False,
        available: bool = True,
    ) -> None:
        self._name = name
        self._needs_token = needs_token
        self._available = available
        self.search_result: list[NewsItem] = []
        self.stock_news_result: list[NewsItem] = []
        self.should_fail: bool = False

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def requires_token(self) -> bool:
        return self._needs_token

    async def is_available(self) -> bool:
        return self._available

    async def search(self, query: str, limit: int = 20) -> list[NewsItem]:
        if self.should_fail:
            raise RuntimeError("模拟搜索失败")
        return self.search_result[:limit]

    async def get_stock_news(self, code: str, limit: int = 20) -> list[NewsItem]:
        if self.should_fail:
            raise RuntimeError("模拟获取新闻失败")
        return self.stock_news_result[:limit]


class TestBaseNewsSource:
    """BaseNewsSource 抽象基类测试。"""

    @pytest.mark.asyncio
    async def test_默认is_available返回True(self) -> None:
        source = MockNewsSource()
        assert await source.is_available() is True

    @pytest.mark.asyncio
    async def test_设置不可用(self) -> None:
        source = MockNewsSource(available=False)
        assert await source.is_available() is False

    def test_source_name属性(self) -> None:
        source = MockNewsSource(name="test_source")
        assert source.source_name == "test_source"

    def test_requires_token属性(self) -> None:
        source = MockNewsSource(needs_token=True)
        assert source.requires_token is True


# ===================== RSS 解析测试 =====================


class TestRssSource:
    """RSS 新闻源测试。"""

    SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>测试财经新闻</title>
        <item>
          <title>A股大涨：沪指突破3500点</title>
          <link>https://example.com/news/1</link>
          <description>今日A股市场全面上涨</description>
          <pubDate>Mon, 30 Mar 2026 10:00:00 +0800</pubDate>
        </item>
        <item>
          <title>央行降准50基点</title>
          <link>https://example.com/news/2</link>
          <description>中国人民银行决定下调准备金率</description>
          <pubDate>Mon, 30 Mar 2026 09:00:00 +0800</pubDate>
        </item>
      </channel>
    </rss>"""

    SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>测试Atom源</title>
      <entry>
        <title>科技股走强</title>
        <link href="https://example.com/atom/1"/>
        <summary>科技板块领涨市场</summary>
        <published>2026-03-30T08:00:00+08:00</published>
      </entry>
    </feed>"""

    def test_解析RSS20格式(self) -> None:
        from src.data.news.rss_source import _parse_rss_xml

        items = _parse_rss_xml(self.SAMPLE_RSS_XML, "测试源")
        assert len(items) == 2
        assert items[0].title == "A股大涨：沪指突破3500点"
        assert items[0].source == "测试源"
        assert items[0].url == "https://example.com/news/1"
        assert items[0].summary == "今日A股市场全面上涨"
        assert items[0].published_at is not None

    def test_解析Atom格式(self) -> None:
        from src.data.news.rss_source import _parse_rss_xml

        items = _parse_rss_xml(self.SAMPLE_ATOM_XML, "Atom源")
        assert len(items) == 1
        assert items[0].title == "科技股走强"
        assert items[0].url == "https://example.com/atom/1"
        assert items[0].source == "Atom源"

    def test_解析无效XML返回空(self) -> None:
        from src.data.news.rss_source import _parse_rss_xml

        items = _parse_rss_xml("这不是XML", "无效源")
        assert items == []

    def test_解析空item跳过(self) -> None:
        from src.data.news.rss_source import _parse_rss_xml

        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item><title></title></item>
            <item><title>有效新闻</title><link>https://example.com/3</link></item>
          </channel>
        </rss>"""
        items = _parse_rss_xml(xml, "测试")
        assert len(items) == 1
        assert items[0].title == "有效新闻"

    @pytest.mark.asyncio
    async def test_RSS源属性(self) -> None:
        from src.data.news.rss_source import RssNewsSource

        source = RssNewsSource()
        assert source.source_name == "rss"
        assert source.requires_token is False
        assert await source.is_available() is True

    @pytest.mark.asyncio
    async def test_自定义feeds(self) -> None:
        from src.data.news.rss_source import RssNewsSource

        custom_feeds = {"自定义源": "https://example.com/rss"}
        source = RssNewsSource(feeds=custom_feeds)
        assert source._feeds == custom_feeds

    @pytest.mark.asyncio
    async def test_search关键词过滤(self) -> None:
        from src.data.news.rss_source import RssNewsSource

        source = RssNewsSource(feeds={"测试": "https://example.com/rss"})

        # Mock NetworkClient
        mock_response = MagicMock()
        mock_response.text = self.SAMPLE_RSS_XML

        with patch(
            "src.data.news.rss_source.NetworkClient"
        ) as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            items = await source.search("降准", limit=10)
            assert len(items) == 1
            assert "降准" in items[0].title

    @pytest.mark.asyncio
    async def test_fetch失败返回空列表(self) -> None:
        from src.data.news.rss_source import RssNewsSource

        source = RssNewsSource(feeds={"失败源": "https://bad-url.example.com/rss"})

        with patch(
            "src.data.news.rss_source.NetworkClient"
        ) as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=RuntimeError("网络错误"))
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            items = await source.search("任何关键词")
            assert items == []


# ===================== 日期解析测试 =====================


class TestDateParsing:
    """日期解析工具函数测试。"""

    def test_解析RFC2822日期(self) -> None:
        from src.data.news.rss_source import _parse_rfc2822_date

        dt = _parse_rfc2822_date("Mon, 30 Mar 2026 10:00:00 +0800")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 30

    def test_解析无效RFC2822返回None(self) -> None:
        from src.data.news.rss_source import _parse_rfc2822_date

        assert _parse_rfc2822_date("无效日期") is None

    def test_解析ISO日期(self) -> None:
        from src.data.news.rss_source import _parse_iso_date

        dt = _parse_iso_date("2026-03-30T08:00:00+08:00")
        assert dt is not None
        assert dt.year == 2026

    def test_解析ISO日期带Z后缀(self) -> None:
        from src.data.news.rss_source import _parse_iso_date

        dt = _parse_iso_date("2026-03-30T00:00:00Z")
        assert dt is not None
        assert dt.year == 2026

    def test_解析无效ISO返回None(self) -> None:
        from src.data.news.rss_source import _parse_iso_date

        assert _parse_iso_date("无效") is None


# ===================== Longbridge 适配器测试 =====================


class TestLongbridgeNewsSource:
    """Longbridge 新闻适配器测试。"""

    @pytest.mark.asyncio
    async def test_属性(self) -> None:
        from src.data.news.longbridge_news import LongbridgeNewsSource

        source = LongbridgeNewsSource()
        assert source.source_name == "longbridge"
        assert source.requires_token is True

    @pytest.mark.asyncio
    async def test_SDK未安装时不可用(self) -> None:
        from src.data.news.longbridge_news import LongbridgeNewsSource

        source = LongbridgeNewsSource()
        with patch("src.data.news.longbridge_news._HAS_LONGBRIDGE", False):
            assert await source.is_available() is False

    @pytest.mark.asyncio
    async def test_ContentContext不可用时不可用(self) -> None:
        from src.data.news.longbridge_news import LongbridgeNewsSource

        source = LongbridgeNewsSource()
        with patch("src.data.news.longbridge_news._HAS_LONGBRIDGE", True), patch(
            "src.data.news.longbridge_news._HAS_CONTENT_CTX", False
        ):
            assert await source.is_available() is False

    @pytest.mark.asyncio
    async def test_无凭证时不可用(self) -> None:
        from src.data.news.longbridge_news import LongbridgeNewsSource

        source = LongbridgeNewsSource()
        with (
            patch("src.data.news.longbridge_news._HAS_LONGBRIDGE", True),
            patch("src.data.news.longbridge_news._HAS_CONTENT_CTX", True),
            patch.dict(
                "os.environ",
                {"LONGBRIDGE_APP_KEY": "", "LONGBRIDGE_APP_SECRET": "", "LONGBRIDGE_ACCESS_TOKEN": ""},
                clear=False,
            ),
        ):
            assert await source.is_available() is False

    @pytest.mark.asyncio
    async def test_凭证齐全时可用(self) -> None:
        from src.data.news.longbridge_news import LongbridgeNewsSource

        source = LongbridgeNewsSource()
        with (
            patch("src.data.news.longbridge_news._HAS_LONGBRIDGE", True),
            patch("src.data.news.longbridge_news._HAS_CONTENT_CTX", True),
            patch.dict(
                "os.environ",
                {
                    "LONGBRIDGE_APP_KEY": "test_key",
                    "LONGBRIDGE_APP_SECRET": "test_secret",
                    "LONGBRIDGE_ACCESS_TOKEN": "test_token",
                },
                clear=False,
            ),
        ):
            assert await source.is_available() is True

    @pytest.mark.asyncio
    async def test_search返回空列表(self) -> None:
        """Longbridge 不支持关键词搜索。"""
        from src.data.news.longbridge_news import LongbridgeNewsSource

        source = LongbridgeNewsSource()
        result = await source.search("测试")
        assert result == []

    def test_代码标准化_沪市(self) -> None:
        from src.data.news.longbridge_news import _normalize_symbol

        assert _normalize_symbol("600000") == "600000.SH"

    def test_代码标准化_深市(self) -> None:
        from src.data.news.longbridge_news import _normalize_symbol

        assert _normalize_symbol("000001") == "000001.SZ"
        assert _normalize_symbol("300001") == "300001.SZ"

    def test_代码标准化_已有后缀(self) -> None:
        from src.data.news.longbridge_news import _normalize_symbol

        assert _normalize_symbol("700.HK") == "700.HK"
        assert _normalize_symbol("AAPL.US") == "AAPL.US"

    def test_时间解析_datetime对象(self) -> None:
        from src.data.news.longbridge_news import _parse_lb_time

        dt = datetime(2026, 3, 30, 10, 0)
        assert _parse_lb_time(dt) == dt

    def test_时间解析_None(self) -> None:
        from src.data.news.longbridge_news import _parse_lb_time

        assert _parse_lb_time(None) is None

    def test_时间解析_字符串(self) -> None:
        from src.data.news.longbridge_news import _parse_lb_time

        result = _parse_lb_time("2026-03-30T10:00:00")
        assert result is not None
        assert result.year == 2026


# ===================== AntiScrapeConfig 测试 =====================


class TestAntiScrapeConfig:
    """反爬配置测试。"""

    def test_默认值(self) -> None:
        config = AntiScrapeConfig()
        assert config.min_interval == 2.0
        assert config.max_interval == 5.0
        assert config.jitter == 3.0
        assert config.backoff_base == 2.0
        assert config.cache_ttl == 86400

    def test_随机间隔在范围内(self) -> None:
        config = AntiScrapeConfig()
        for _ in range(100):
            interval = config.get_random_interval()
            # min_interval + 0 <= interval <= max_interval + jitter
            assert 2.0 <= interval <= 8.0

    def test_指数退避(self) -> None:
        config = AntiScrapeConfig()
        assert config.get_backoff_delay(0) == 2.0  # 2 * 2^0
        assert config.get_backoff_delay(1) == 4.0  # 2 * 2^1
        assert config.get_backoff_delay(2) == 8.0  # 2 * 2^2

    def test_退避不超过最大值(self) -> None:
        config = AntiScrapeConfig(max_backoff=10.0)
        assert config.get_backoff_delay(10) == 10.0

    def test_UA池数量充足(self) -> None:
        assert len(_USER_AGENTS) >= 50

    def test_随机UA(self) -> None:
        ua = AntiScrapeConfig.get_random_ua()
        assert ua in _USER_AGENTS
        assert "Mozilla" in ua


# ===================== NewsManager 测试 =====================


class TestNewsManager:
    """NewsManager 聚合管理器测试。"""

    def _make_manager(self, *sources: BaseNewsSource) -> NewsManager:
        mgr = NewsManager()
        for s in sources:
            mgr.register(s)
        return mgr

    @pytest.mark.asyncio
    async def test_单源搜索成功(self) -> None:
        source = MockNewsSource(name="src1")
        source.search_result = [
            NewsItem(
                title="测试新闻",
                source="src1",
                url="https://example.com/1",
                published_at=datetime(2026, 3, 30),
            )
        ]
        mgr = self._make_manager(source)
        items = await mgr.search("测试")
        assert len(items) == 1
        assert items[0].title == "测试新闻"
        assert mgr.get_stats()["src1"]["success"] == 1

    @pytest.mark.asyncio
    async def test_多源聚合(self) -> None:
        s1 = MockNewsSource(name="src1")
        s1.search_result = [
            NewsItem(
                title="新闻A",
                source="src1",
                url="https://a.com/1",
                published_at=datetime(2026, 3, 30, 10),
            )
        ]
        s2 = MockNewsSource(name="src2")
        s2.search_result = [
            NewsItem(
                title="新闻B",
                source="src2",
                url="https://b.com/1",
                published_at=datetime(2026, 3, 30, 11),
            )
        ]
        mgr = self._make_manager(s1, s2)
        items = await mgr.search("新闻")
        assert len(items) == 2
        # 按时间倒序排列
        assert items[0].title == "新闻B"
        assert items[1].title == "新闻A"

    @pytest.mark.asyncio
    async def test_单源失败不阻塞(self) -> None:
        s1 = MockNewsSource(name="正常源")
        s1.search_result = [
            NewsItem(title="正常新闻", source="正常源", url="https://ok.com/1")
        ]
        s2 = MockNewsSource(name="故障源")
        s2.should_fail = True
        mgr = self._make_manager(s1, s2)

        items = await mgr.search("测试")
        assert len(items) == 1
        assert items[0].title == "正常新闻"
        assert mgr.get_stats()["正常源"]["success"] == 1
        assert mgr.get_stats()["故障源"]["failure"] == 1

    @pytest.mark.asyncio
    async def test_全部失败返回空列表(self) -> None:
        s1 = MockNewsSource(name="故障A")
        s1.should_fail = True
        s2 = MockNewsSource(name="故障B")
        s2.should_fail = True
        mgr = self._make_manager(s1, s2)

        items = await mgr.search("测试")
        assert items == []
        assert mgr.get_stats()["故障A"]["failure"] == 1
        assert mgr.get_stats()["故障B"]["failure"] == 1

    @pytest.mark.asyncio
    async def test_无可用源返回空列表(self) -> None:
        s1 = MockNewsSource(name="不可用", available=False)
        mgr = self._make_manager(s1)
        items = await mgr.search("测试")
        assert items == []

    @pytest.mark.asyncio
    async def test_URL去重(self) -> None:
        s1 = MockNewsSource(name="src1")
        s1.search_result = [
            NewsItem(title="新闻A", source="src1", url="https://same.com/1")
        ]
        s2 = MockNewsSource(name="src2")
        s2.search_result = [
            NewsItem(title="新闻A副本", source="src2", url="https://same.com/1")
        ]
        mgr = self._make_manager(s1, s2)
        items = await mgr.search("新闻")
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_空URL不去重(self) -> None:
        s1 = MockNewsSource(name="src1")
        s1.search_result = [
            NewsItem(title="无URL新闻1", source="src1", url="")
        ]
        s2 = MockNewsSource(name="src2")
        s2.search_result = [
            NewsItem(title="无URL新闻2", source="src2", url="")
        ]
        mgr = self._make_manager(s1, s2)
        items = await mgr.search("新闻")
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_limit限制(self) -> None:
        source = MockNewsSource(name="多新闻源")
        source.search_result = [
            NewsItem(
                title=f"新闻{i}",
                source="src",
                url=f"https://example.com/{i}",
            )
            for i in range(50)
        ]
        mgr = self._make_manager(source)
        items = await mgr.search("新闻", limit=5)
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_get_stock_news(self) -> None:
        source = MockNewsSource(name="stock_src")
        source.stock_news_result = [
            NewsItem(
                title="平安银行利好",
                source="stock_src",
                url="https://example.com/stock/1",
            )
        ]
        mgr = self._make_manager(source)
        items = await mgr.get_stock_news("000001")
        assert len(items) == 1
        assert items[0].title == "平安银行利好"

    def test_source_count(self) -> None:
        mgr = NewsManager()
        assert mgr.source_count == 0
        mgr.register(MockNewsSource(name="a"))
        assert mgr.source_count == 1
        mgr.register(MockNewsSource(name="b"))
        assert mgr.source_count == 2

    def test_get_stats(self) -> None:
        mgr = NewsManager()
        mgr.register(MockNewsSource(name="src1"))
        stats = mgr.get_stats()
        assert stats["src1"] == {"success": 0, "failure": 0}

    @pytest.mark.asyncio
    async def test_不可用源被跳过_is_available异常(self) -> None:
        """is_available 本身抛异常时应跳过该源。"""

        class BrokenSource(MockNewsSource):
            async def is_available(self) -> bool:
                raise RuntimeError("检查可用性爆炸")

        broken = BrokenSource(name="broken")
        ok = MockNewsSource(name="ok")
        ok.search_result = [
            NewsItem(title="正常新闻", source="ok", url="https://ok.com")
        ]
        mgr = self._make_manager(broken, ok)
        items = await mgr.search("测试")
        assert len(items) == 1


# ===================== 去重排序工具函数测试 =====================


class TestDeduplicateAndSort:
    """_deduplicate_and_sort 工具函数测试。"""

    def test_按时间倒序(self) -> None:
        items = [
            NewsItem(
                title="旧",
                source="s",
                url="https://a.com",
                published_at=datetime(2026, 3, 28),
            ),
            NewsItem(
                title="新",
                source="s",
                url="https://b.com",
                published_at=datetime(2026, 3, 30),
            ),
        ]
        result = _deduplicate_and_sort(items, 10)
        assert result[0].title == "新"
        assert result[1].title == "旧"

    def test_None时间排在最后(self) -> None:
        items = [
            NewsItem(title="无时间", source="s", url="https://a.com"),
            NewsItem(
                title="有时间",
                source="s",
                url="https://b.com",
                published_at=datetime(2026, 3, 30),
            ),
        ]
        result = _deduplicate_and_sort(items, 10)
        assert result[0].title == "有时间"
        assert result[1].title == "无时间"

    def test_URL去重保留第一条(self) -> None:
        items = [
            NewsItem(title="第一条", source="s1", url="https://same.com"),
            NewsItem(title="第二条", source="s2", url="https://same.com"),
        ]
        result = _deduplicate_and_sort(items, 10)
        assert len(result) == 1
        assert result[0].title == "第一条"

    def test_空列表(self) -> None:
        assert _deduplicate_and_sort([], 10) == []

    def test_limit截断(self) -> None:
        items = [
            NewsItem(title=f"n{i}", source="s", url=f"https://e.com/{i}")
            for i in range(20)
        ]
        result = _deduplicate_and_sort(items, 5)
        assert len(result) == 5

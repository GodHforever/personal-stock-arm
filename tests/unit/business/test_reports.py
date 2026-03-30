"""研报管理模块单元测试。

测试策略：
- Mock LLM 和 NewsManager 的所有外部调用
- 测试数据模型校验
- 测试研报搜索和筛选
- 测试 LLM 摘要生成
- 测试错误处理
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.analysis.llm.base import LLMResponse
from src.business.reports.manager import ReportManager
from src.business.reports.models import ReportFilter, ResearchReportSummary
from src.data.news.base import NewsItem


# ===================== 数据模型测试 =====================


class TestResearchReportSummary:
    """ResearchReportSummary 数据模型测试。"""

    def test_创建完整摘要(self) -> None:
        summary = ResearchReportSummary(
            title="浦发银行深度报告：零售转型再加速",
            source="中信证券",
            url="https://example.com/report/1",
            published_at=datetime(2026, 3, 30, 10, 0),
            stock_code="600000",
            stock_name="浦发银行",
            industry="银行",
            rating="买入",
            rating_change="维持",
            target_price=12.50,
            core_views=["零售业务占比提升", "不良率持续下降"],
            logic_chain="零售转型→非利息收入增长→ROE提升",
            risk_alerts=["利率下行压缩息差", "信用风险暴露"],
            summary_markdown="## 研报摘要\n...",
        )
        assert summary.title == "浦发银行深度报告：零售转型再加速"
        assert summary.source == "中信证券"
        assert summary.rating == "买入"
        assert summary.target_price == 12.50
        assert len(summary.core_views) == 2
        assert len(summary.risk_alerts) == 2

    def test_创建最小摘要(self) -> None:
        summary = ResearchReportSummary()
        assert summary.title == ""
        assert summary.stock_code == ""
        assert summary.rating == ""
        assert summary.target_price is None
        assert summary.core_views == []
        assert summary.risk_alerts == []
        assert summary.errors == []

    def test_评级变化字段(self) -> None:
        summary = ResearchReportSummary(
            rating="增持",
            rating_change="上调",
        )
        assert summary.rating == "增持"
        assert summary.rating_change == "上调"


class TestReportFilter:
    """ReportFilter 筛选条件测试。"""

    def test_默认值(self) -> None:
        f = ReportFilter()
        assert f.industry == ""
        assert f.stock_code == ""
        assert f.rating == ""
        assert f.limit == 20

    def test_自定义值(self) -> None:
        f = ReportFilter(
            industry="银行",
            stock_code="600000",
            rating="买入",
            limit=10,
        )
        assert f.industry == "银行"
        assert f.stock_code == "600000"
        assert f.rating == "买入"
        assert f.limit == 10


# ===================== ReportManager 测试 =====================


def _make_manager(
    llm_content: str = "## 研报摘要\n测试内容",
    llm_success: bool = True,
    news_items: list[NewsItem] | None = None,
    news_error: bool = False,
) -> tuple[ReportManager, AsyncMock, AsyncMock]:
    """构造带 mock 依赖的 ReportManager。"""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=LLMResponse(
            content=llm_content,
            success=llm_success,
            error=None if llm_success else "模拟失败",
        )
    )

    mock_news = AsyncMock()
    if news_error:
        mock_news.search = AsyncMock(
            side_effect=RuntimeError("搜索失败")
        )
    else:
        mock_news.search = AsyncMock(
            return_value=news_items
            if news_items is not None
            else [
                NewsItem(
                    title="浦发银行深度报告",
                    source="中信证券",
                    url="https://example.com/report/1",
                    published_at=datetime(2026, 3, 30),
                ),
            ]
        )

    manager = ReportManager(llm=mock_llm, news_manager=mock_news)
    return manager, mock_llm, mock_news


class TestReportManager:
    """ReportManager 研报管理器测试。"""

    @pytest.mark.asyncio
    async def test_默认搜索(self) -> None:
        manager, _, _ = _make_manager()
        results = await manager.search_reports()
        assert len(results) == 1
        assert results[0].title == "浦发银行深度报告"
        assert results[0].source == "中信证券"

    @pytest.mark.asyncio
    async def test_按行业筛选(self) -> None:
        manager, _, mock_news = _make_manager()
        filters = ReportFilter(industry="银行")
        results = await manager.search_reports(filters)
        assert len(results) == 1
        # 验证搜索关键词包含行业
        query = mock_news.search.call_args[0][0]
        assert "银行" in query

    @pytest.mark.asyncio
    async def test_按个股筛选(self) -> None:
        manager, _, mock_news = _make_manager()
        filters = ReportFilter(stock_code="600000")
        results = await manager.search_reports(filters)
        assert len(results) == 1
        assert results[0].stock_code == "600000"
        query = mock_news.search.call_args[0][0]
        assert "600000" in query

    @pytest.mark.asyncio
    async def test_按评级筛选(self) -> None:
        manager, _, mock_news = _make_manager()
        filters = ReportFilter(rating="买入")
        await manager.search_reports(filters)
        query = mock_news.search.call_args[0][0]
        assert "买入" in query

    @pytest.mark.asyncio
    async def test_搜索失败返回空列表(self) -> None:
        manager, _, _ = _make_manager(news_error=True)
        results = await manager.search_reports()
        assert results == []

    @pytest.mark.asyncio
    async def test_limit参数传递(self) -> None:
        manager, _, mock_news = _make_manager()
        filters = ReportFilter(limit=5)
        await manager.search_reports(filters)
        assert mock_news.search.call_args[1]["limit"] == 5

    @pytest.mark.asyncio
    async def test_成功生成摘要(self) -> None:
        manager, _, _ = _make_manager(
            llm_content="## 研报摘要\n核心观点分析..."
        )
        result = await manager.summarize("https://example.com/report/1")
        assert result.title == "浦发银行深度报告"
        assert result.source == "中信证券"
        assert result.url == "https://example.com/report/1"
        assert "研报摘要" in result.summary_markdown
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_LLM失败记录错误(self) -> None:
        manager, _, _ = _make_manager(llm_success=False)
        result = await manager.summarize("https://example.com/report/1")
        assert result.summary_markdown == ""
        assert len(result.errors) == 1
        assert "LLM 调用失败" in result.errors[0]

    @pytest.mark.asyncio
    async def test_新闻搜索失败时摘要报错(self) -> None:
        manager, _, _ = _make_manager(news_error=True)
        result = await manager.summarize("https://example.com/report/1")
        assert len(result.errors) == 1
        assert "获取研报信息失败" in result.errors[0]

    @pytest.mark.asyncio
    async def test_无新闻时使用默认标题(self) -> None:
        manager, _, _ = _make_manager(news_items=[])
        result = await manager.summarize("https://example.com/report/1")
        assert result.title == "未知研报"
        assert result.source == "未知来源"

    @pytest.mark.asyncio
    async def test_搜索关键词构建_无筛选(self) -> None:
        query = ReportManager._build_search_query(ReportFilter())
        assert "券商研报" in query

    @pytest.mark.asyncio
    async def test_搜索关键词构建_组合筛选(self) -> None:
        filters = ReportFilter(
            industry="银行",
            stock_code="600000",
            rating="买入",
        )
        query = ReportManager._build_search_query(filters)
        assert "买入" in query
        assert "600000" in query
        assert "银行" in query

    @pytest.mark.asyncio
    async def test_摘要prompt包含研报信息(self) -> None:
        news = [
            NewsItem(
                title="浦发银行2025年报",
                source="中信证券",
                url="https://example.com/report/1",
                summary="浦发银行零售业务持续增长...",
            )
        ]
        manager, mock_llm, _ = _make_manager(news_items=news)
        await manager.summarize("https://example.com/report/1")

        prompt = mock_llm.complete.call_args[0][0]
        assert "浦发银行2025年报" in prompt
        assert "零售业务持续增长" in prompt

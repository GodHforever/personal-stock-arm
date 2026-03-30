"""财报处理模块单元测试。

测试策略：
- Mock LLM 和 NewsManager 的所有外部调用
- 测试数据模型校验
- 测试扫描范围（watchlist/all）
- 测试单股票失败不阻塞其他股票
- 测试财报季判断
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.analysis.llm.base import LLMResponse
from src.business.earnings.models import EarningsSummary
from src.business.earnings.processor import EarningsProcessor
from src.data.news.base import NewsItem


# ===================== 数据模型测试 =====================


class TestEarningsSummary:
    """EarningsSummary 数据模型测试。"""

    def test_创建完整摘要(self) -> None:
        summary = EarningsSummary(
            stock_code="600000",
            stock_name="浦发银行",
            report_period="2025Q3",
            report_date=date(2025, 10, 30),
            revenue=150.5,
            net_profit=45.2,
            gross_margin=35.0,
            net_margin=30.0,
            revenue_yoy=10.5,
            net_profit_yoy=8.3,
            summary_markdown="## 浦发银行 2025Q3 财报摘要\n...",
        )
        assert summary.stock_code == "600000"
        assert summary.stock_name == "浦发银行"
        assert summary.revenue == 150.5
        assert summary.net_profit_yoy == 8.3
        assert summary.summary_markdown.startswith("## 浦发银行")

    def test_创建最小摘要(self) -> None:
        summary = EarningsSummary(stock_code="000001")
        assert summary.stock_code == "000001"
        assert summary.stock_name == ""
        assert summary.revenue is None
        assert summary.net_profit is None
        assert summary.summary_markdown == ""
        assert summary.errors == []

    def test_带错误信息的摘要(self) -> None:
        summary = EarningsSummary(
            stock_code="000001",
            errors=["LLM 调用失败", "数据源不可用"],
        )
        assert len(summary.errors) == 2


# ===================== 财报季判断测试 =====================


class TestEarningsSeason:
    """财报季月份判断测试。"""

    def test_4月是财报季(self) -> None:
        assert EarningsProcessor.is_earnings_season(date(2026, 4, 15)) is True

    def test_8月是财报季(self) -> None:
        assert EarningsProcessor.is_earnings_season(date(2026, 8, 1)) is True

    def test_10月是财报季(self) -> None:
        assert EarningsProcessor.is_earnings_season(date(2026, 10, 30)) is True

    def test_1月不是财报季(self) -> None:
        assert EarningsProcessor.is_earnings_season(date(2026, 1, 15)) is False

    def test_6月不是财报季(self) -> None:
        assert EarningsProcessor.is_earnings_season(date(2026, 6, 1)) is False

    def test_默认使用今天日期(self) -> None:
        # 只验证不报错
        result = EarningsProcessor.is_earnings_season()
        assert isinstance(result, bool)


# ===================== EarningsProcessor 测试 =====================


def _make_processor(
    llm_content: str = "## 财报摘要\n测试内容",
    llm_success: bool = True,
    news_items: list[NewsItem] | None = None,
    watchlist: list[str] | None = None,
) -> tuple[EarningsProcessor, AsyncMock, AsyncMock]:
    """构造带 mock 依赖的 EarningsProcessor。"""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=LLMResponse(
            content=llm_content,
            success=llm_success,
            error=None if llm_success else "模拟失败",
        )
    )

    mock_news = AsyncMock()
    mock_news.search = AsyncMock(
        return_value=news_items if news_items is not None else []
    )

    processor = EarningsProcessor(
        llm=mock_llm,
        news_manager=mock_news,
        watchlist_codes=watchlist if watchlist is not None else ["600000", "000001"],
    )
    return processor, mock_llm, mock_news


class TestEarningsProcessor:
    """EarningsProcessor 财报处理器测试。"""

    @pytest.mark.asyncio
    async def test_watchlist范围扫描(self) -> None:
        processor, mock_llm, _ = _make_processor(
            watchlist=["600000", "000001"]
        )
        results = await processor.scan_reports("watchlist")
        assert len(results) == 2
        assert results[0].stock_code == "600000"
        assert results[1].stock_code == "000001"
        assert mock_llm.complete.call_count == 2

    @pytest.mark.asyncio
    async def test_all范围扫描(self) -> None:
        processor, mock_llm, _ = _make_processor(
            watchlist=["600000"]
        )
        results = await processor.scan_reports("all")
        assert len(results) == 1
        assert mock_llm.complete.call_count == 1

    @pytest.mark.asyncio
    async def test_空列表跳过扫描(self) -> None:
        processor, mock_llm, _ = _make_processor(watchlist=[])
        results = await processor.scan_reports("watchlist")
        assert results == []
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_未知scope默认watchlist(self) -> None:
        processor, _, _ = _make_processor(watchlist=["600000"])
        results = await processor.scan_reports("unknown_scope")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_LLM成功生成摘要(self) -> None:
        processor, _, _ = _make_processor(
            llm_content="## 财报摘要\n关键指标分析..."
        )
        result = await processor.summarize_single("600000")
        assert result.stock_code == "600000"
        assert "财报摘要" in result.summary_markdown
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_LLM失败记录错误(self) -> None:
        processor, _, _ = _make_processor(llm_success=False)
        result = await processor.summarize_single("600000")
        assert result.stock_code == "600000"
        assert result.summary_markdown == ""
        assert len(result.errors) == 1
        assert "LLM 调用失败" in result.errors[0]

    @pytest.mark.asyncio
    async def test_含新闻数据的摘要(self) -> None:
        news = [
            NewsItem(
                title="浦发银行三季报营收增长10%",
                source="财联社",
                url="https://example.com/news/1",
            ),
            NewsItem(
                title="浦发银行业绩超预期",
                source="东方财富",
            ),
        ]
        processor, mock_llm, _ = _make_processor(news_items=news)
        await processor.summarize_single("600000")

        # 验证 prompt 包含新闻信息
        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0]
        assert "浦发银行三季报" in prompt
        assert "业绩超预期" in prompt

    @pytest.mark.asyncio
    async def test_单股票失败不阻塞(self) -> None:
        """第一只股票 LLM 调用抛异常，第二只正常。"""
        mock_llm = AsyncMock()
        call_count = 0

        async def side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("模拟网络超时")
            return LLMResponse(content="摘要内容", success=True)

        mock_llm.complete = AsyncMock(side_effect=side_effect)
        mock_news = AsyncMock()
        mock_news.search = AsyncMock(return_value=[])

        processor = EarningsProcessor(
            llm=mock_llm,
            news_manager=mock_news,
            watchlist_codes=["600000", "000001"],
        )

        results = await processor.scan_reports("watchlist")
        assert len(results) == 2
        # 第一只失败
        assert len(results[0].errors) == 1
        assert "扫描失败" in results[0].errors[0]
        # 第二只成功
        assert results[1].summary_markdown == "摘要内容"
        assert results[1].errors == []

    @pytest.mark.asyncio
    async def test_新闻搜索关键词包含股票代码(self) -> None:
        processor, _, mock_news = _make_processor()
        await processor.summarize_single("600000")
        call_args = mock_news.search.call_args
        assert "600000" in call_args[0][0]
        assert "财报" in call_args[0][0]

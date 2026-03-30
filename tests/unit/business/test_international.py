"""国际金融简报模块单元测试。

测试策略：
- Mock IntlDataManager、NewsManager、LLMRouter 的所有外部调用
- 测试数据模型校验
- 测试简报生成流程
- 测试数据源失败降级处理
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.analysis.llm.base import LLMResponse
from src.business.international.briefing import InternationalBriefingGenerator
from src.business.international.models import BriefingResult, MarketSnapshot
from src.data.international.base import IntlQuote
from src.data.news.base import NewsItem


# ===================== 数据模型测试 =====================


class TestMarketSnapshot:
    """MarketSnapshot 数据模型测试。"""

    def test_创建快照(self) -> None:
        snapshot = MarketSnapshot(
            index_name="道琼斯工业平均指数",
            symbol=".DJI.US",
            price=39000.50,
            change_pct=1.25,
        )
        assert snapshot.index_name == "道琼斯工业平均指数"
        assert snapshot.price == 39000.50
        assert snapshot.change_pct == 1.25

    def test_默认值(self) -> None:
        snapshot = MarketSnapshot(index_name="测试指数")
        assert snapshot.symbol == ""
        assert snapshot.price == 0.0
        assert snapshot.change_pct == 0.0


class TestBriefingResult:
    """BriefingResult 数据模型测试。"""

    def test_创建完整简报(self) -> None:
        result = BriefingResult(
            briefing_date=date(2026, 3, 30),
            market_snapshots=[
                MarketSnapshot(
                    index_name="道琼斯",
                    symbol=".DJI.US",
                    price=39000.0,
                    change_pct=1.0,
                )
            ],
            briefing_markdown="# 简报内容\n...",
            news_count=10,
        )
        assert result.briefing_date == date(2026, 3, 30)
        assert len(result.market_snapshots) == 1
        assert result.news_count == 10

    def test_创建最小简报(self) -> None:
        result = BriefingResult(briefing_date=date(2026, 3, 30))
        assert result.market_snapshots == []
        assert result.briefing_markdown == ""
        assert result.news_count == 0
        assert result.errors == []


# ===================== InternationalBriefingGenerator 测试 =====================


def _make_generator(
    llm_content: str = "# 国际金融简报\n测试内容",
    llm_success: bool = True,
    indices: list[IntlQuote] | None = None,
    news_items: list[NewsItem] | None = None,
    indices_error: bool = False,
    news_error: bool = False,
) -> tuple[InternationalBriefingGenerator, AsyncMock, AsyncMock, AsyncMock]:
    """构造带 mock 依赖的 InternationalBriefingGenerator。"""
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(
        return_value=LLMResponse(
            content=llm_content,
            success=llm_success,
            error=None if llm_success else "模拟失败",
        )
    )

    mock_intl = AsyncMock()
    if indices_error:
        mock_intl.get_market_indices = AsyncMock(
            side_effect=RuntimeError("指数数据获取失败")
        )
    else:
        mock_intl.get_market_indices = AsyncMock(
            return_value=indices
            or [
                IntlQuote(
                    symbol=".DJI.US",
                    name="道琼斯工业平均指数",
                    price=39000.0,
                    change_pct=1.25,
                ),
                IntlQuote(
                    symbol=".SPX.US",
                    name="标普500指数",
                    price=5200.0,
                    change_pct=0.80,
                ),
            ]
        )

    mock_news = AsyncMock()
    if news_error:
        mock_news.search = AsyncMock(
            side_effect=RuntimeError("新闻获取失败")
        )
    else:
        mock_news.search = AsyncMock(
            return_value=news_items
            or [
                NewsItem(
                    title="美联储暗示降息",
                    source="路透社",
                    url="https://example.com/1",
                )
            ]
        )

    generator = InternationalBriefingGenerator(
        llm=mock_llm,
        intl_data=mock_intl,
        news_manager=mock_news,
    )
    return generator, mock_llm, mock_intl, mock_news


class TestInternationalBriefingGenerator:
    """InternationalBriefingGenerator 简报生成器测试。"""

    @pytest.mark.asyncio
    async def test_成功生成简报(self) -> None:
        generator, _, _, _ = _make_generator()
        result = await generator.generate(date(2026, 3, 30))

        assert result.briefing_date == date(2026, 3, 30)
        assert len(result.market_snapshots) == 2
        assert result.market_snapshots[0].index_name == "道琼斯工业平均指数"
        assert result.briefing_markdown == "# 国际金融简报\n测试内容"
        assert result.news_count == 1
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_默认日期为今天(self) -> None:
        generator, _, _, _ = _make_generator()
        result = await generator.generate()
        assert result.briefing_date == date.today()

    @pytest.mark.asyncio
    async def test_LLM调用包含市场数据(self) -> None:
        generator, mock_llm, _, _ = _make_generator()
        await generator.generate(date(2026, 3, 30))

        prompt = mock_llm.complete.call_args[0][0]
        assert "道琼斯工业平均指数" in prompt
        assert "39000" in prompt

    @pytest.mark.asyncio
    async def test_LLM调用包含新闻(self) -> None:
        generator, mock_llm, _, _ = _make_generator()
        await generator.generate(date(2026, 3, 30))

        prompt = mock_llm.complete.call_args[0][0]
        assert "美联储暗示降息" in prompt

    @pytest.mark.asyncio
    async def test_LLM失败记录错误(self) -> None:
        generator, _, _, _ = _make_generator(llm_success=False)
        result = await generator.generate(date(2026, 3, 30))

        assert result.briefing_markdown == ""
        assert len(result.errors) == 1
        assert "LLM 调用失败" in result.errors[0]

    @pytest.mark.asyncio
    async def test_指数数据失败降级(self) -> None:
        generator, _, _, _ = _make_generator(indices_error=True)
        result = await generator.generate(date(2026, 3, 30))

        assert result.market_snapshots == []
        assert any("指数数据获取失败" in e for e in result.errors)
        # LLM 仍然被调用（带"暂无市场数据"）
        assert result.briefing_markdown != ""

    @pytest.mark.asyncio
    async def test_新闻数据失败降级(self) -> None:
        generator, _, _, _ = _make_generator(news_error=True)
        result = await generator.generate(date(2026, 3, 30))

        assert result.news_count == 0
        assert any("新闻获取失败" in e for e in result.errors)
        # LLM 仍然被调用
        assert result.briefing_markdown != ""

    @pytest.mark.asyncio
    async def test_所有数据源失败仍返回结果(self) -> None:
        generator, _, _, _ = _make_generator(
            indices_error=True, news_error=True
        )
        result = await generator.generate(date(2026, 3, 30))
        assert result.briefing_date == date(2026, 3, 30)
        assert len(result.errors) >= 2

    @pytest.mark.asyncio
    async def test_空指数列表格式化(self) -> None:
        text = InternationalBriefingGenerator._format_market_data([])
        assert text == "暂无市场数据"

    @pytest.mark.asyncio
    async def test_指数上涨格式化(self) -> None:
        snapshots = [
            MarketSnapshot(
                index_name="道琼斯",
                symbol=".DJI.US",
                price=39000.0,
                change_pct=1.25,
            )
        ]
        text = InternationalBriefingGenerator._format_market_data(snapshots)
        assert "↑" in text
        assert "1.25%" in text

    @pytest.mark.asyncio
    async def test_指数下跌格式化(self) -> None:
        snapshots = [
            MarketSnapshot(
                index_name="恒生指数",
                symbol=".HSI.HK",
                price=16000.0,
                change_pct=-2.50,
            )
        ]
        text = InternationalBriefingGenerator._format_market_data(snapshots)
        assert "↓" in text
        assert "2.50%" in text

"""自选股管理与分析流水线单元测试。"""

from __future__ import annotations

import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.analysis.llm.base import LLMResponse
from src.analysis.technical.models import TechnicalSummary
from src.business.watchlist.manager import WatchlistManager
from src.business.watchlist.models import (
    AnalysisRecord,
    LLMVerdict,
    StockAnalysisResult,
    WatchlistGroup,
)
from src.business.watchlist.pipeline import StockAnalysisPipeline
from src.data.a_share.base import Fundamentals, KlineBar
from src.data.news.base import NewsItem


# ============================================================
# 辅助函数
# ============================================================


class _MockWatchlistGroup:
    """用于测试的 WatchlistGroup 替代品，避免 SQLAlchemy 内部状态问题。"""

    def __init__(
        self,
        name: str = "测试分组",
        stocks_json: str = "[]",
        description: str = "",
        strategy: str = "default",
        push_frequency: str = "daily",
    ) -> None:
        self.name = name
        self.description = description
        self.strategy = strategy
        self.push_frequency = push_frequency
        self.stocks_json = stocks_json

    @property
    def stocks(self) -> list[str]:
        return json.loads(self.stocks_json)

    @stocks.setter
    def stocks(self, value: list[str]) -> None:
        self.stocks_json = json.dumps(value, ensure_ascii=False)


def _make_mock_group(
    name: str = "测试分组",
    stocks_json: str = "[]",
    **kwargs: str,
) -> _MockWatchlistGroup:
    """创建 WatchlistGroup 的替代测试实例。"""
    return _MockWatchlistGroup(name=name, stocks_json=stocks_json, **kwargs)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture()
def mock_db() -> MagicMock:
    """模拟 Database 实例。"""
    db = MagicMock()
    session = AsyncMock()

    # Database.session() 是 asynccontextmanager，返回 AsyncContextManager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    db.session.return_value = ctx
    db._mock_session = session  # 方便测试中访问
    return db


@pytest.fixture()
def mock_data_manager() -> AsyncMock:
    """模拟 DataFetcherManager。"""
    manager = AsyncMock()
    manager.get_kline.return_value = [
        KlineBar(
            date=f"2024-01-{i + 1:02d}",
            open=10.0 + i * 0.1,
            high=10.5 + i * 0.1,
            low=9.5 + i * 0.1,
            close=10.0 + i * 0.1,
            volume=1000.0,
        )
        for i in range(60)
    ]
    manager.get_fundamentals.return_value = Fundamentals(
        code="000001",
        name="平安银行",
        pe_ttm=8.5,
        pb=0.9,
        market_cap=300000000000.0,
        revenue=170000000000.0,
        net_profit=45000000000.0,
    )
    return manager


@pytest.fixture()
def mock_news_manager() -> AsyncMock:
    """模拟 NewsManager。"""
    manager = AsyncMock()
    manager.get_stock_news.return_value = [
        NewsItem(
            title="平安银行发布年度业绩报告",
            source="财经新闻",
            url="https://example.com/1",
        ),
        NewsItem(
            title="银行板块集体走强",
            source="券商研报",
            url="https://example.com/2",
        ),
    ]
    return manager


@pytest.fixture()
def mock_llm() -> AsyncMock:
    """模拟 LLM 提供者。"""
    llm = AsyncMock()
    verdict = LLMVerdict(
        signal="看多",
        confidence=75,
        reasoning="基本面稳健，技术面偏多，新闻面中性",
        risk_alerts=["注意银行板块政策风险"],
    )
    llm.complete.return_value = LLMResponse(
        success=True,
        content=json.dumps(verdict.model_dump(), ensure_ascii=False),
        parsed=verdict,
        model="gpt-4",
        input_tokens=100,
        output_tokens=200,
        latency_ms=1000,
    )
    return llm


@pytest.fixture()
def mock_prompt_manager() -> MagicMock:
    """模拟 PromptManager。"""
    pm = MagicMock()
    pm.render.return_value = "请分析股票 000001"
    return pm


@pytest.fixture()
def pipeline(
    mock_db: MagicMock,
    mock_data_manager: AsyncMock,
    mock_news_manager: AsyncMock,
    mock_llm: AsyncMock,
    mock_prompt_manager: MagicMock,
) -> StockAnalysisPipeline:
    """构造分析流水线实例。"""
    return StockAnalysisPipeline(
        db=mock_db,
        data_manager=mock_data_manager,
        news_manager=mock_news_manager,
        technical_analyzer=MagicMock(
            analyze=MagicMock(
                return_value=TechnicalSummary(
                    ma_alignment="多头排列",
                    macd_signal="金叉",
                    rsi_value=55.0,
                    rsi_status="正常",
                    volume_trend="正常",
                    overall_score=60,
                    summary="技术面偏多。均线呈多头排列，趋势向上；MACD金叉；RSI正常。",
                )
            )
        ),
        llm_provider=mock_llm,
        prompt_manager=mock_prompt_manager,
    )


# ============================================================
# WatchlistGroup 模型测试
# ============================================================


class TestWatchlistGroupModel:
    """WatchlistGroup ORM 模型测试。"""

    def test_stocks_property_get(self) -> None:
        """stocks 属性正确解析 JSON。"""
        group = WatchlistGroup(
            name="test", stocks_json='["000001", "600036"]'
        )
        assert group.stocks == ["000001", "600036"]

    def test_stocks_property_set(self) -> None:
        """stocks 属性正确序列化为 JSON。"""
        group = WatchlistGroup(name="test")
        group.stocks = ["000001", "600036"]
        assert json.loads(group.stocks_json) == ["000001", "600036"]

    def test_stocks_empty_list(self) -> None:
        """空列表正确处理。"""
        group = WatchlistGroup(name="test", stocks_json="[]")
        assert group.stocks == []

        group.stocks = []
        assert group.stocks_json == "[]"


# ============================================================
# LLMVerdict 模型测试
# ============================================================


class TestLLMVerdict:
    """LLMVerdict Pydantic Schema 测试。"""

    def test_default_values(self) -> None:
        """默认值正确。"""
        verdict = LLMVerdict()
        assert verdict.signal == "中性"
        assert verdict.confidence == 50
        assert verdict.reasoning == ""
        assert verdict.risk_alerts == []

    def test_custom_values(self) -> None:
        """自定义值正确。"""
        verdict = LLMVerdict(
            signal="看多",
            confidence=85,
            reasoning="技术面强势",
            risk_alerts=["政策风险", "流动性风险"],
        )
        assert verdict.signal == "看多"
        assert verdict.confidence == 85
        assert len(verdict.risk_alerts) == 2

    def test_confidence_range(self) -> None:
        """置信度边界检查。"""
        # 有效值
        LLMVerdict(confidence=0)
        LLMVerdict(confidence=100)
        # 无效值
        with pytest.raises(Exception):
            LLMVerdict(confidence=-1)
        with pytest.raises(Exception):
            LLMVerdict(confidence=101)

    def test_serialization(self) -> None:
        """序列化/反序列化一致。"""
        verdict = LLMVerdict(
            signal="看空", confidence=30, reasoning="基本面恶化"
        )
        data = verdict.model_dump()
        restored = LLMVerdict.model_validate(data)
        assert restored.signal == "看空"
        assert restored.confidence == 30


# ============================================================
# StockAnalysisResult 模型测试
# ============================================================


class TestStockAnalysisResult:
    """StockAnalysisResult Pydantic Schema 测试。"""

    def test_minimal(self) -> None:
        """最小字段创建。"""
        result = StockAnalysisResult(stock_code="000001")
        assert result.stock_code == "000001"
        assert result.stock_name == ""
        assert result.llm_verdict.signal == "中性"

    def test_full_result(self) -> None:
        """完整字段创建。"""
        result = StockAnalysisResult(
            stock_code="000001",
            stock_name="平安银行",
            analysis_date="2024-03-30",
            technical_summary="技术面偏多",
            technical_score=60,
            pe_ttm=8.5,
            pb=0.9,
            market_cap=300000000000.0,
            news_summary="平安银行发布年报",
            news_count=5,
            llm_verdict=LLMVerdict(signal="看多", confidence=75),
            errors=[],
        )
        assert result.pe_ttm == 8.5
        assert result.llm_verdict.signal == "看多"

    def test_json_serialization(self) -> None:
        """JSON 序列化。"""
        result = StockAnalysisResult(stock_code="600036")
        data = json.dumps(result.model_dump(), ensure_ascii=False)
        assert "600036" in data


# ============================================================
# WatchlistManager 测试（使用 mock DB）
# ============================================================


class TestWatchlistManager:
    """WatchlistManager 分组 CRUD 测试。"""

    @pytest.fixture()
    def manager(self, mock_db: MagicMock) -> WatchlistManager:
        return WatchlistManager(mock_db)

    @pytest.mark.asyncio()
    async def test_add_group(self, manager: WatchlistManager, mock_db: MagicMock) -> None:
        """创建分组。"""
        session = mock_db._mock_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        group = await manager.add_group(
            "重仓股",
            description="主要持仓",
            strategy="aggressive",
            stocks=["000001", "600036"],
        )
        assert group.name == "重仓股"
        assert group.description == "主要持仓"
        assert group.strategy == "aggressive"
        assert group.stocks == ["000001", "600036"]
        session.add.assert_called_once()

    @pytest.mark.asyncio()
    async def test_add_group_duplicate(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """创建重名分组应抛出异常。"""
        session = mock_db._mock_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = _make_mock_group("重仓股")
        session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="已存在"):
            await manager.add_group("重仓股")

    @pytest.mark.asyncio()
    async def test_remove_group_exists(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """删除存在的分组。"""
        session = mock_db._mock_session
        mock_group = _make_mock_group("重仓股")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        session.execute.return_value = mock_result

        result = await manager.remove_group("重仓股")
        assert result is True
        session.delete.assert_called_once_with(mock_group)

    @pytest.mark.asyncio()
    async def test_remove_group_not_exists(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """删除不存在的分组返回 False。"""
        session = mock_db._mock_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await manager.remove_group("不存在")
        assert result is False

    @pytest.mark.asyncio()
    async def test_list_groups(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """查询分组列表。"""
        session = mock_db._mock_session
        g1 = _make_mock_group("分组1")
        g2 = _make_mock_group("分组2")

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [g1, g2]
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

        groups = await manager.list_groups()
        assert len(groups) == 2
        assert groups[0].name == "分组1"

    @pytest.mark.asyncio()
    async def test_add_stock(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """向分组添加股票。"""
        session = mock_db._mock_session
        group = _make_mock_group("重仓股", stocks_json='["000001"]')

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = group
        session.execute.return_value = mock_result

        result = await manager.add_stock("重仓股", "600036")
        assert result is True
        assert "600036" in group.stocks

    @pytest.mark.asyncio()
    async def test_add_stock_duplicate(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """添加已存在的股票返回 False。"""
        session = mock_db._mock_session
        group = _make_mock_group("重仓股", stocks_json='["000001"]')

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = group
        session.execute.return_value = mock_result

        result = await manager.add_stock("重仓股", "000001")
        assert result is False

    @pytest.mark.asyncio()
    async def test_add_stock_group_not_found(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """向不存在的分组添加股票返回 False。"""
        session = mock_db._mock_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        result = await manager.add_stock("不存在", "000001")
        assert result is False

    @pytest.mark.asyncio()
    async def test_remove_stock(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """从分组移除股票。"""
        session = mock_db._mock_session
        group = _make_mock_group("重仓股", stocks_json='["000001", "600036"]')

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = group
        session.execute.return_value = mock_result

        result = await manager.remove_stock("重仓股", "000001")
        assert result is True
        assert "000001" not in group.stocks
        assert "600036" in group.stocks

    @pytest.mark.asyncio()
    async def test_remove_stock_not_in_group(
        self, manager: WatchlistManager, mock_db: MagicMock
    ) -> None:
        """移除不在分组中的股票返回 False。"""
        session = mock_db._mock_session
        group = _make_mock_group("重仓股", stocks_json='["000001"]')

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = group
        session.execute.return_value = mock_result

        result = await manager.remove_stock("重仓股", "999999")
        assert result is False


# ============================================================
# StockAnalysisPipeline 测试
# ============================================================


class TestStockAnalysisPipeline:
    """分析流水线测试。"""

    @pytest.mark.asyncio()
    async def test_analyze_stock_success(self, pipeline: StockAnalysisPipeline) -> None:
        """完整分析流程成功。"""
        result = await pipeline.analyze_stock("000001")

        assert result.stock_code == "000001"
        assert result.stock_name == "平安银行"
        assert result.technical_summary != ""
        assert result.technical_score == 60
        assert result.pe_ttm == 8.5
        assert result.pb == 0.9
        assert result.news_count == 2
        assert result.llm_verdict.signal == "看多"
        assert result.llm_verdict.confidence == 75
        assert result.errors == []

    @pytest.mark.asyncio()
    async def test_analyze_stock_technical_failure(
        self,
        mock_db: MagicMock,
        mock_data_manager: AsyncMock,
        mock_news_manager: AsyncMock,
        mock_llm: AsyncMock,
        mock_prompt_manager: MagicMock,
    ) -> None:
        """技术分析失败时降级处理。"""
        mock_data_manager.get_kline.side_effect = Exception("数据源不可用")

        p = StockAnalysisPipeline(
            db=mock_db,
            data_manager=mock_data_manager,
            news_manager=mock_news_manager,
            technical_analyzer=MagicMock(),
            llm_provider=mock_llm,
            prompt_manager=mock_prompt_manager,
        )
        result = await p.analyze_stock("000001")

        assert "技术分析失败" in result.errors[0]
        assert result.technical_summary == "技术分析数据获取失败"
        # 其他部分仍正常
        assert result.stock_name == "平安银行"

    @pytest.mark.asyncio()
    async def test_analyze_stock_fundamentals_failure(
        self,
        mock_db: MagicMock,
        mock_data_manager: AsyncMock,
        mock_news_manager: AsyncMock,
        mock_llm: AsyncMock,
        mock_prompt_manager: MagicMock,
    ) -> None:
        """基本面数据获取失败时降级处理。"""
        mock_data_manager.get_fundamentals.side_effect = Exception("超时")

        p = StockAnalysisPipeline(
            db=mock_db,
            data_manager=mock_data_manager,
            news_manager=mock_news_manager,
            technical_analyzer=MagicMock(
                analyze=MagicMock(
                    return_value=TechnicalSummary(
                        ma_alignment="混乱",
                        macd_signal="中性",
                        rsi_value=50.0,
                        rsi_status="正常",
                        volume_trend="正常",
                        overall_score=0,
                        summary="中性",
                    )
                )
            ),
            llm_provider=mock_llm,
            prompt_manager=mock_prompt_manager,
        )
        result = await p.analyze_stock("000001")

        assert "基本面数据获取失败" in result.errors[0]
        assert result.pe_ttm is None
        # 技术面和新闻仍正常
        assert result.news_count == 2

    @pytest.mark.asyncio()
    async def test_analyze_stock_news_failure(
        self, pipeline: StockAnalysisPipeline, mock_news_manager: AsyncMock
    ) -> None:
        """新闻获取失败时降级处理。"""
        mock_news_manager.get_stock_news.side_effect = Exception("网络错误")

        result = await pipeline.analyze_stock("000001")

        assert any("新闻获取失败" in e for e in result.errors)
        assert result.news_summary == "新闻数据获取失败"
        assert result.news_count == 0

    @pytest.mark.asyncio()
    async def test_analyze_stock_llm_failure(
        self, pipeline: StockAnalysisPipeline, mock_llm: AsyncMock
    ) -> None:
        """LLM 调用失败时降级处理。"""
        mock_llm.complete.return_value = LLMResponse(
            success=False,
            error="API Key 无效",
        )

        result = await pipeline.analyze_stock("000001")

        assert result.llm_verdict.signal == "中性"
        assert result.llm_verdict.confidence == 0
        assert any("LLM" in e for e in result.errors)

    @pytest.mark.asyncio()
    async def test_analyze_stock_llm_exception(
        self, pipeline: StockAnalysisPipeline, mock_llm: AsyncMock
    ) -> None:
        """LLM 调用异常时降级处理。"""
        mock_llm.complete.side_effect = Exception("连接超时")

        result = await pipeline.analyze_stock("000001")

        assert result.llm_verdict.signal == "中性"
        assert result.llm_verdict.confidence == 0
        assert any("LLM" in e for e in result.errors)

    @pytest.mark.asyncio()
    async def test_analyze_stock_no_news(
        self, pipeline: StockAnalysisPipeline, mock_news_manager: AsyncMock
    ) -> None:
        """无新闻时的处理。"""
        mock_news_manager.get_stock_news.return_value = []

        result = await pipeline.analyze_stock("000001")

        assert result.news_summary == "暂无相关新闻"
        assert result.news_count == 0

    @pytest.mark.asyncio()
    async def test_analyze_group(
        self,
        mock_db: MagicMock,
        mock_data_manager: AsyncMock,
        mock_news_manager: AsyncMock,
        mock_llm: AsyncMock,
        mock_prompt_manager: MagicMock,
    ) -> None:
        """分组批量分析。"""
        # 构造 WatchlistManager mock
        wm = AsyncMock()
        group = _make_mock_group("测试分组", stocks_json='["000001", "600036"]')
        wm.get_group.return_value = group

        p = StockAnalysisPipeline(
            db=mock_db,
            data_manager=mock_data_manager,
            news_manager=mock_news_manager,
            technical_analyzer=MagicMock(
                analyze=MagicMock(
                    return_value=TechnicalSummary(
                        ma_alignment="多头排列",
                        macd_signal="金叉",
                        rsi_value=55.0,
                        rsi_status="正常",
                        volume_trend="正常",
                        overall_score=60,
                        summary="技术面偏多",
                    )
                )
            ),
            llm_provider=mock_llm,
            prompt_manager=mock_prompt_manager,
            watchlist_manager=wm,
        )

        results = await p.analyze_group("测试分组")

        assert len(results) == 2
        assert results[0].stock_code == "000001"
        assert results[1].stock_code == "600036"

    @pytest.mark.asyncio()
    async def test_analyze_group_not_found(
        self,
        mock_db: MagicMock,
        mock_data_manager: AsyncMock,
        mock_news_manager: AsyncMock,
        mock_llm: AsyncMock,
        mock_prompt_manager: MagicMock,
    ) -> None:
        """分组不存在时抛出异常。"""
        wm = AsyncMock()
        wm.get_group.return_value = None

        p = StockAnalysisPipeline(
            db=mock_db,
            data_manager=mock_data_manager,
            news_manager=mock_news_manager,
            technical_analyzer=MagicMock(),
            llm_provider=mock_llm,
            prompt_manager=mock_prompt_manager,
            watchlist_manager=wm,
        )

        with pytest.raises(ValueError, match="不存在"):
            await p.analyze_group("不存在的分组")

    @pytest.mark.asyncio()
    async def test_analyze_group_empty(
        self,
        mock_db: MagicMock,
        mock_data_manager: AsyncMock,
        mock_news_manager: AsyncMock,
        mock_llm: AsyncMock,
        mock_prompt_manager: MagicMock,
    ) -> None:
        """空分组返回空列表。"""
        wm = AsyncMock()
        group = _make_mock_group("空分组", stocks_json="[]")
        wm.get_group.return_value = group

        p = StockAnalysisPipeline(
            db=mock_db,
            data_manager=mock_data_manager,
            news_manager=mock_news_manager,
            technical_analyzer=MagicMock(),
            llm_provider=mock_llm,
            prompt_manager=mock_prompt_manager,
            watchlist_manager=wm,
        )

        results = await p.analyze_group("空分组")
        assert results == []

    @pytest.mark.asyncio()
    async def test_analyze_group_partial_failure(
        self,
        mock_db: MagicMock,
        mock_data_manager: AsyncMock,
        mock_news_manager: AsyncMock,
        mock_llm: AsyncMock,
        mock_prompt_manager: MagicMock,
    ) -> None:
        """部分股票分析失败不影响其他。"""
        wm = AsyncMock()
        group = _make_mock_group("部分失败", stocks_json='["000001", "FAIL01"]')
        wm.get_group.return_value = group

        call_count = 0

        async def _kline_side_effect(code: str, **kwargs):
            if code == "FAIL01":
                raise Exception("数据源不可用")
            return mock_data_manager.get_kline.return_value

        mock_data_manager.get_kline.side_effect = _kline_side_effect

        p = StockAnalysisPipeline(
            db=mock_db,
            data_manager=mock_data_manager,
            news_manager=mock_news_manager,
            technical_analyzer=MagicMock(
                analyze=MagicMock(
                    return_value=TechnicalSummary(
                        ma_alignment="混乱",
                        macd_signal="中性",
                        rsi_value=50.0,
                        rsi_status="正常",
                        volume_trend="正常",
                        overall_score=0,
                        summary="中性",
                    )
                )
            ),
            llm_provider=mock_llm,
            prompt_manager=mock_prompt_manager,
            watchlist_manager=wm,
        )

        results = await p.analyze_group("部分失败")

        assert len(results) == 2
        # FAIL01 应有错误但不阻塞 000001
        fail_result = next(r for r in results if r.stock_code == "FAIL01")
        assert len(fail_result.errors) > 0

    @pytest.mark.asyncio()
    async def test_analyze_no_watchlist_manager(
        self, pipeline: StockAnalysisPipeline
    ) -> None:
        """未配置 WatchlistManager 时调用 analyze_group 抛出 RuntimeError。"""
        with pytest.raises(RuntimeError, match="WatchlistManager"):
            await pipeline.analyze_group("任意分组")

    @pytest.mark.asyncio()
    async def test_analyze_stock_llm_unstructured(
        self, pipeline: StockAnalysisPipeline, mock_llm: AsyncMock
    ) -> None:
        """LLM 返回非结构化内容时降级处理。"""
        mock_llm.complete.return_value = LLMResponse(
            success=True,
            content="这只股票技术面偏多，建议持有",
            parsed=None,
            model="gpt-4",
        )

        result = await pipeline.analyze_stock("000001")

        assert result.llm_verdict.signal == "中性"
        assert result.llm_verdict.confidence == 30
        assert "结构化格式" in result.llm_verdict.risk_alerts[0]

    @pytest.mark.asyncio()
    async def test_analysis_date_is_today(
        self, pipeline: StockAnalysisPipeline
    ) -> None:
        """分析日期为当天。"""
        result = await pipeline.analyze_stock("000001")
        assert result.analysis_date == datetime.date.today().isoformat()

    @pytest.mark.asyncio()
    async def test_news_summary_format(
        self, pipeline: StockAnalysisPipeline, mock_news_manager: AsyncMock
    ) -> None:
        """新闻摘要格式（超过5条时显示总数）。"""
        mock_news_manager.get_stock_news.return_value = [
            NewsItem(title=f"新闻{i}", source="测试") for i in range(8)
        ]

        result = await pipeline.analyze_stock("000001")

        assert "共 8 条新闻" in result.news_summary
        assert result.news_count == 8

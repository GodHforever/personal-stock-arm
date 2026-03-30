"""宏观数据追踪模块单元测试。"""

from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.analysis.llm.base import LLMResponse
from src.business.macro.indicators import (
    MACRO_INDICATORS,
    IndicatorDef,
    get_indicator_by_name,
    get_indicators_by_category,
)
from src.business.macro.models import MacroIndicator, MacroRecord
from src.business.macro.tracker import MacroTracker


# ============================================================
# Fixtures
# ============================================================


from contextlib import asynccontextmanager


def _make_db_mock(session: AsyncMock) -> MagicMock:
    """创建带有 asynccontextmanager session 的 DB mock。"""
    db = MagicMock()

    @asynccontextmanager
    async def _mock_session():
        yield session

    db.session = _mock_session
    db._mock_session = session
    return db


@pytest.fixture()
def mock_db() -> MagicMock:
    """模拟 Database 实例。"""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return _make_db_mock(session)


@pytest.fixture()
def mock_llm() -> AsyncMock:
    """模拟 LLM Provider。"""
    llm = AsyncMock()
    llm.complete.return_value = LLMResponse(
        content="宏观分析：CPI 数据显示通胀温和，对 A 股中性偏积极。",
        model="test-model",
        input_tokens=100,
        output_tokens=50,
        success=True,
    )
    return llm


@pytest.fixture()
def tracker(mock_db: AsyncMock, mock_llm: AsyncMock) -> MacroTracker:
    """创建 MacroTracker 实例。"""
    return MacroTracker(db=mock_db, llm=mock_llm)


# ============================================================
# MacroIndicator Pydantic 模型测试
# ============================================================


class TestMacroIndicatorModel:
    """MacroIndicator Pydantic 模型测试。"""

    def test_create_basic_indicator(self) -> None:
        """AC-1: 创建基本指标数据。"""
        indicator = MacroIndicator(
            name="CPI",
            category="价格",
            value=2.1,
            prev_value=1.8,
            unit="%",
            source="akshare",
        )
        assert indicator.name == "CPI"
        assert indicator.category == "价格"
        assert indicator.value == 2.1
        assert indicator.prev_value == 1.8
        assert indicator.unit == "%"
        assert indicator.source == "akshare"

    def test_indicator_with_change(self) -> None:
        """AC-1: 指标包含变化量和变化率。"""
        indicator = MacroIndicator(
            name="M2",
            category="货币",
            value=300.0,
            prev_value=290.0,
            unit="万亿元",
            change=10.0,
            change_pct=3.4483,
        )
        assert indicator.change == 10.0
        assert indicator.change_pct == 3.4483

    def test_indicator_no_update(self) -> None:
        """AC-7: 当日无更新的指标。"""
        indicator = MacroIndicator(
            name="CPI",
            category="价格",
            unit="%",
            no_update=True,
            last_available_date="2026-02-10",
            value=2.1,
        )
        assert indicator.no_update is True
        assert indicator.last_available_date == "2026-02-10"

    def test_indicator_with_error(self) -> None:
        """AC-8: 拉取失败的指标。"""
        indicator = MacroIndicator(
            name="PPI",
            category="价格",
            unit="%",
            error="拉取超时（10s）",
        )
        assert indicator.error == "拉取超时（10s）"
        assert indicator.value is None

    def test_indicator_defaults(self) -> None:
        """AC-1: 默认值正确。"""
        indicator = MacroIndicator(name="test", category="test")
        assert indicator.value is None
        assert indicator.prev_value is None
        assert indicator.unit == ""
        assert indicator.source == ""
        assert indicator.change is None
        assert indicator.change_pct is None
        assert indicator.no_update is False
        assert indicator.error is None


# ============================================================
# MacroRecord ORM 模型测试
# ============================================================


class TestMacroRecordModel:
    """MacroRecord ORM 模型测试。"""

    def test_model_has_required_columns(self) -> None:
        """AC-2: ORM 模型包含必需字段。"""
        columns = {c.name for c in MacroRecord.__table__.columns}
        expected = {
            "id",
            "created_at",
            "updated_at",
            "indicator_name",
            "current_value",
            "previous_value",
            "change",
            "change_pct",
            "unit",
            "source",
            "data_updated_at",
        }
        assert expected.issubset(columns)

    def test_table_name(self) -> None:
        """AC-2: 表名遵循命名规范。"""
        assert MacroRecord.__tablename__ == "macro_record"

    def test_indicator_name_unique(self) -> None:
        """AC-2: indicator_name 列有唯一约束。"""
        col = MacroRecord.__table__.columns["indicator_name"]
        assert col.unique is True


# ============================================================
# 指标定义测试
# ============================================================


class TestIndicatorDefinitions:
    """预定义指标列表测试。"""

    def test_indicators_not_empty(self) -> None:
        """AC-3: 指标列表非空。"""
        assert len(MACRO_INDICATORS) > 0

    def test_indicator_has_required_fields(self) -> None:
        """AC-3: 每个指标定义包含必需字段。"""
        for ind in MACRO_INDICATORS:
            assert ind.name, f"指标缺少名称"
            assert ind.category, f"指标 {ind.name} 缺少类别"
            assert ind.akshare_api, f"指标 {ind.name} 缺少 AkShare API"
            assert ind.frequency in ("daily", "monthly", "event"), (
                f"指标 {ind.name} 频率无效: {ind.frequency}"
            )
            assert ind.unit, f"指标 {ind.name} 缺少单位"
            assert ind.value_column, f"指标 {ind.name} 缺少值列名"

    def test_categories_coverage(self) -> None:
        """AC-3: 指标覆盖核心类别。"""
        categories = {ind.category for ind in MACRO_INDICATORS}
        assert "价格" in categories
        assert "货币" in categories
        assert "利率" in categories
        assert "市场" in categories
        assert "商品" in categories

    def test_get_indicator_by_name(self) -> None:
        """AC-3: 按名称查找指标。"""
        ind = get_indicator_by_name("CPI")
        assert ind is not None
        assert ind.name == "CPI"
        assert ind.category == "价格"

    def test_get_indicator_by_name_not_found(self) -> None:
        """AC-3: 查找不存在的指标。"""
        assert get_indicator_by_name("不存在的指标") is None

    def test_get_indicators_by_category(self) -> None:
        """AC-3: 按类别筛选指标。"""
        prices = get_indicators_by_category("价格")
        assert len(prices) >= 2  # CPI + PPI
        for ind in prices:
            assert ind.category == "价格"

    def test_indicator_names_unique(self) -> None:
        """AC-3: 指标名称不重复。"""
        names = [ind.name for ind in MACRO_INDICATORS]
        assert len(names) == len(set(names))


# ============================================================
# MacroTracker 测试
# ============================================================


class TestMacroTrackerPull:
    """MacroTracker.pull_daily_indicators 测试。"""

    @pytest.mark.asyncio()
    async def test_pull_success_single_indicator(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-4: 成功拉取单个指标。"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {"日期": ["2026-03-01"], "同比增长": [2.1]}
        )

        # 模拟数据库无前值记录
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            return_value=mock_df,
        ):
            results = await tracker.pull_daily_indicators()

        assert len(results) == 1
        assert results[0].name == "CPI"
        assert results[0].value == 2.1
        assert results[0].error is None

    @pytest.mark.asyncio()
    async def test_pull_with_previous_value(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-5: 拉取后与前值比较，计算 change 和 change_pct。"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {"日期": ["2026-03-01"], "同比增长": [2.5]}
        )

        # 模拟数据库有前值记录
        prev_record = MagicMock(spec=MacroRecord)
        prev_record.current_value = 2.0
        prev_record.previous_value = 1.8
        prev_record.data_updated_at = datetime.datetime(2026, 2, 1)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prev_record
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            return_value=mock_df,
        ):
            results = await tracker.pull_daily_indicators()

        assert len(results) == 1
        ind = results[0]
        assert ind.value == 2.5
        assert ind.prev_value == 2.0
        assert ind.change == pytest.approx(0.5)
        assert ind.change_pct == pytest.approx(25.0)

    @pytest.mark.asyncio()
    async def test_pull_no_update_today(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-7: 当日无更新时标注暂无更新。"""
        import pandas as pd

        # 返回空 DataFrame 表示无更新
        mock_df = pd.DataFrame()

        prev_record = MagicMock(spec=MacroRecord)
        prev_record.current_value = 2.0
        prev_record.previous_value = 1.8
        prev_record.data_updated_at = datetime.datetime(2026, 2, 10)

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = prev_record
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            return_value=mock_df,
        ):
            results = await tracker.pull_daily_indicators()

        assert len(results) == 1
        assert results[0].no_update is True
        assert results[0].last_available_date == "2026-02-10"
        assert results[0].value == 2.0

    @pytest.mark.asyncio()
    async def test_pull_single_failure_does_not_block_others(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-8: 单个指标拉取失败不影响其他指标。"""
        import pandas as pd

        good_df = pd.DataFrame({"日期": ["2026-03-01"], "同比增长": [2.1]})

        call_count = 0

        async def mock_to_thread(func, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("网络不可达")
            return good_df

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
            IndicatorDef(
                name="PPI",
                category="价格",
                akshare_api="macro_china_ppi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            side_effect=mock_to_thread,
        ), patch("akshare.macro_china_ppi_monthly", create=True):
            results = await tracker.pull_daily_indicators()

        assert len(results) == 2
        # 第一个失败
        assert results[0].error is not None
        assert "网络不可达" in results[0].error
        # 第二个成功
        assert results[1].error is None
        assert results[1].value == 2.1

    @pytest.mark.asyncio()
    async def test_pull_timeout(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-8: 拉取超时时记录错误。"""
        import asyncio

        async def slow_fetch(*args, **kwargs):
            await asyncio.sleep(100)  # 故意很慢

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker._FETCH_TIMEOUT", 0.01,
        ), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            side_effect=slow_fetch,
        ):
            results = await tracker.pull_daily_indicators()

        assert len(results) == 1
        assert results[0].error is not None
        assert "超时" in results[0].error


class TestMacroTrackerAnalyze:
    """MacroTracker.analyze 测试。"""

    @pytest.mark.asyncio()
    async def test_analyze_success(self, tracker: MacroTracker, mock_llm: AsyncMock) -> None:
        """AC-6: LLM 分析成功返回分析文本。"""
        indicators = [
            MacroIndicator(
                name="CPI",
                category="价格",
                value=2.1,
                prev_value=1.8,
                unit="%",
                change=0.3,
                change_pct=16.67,
            ),
        ]

        result = await tracker.analyze(indicators)

        assert "宏观分析" in result
        mock_llm.complete.assert_called_once()
        # 验证 prompt 包含指标数据
        call_args = mock_llm.complete.call_args
        prompt = call_args[0][0]
        assert "CPI" in prompt
        assert "2.1" in prompt

    @pytest.mark.asyncio()
    async def test_analyze_llm_failure(
        self, tracker: MacroTracker, mock_llm: AsyncMock
    ) -> None:
        """AC-6: LLM 调用失败返回错误提示。"""
        mock_llm.complete.return_value = LLMResponse(
            success=False,
            error="API Key 无效",
        )

        indicators = [
            MacroIndicator(name="CPI", category="价格", value=2.1, unit="%"),
        ]

        result = await tracker.analyze(indicators)
        assert "失败" in result
        assert "API Key" in result

    @pytest.mark.asyncio()
    async def test_analyze_with_mixed_indicators(
        self, tracker: MacroTracker, mock_llm: AsyncMock
    ) -> None:
        """AC-6: 分析包含成功、无更新、失败的混合指标。"""
        indicators = [
            MacroIndicator(
                name="CPI", category="价格", value=2.1, unit="%", change=0.3,
            ),
            MacroIndicator(
                name="PPI", category="价格", unit="%", no_update=True,
                last_available_date="2026-02-10", value=1.5,
            ),
            MacroIndicator(
                name="M1", category="货币", unit="亿元", error="网络超时",
            ),
        ]

        result = await tracker.analyze(indicators)
        assert result  # 有返回值

        # 验证 prompt 格式化包含所有指标
        prompt = mock_llm.complete.call_args[0][0]
        assert "CPI" in prompt
        assert "PPI" in prompt
        assert "暂无更新" in prompt
        assert "拉取失败" in prompt


class TestMacroTrackerRunDaily:
    """MacroTracker.run_daily 测试。"""

    @pytest.mark.asyncio()
    async def test_run_daily_calls_pull_and_analyze(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-4 + AC-6: run_daily 执行拉取 + 分析。"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {"日期": ["2026-03-01"], "同比增长": [2.1]}
        )

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            return_value=mock_df,
        ):
            indicators, analysis = await tracker.run_daily()

        assert len(indicators) == 1
        assert indicators[0].name == "CPI"
        assert "宏观分析" in analysis
        mock_llm.complete.assert_called_once()


class TestMacroTrackerDbUpdate:
    """MacroTracker 数据库更新测试。"""

    @pytest.mark.asyncio()
    async def test_first_record_created(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-5: 首次拉取时创建数据库记录。"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {"日期": ["2026-03-01"], "同比增长": [2.1]}
        )

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            return_value=mock_df,
        ):
            results = await tracker.pull_daily_indicators()

        # 验证 session.add 被调用（新建记录）
        session.add.assert_called()
        added = session.add.call_args[0][0]
        assert isinstance(added, MacroRecord)
        assert added.indicator_name == "CPI"
        assert added.current_value == 2.1
        assert added.previous_value is None

    @pytest.mark.asyncio()
    async def test_existing_record_updated(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """AC-5: 已有记录时更新：当前值变前值，新值写入。"""
        import pandas as pd

        mock_df = pd.DataFrame(
            {"日期": ["2026-03-01"], "同比增长": [2.5]}
        )

        # 模拟已有记录
        existing = MagicMock(spec=MacroRecord)
        existing.current_value = 2.0
        existing.previous_value = 1.8

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=mock_result)
        mock_db = _make_db_mock(session)

        tracker = MacroTracker(db=mock_db, llm=mock_llm)

        with patch("src.business.macro.tracker.MACRO_INDICATORS", [
            IndicatorDef(
                name="CPI",
                category="价格",
                akshare_api="macro_china_cpi_monthly",
                frequency="monthly",
                unit="%",
                value_column="同比增长",
            ),
        ]), patch(
            "src.business.macro.tracker.asyncio.to_thread",
            return_value=mock_df,
        ):
            results = await tracker.pull_daily_indicators()

        # 验证记录被更新
        assert existing.previous_value == 2.0  # 旧 current 变 previous
        assert existing.current_value == 2.5  # 新值
        assert existing.change == pytest.approx(0.5)
        assert existing.change_pct == pytest.approx(25.0)


class TestFormatIndicators:
    """指标格式化测试。"""

    def test_format_success_indicator(self) -> None:
        """格式化成功的指标。"""
        indicators = [
            MacroIndicator(
                name="CPI",
                category="价格",
                value=2.1,
                prev_value=1.8,
                unit="%",
                change=0.3,
                change_pct=16.67,
            ),
        ]
        text = MacroTracker._format_indicators_for_llm(indicators)
        assert "CPI" in text
        assert "2.1%" in text
        assert "+0.3%" in text
        assert "前值 1.8%" in text

    def test_format_no_update_indicator(self) -> None:
        """格式化无更新的指标。"""
        indicators = [
            MacroIndicator(
                name="CPI",
                category="价格",
                unit="%",
                value=2.0,
                no_update=True,
                last_available_date="2026-02-10",
            ),
        ]
        text = MacroTracker._format_indicators_for_llm(indicators)
        assert "暂无更新" in text
        assert "2026-02-10" in text

    def test_format_error_indicator(self) -> None:
        """格式化失败的指标。"""
        indicators = [
            MacroIndicator(
                name="M1",
                category="货币",
                unit="亿元",
                error="网络超时",
            ),
        ]
        text = MacroTracker._format_indicators_for_llm(indicators)
        assert "拉取失败" in text
        assert "网络超时" in text

    def test_format_negative_change(self) -> None:
        """格式化负变化的指标。"""
        indicators = [
            MacroIndicator(
                name="北向资金净流入",
                category="市场",
                value=-50.0,
                prev_value=30.0,
                unit="亿元",
                change=-80.0,
                change_pct=-266.67,
            ),
        ]
        text = MacroTracker._format_indicators_for_llm(indicators)
        assert "-80.0亿元" in text


class TestBuildApiKwargs:
    """AkShare API 参数构建测试。"""

    def test_commodity_wti(self) -> None:
        """商品类 WTI 原油参数。"""
        ind = IndicatorDef(
            name="WTI原油",
            category="商品",
            akshare_api="futures_foreign_commodity_realtime",
            frequency="daily",
            unit="美元/桶",
            value_column="最新价",
        )
        kwargs = MacroTracker._build_api_kwargs(ind)
        assert kwargs["symbol"] == "WTI原油"

    def test_commodity_gold(self) -> None:
        """商品类 COMEX 黄金参数。"""
        ind = IndicatorDef(
            name="COMEX黄金",
            category="商品",
            akshare_api="futures_foreign_commodity_realtime",
            frequency="daily",
            unit="美元/盎司",
            value_column="最新价",
        )
        kwargs = MacroTracker._build_api_kwargs(ind)
        assert kwargs["symbol"] == "COMEX黄金"

    def test_interbank_rate(self) -> None:
        """银行间利率参数。"""
        ind = IndicatorDef(
            name="Shibor-ON",
            category="利率",
            akshare_api="rate_interbank",
            frequency="daily",
            unit="%",
            value_column="Shibor人民币-隔夜",
        )
        kwargs = MacroTracker._build_api_kwargs(ind)
        assert kwargs["market"] == "上海银行间同业拆放利率"

    def test_regular_indicator_no_extra_kwargs(self) -> None:
        """普通指标无额外参数。"""
        ind = IndicatorDef(
            name="CPI",
            category="价格",
            akshare_api="macro_china_cpi_monthly",
            frequency="monthly",
            unit="%",
            value_column="同比增长",
        )
        kwargs = MacroTracker._build_api_kwargs(ind)
        assert kwargs == {}

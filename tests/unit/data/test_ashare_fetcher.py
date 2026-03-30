"""A股数据源适配器单元测试。

测试策略：
- Mock 所有外部数据源调用
- 测试 failover 逻辑（primary fail -> fallback success）
- 测试全部失败时返回 DataUnavailableError
- 测试数据模型校验
- 测试 requires_token 逻辑
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.a_share.base import (
    BaseDataFetcher,
    DataUnavailableError,
    Fundamentals,
    KlineBar,
    StockQuote,
)
from src.data.a_share.manager import DataFetcherManager
from src.network.errors import DataSourceError


# ===================== 数据模型测试 =====================


class TestStockQuote:
    """StockQuote 数据模型测试。"""

    def test_创建完整行情(self) -> None:
        quote = StockQuote(
            code="000001",
            name="平安银行",
            price=10.5,
            change=0.3,
            change_pct=2.94,
            volume=1000000,
            amount=10500000,
            high=10.8,
            low=10.2,
            open=10.3,
            prev_close=10.2,
            timestamp=datetime(2026, 3, 30, 15, 0),
        )
        assert quote.code == "000001"
        assert quote.name == "平安银行"
        assert quote.price == 10.5

    def test_创建最小行情(self) -> None:
        quote = StockQuote(code="000001", price=10.5)
        assert quote.code == "000001"
        assert quote.price == 10.5
        assert quote.name == ""
        assert quote.change == 0.0
        assert quote.timestamp is None


class TestKlineBar:
    """KlineBar 数据模型测试。"""

    def test_创建K线(self) -> None:
        bar = KlineBar(
            date="2026-03-30",
            open=10.0,
            high=10.8,
            low=9.9,
            close=10.5,
            volume=1000000,
            amount=10500000,
        )
        assert bar.date == "2026-03-30"
        assert bar.close == 10.5

    def test_默认成交量为零(self) -> None:
        bar = KlineBar(date="2026-03-30", open=10.0, high=10.8, low=9.9, close=10.5)
        assert bar.volume == 0.0
        assert bar.amount == 0.0


class TestFundamentals:
    """Fundamentals 数据模型测试。"""

    def test_创建完整基本面(self) -> None:
        f = Fundamentals(
            code="000001",
            name="平安银行",
            pe_ttm=8.5,
            pb=0.9,
            market_cap=200000000000,
        )
        assert f.code == "000001"
        assert f.pe_ttm == 8.5

    def test_可选字段默认为None(self) -> None:
        f = Fundamentals(code="000001")
        assert f.pe_ttm is None
        assert f.pb is None
        assert f.market_cap is None
        assert f.revenue is None


class TestDataUnavailableError:
    """DataUnavailableError 异常测试。"""

    def test_异常包含错误列表(self) -> None:
        errors = [
            {"source": "efinance", "error_msg": "超时"},
            {"source": "akshare", "error_msg": "连接失败"},
        ]
        exc = DataUnavailableError("全部失败", errors=errors)
        assert "全部失败" in str(exc)
        assert len(exc.errors) == 2

    def test_空错误列表(self) -> None:
        exc = DataUnavailableError("无可用源")
        assert exc.errors == []


# ===================== Mock Fetcher 工具 =====================


class MockFetcher(BaseDataFetcher):
    """用于测试的 Mock 数据源。"""

    def __init__(
        self,
        name: str = "mock",
        prio: int = 0,
        needs_token: bool = False,
        available: bool = True,
    ) -> None:
        self._name = name
        self._prio = prio
        self._needs_token = needs_token
        self._available = available
        self.quote_result: StockQuote | None = None
        self.kline_result: list[KlineBar] | None = None
        self.fundamentals_result: Fundamentals | None = None
        self.should_fail: bool = False
        self.fail_error: Exception | None = None

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._prio

    @property
    def requires_token(self) -> bool:
        return self._needs_token

    async def is_available(self) -> bool:
        return self._available

    async def get_realtime_quote(self, code: str) -> StockQuote:
        if self.should_fail:
            raise self.fail_error or DataSourceError(
                source=self._name,
                step="获取行情",
                url="",
                error_type="MockError",
                error_msg="模拟失败",
                suggestion="测试用",
            )
        if self.quote_result:
            return self.quote_result
        return StockQuote(code=code, name=f"{self._name}_stock", price=10.0)

    async def get_kline(self, code: str, period: str, count: int) -> list[KlineBar]:
        if self.should_fail:
            raise self.fail_error or DataSourceError(
                source=self._name,
                step="获取K线",
                url="",
                error_type="MockError",
                error_msg="模拟失败",
                suggestion="测试用",
            )
        if self.kline_result is not None:
            return self.kline_result
        return [
            KlineBar(date="2026-03-30", open=10.0, high=10.5, low=9.8, close=10.2)
        ]

    async def get_fundamentals(self, code: str) -> Fundamentals:
        if self.should_fail:
            raise self.fail_error or DataSourceError(
                source=self._name,
                step="获取基本面",
                url="",
                error_type="MockError",
                error_msg="模拟失败",
                suggestion="测试用",
            )
        if self.fundamentals_result:
            return self.fundamentals_result
        return Fundamentals(code=code, name=f"{self._name}_stock")


# ===================== DataFetcherManager 测试 =====================


class TestDataFetcherManager:
    """DataFetcherManager failover 编排测试。"""

    def _make_manager(self, *fetchers: BaseDataFetcher) -> DataFetcherManager:
        mgr = DataFetcherManager()
        for f in fetchers:
            mgr.register(f)
        return mgr

    @pytest.mark.asyncio
    async def test_单源成功(self) -> None:
        fetcher = MockFetcher(name="primary", prio=0)
        mgr = self._make_manager(fetcher)
        quote = await mgr.get_realtime_quote("000001")
        assert quote.code == "000001"
        assert quote.name == "primary_stock"
        assert mgr.get_stats()["primary"]["success"] == 1

    @pytest.mark.asyncio
    async def test_primary失败_fallback成功(self) -> None:
        primary = MockFetcher(name="primary", prio=0)
        primary.should_fail = True
        fallback = MockFetcher(name="fallback", prio=1)
        mgr = self._make_manager(primary, fallback)

        quote = await mgr.get_realtime_quote("000001")
        assert quote.name == "fallback_stock"
        assert mgr.get_stats()["primary"]["failure"] == 1
        assert mgr.get_stats()["fallback"]["success"] == 1

    @pytest.mark.asyncio
    async def test_全部失败_抛出DataUnavailableError(self) -> None:
        f1 = MockFetcher(name="source_a", prio=0)
        f1.should_fail = True
        f2 = MockFetcher(name="source_b", prio=1)
        f2.should_fail = True
        mgr = self._make_manager(f1, f2)

        with pytest.raises(DataUnavailableError) as exc_info:
            await mgr.get_realtime_quote("000001")

        assert len(exc_info.value.errors) == 2
        assert mgr.get_stats()["source_a"]["failure"] == 1
        assert mgr.get_stats()["source_b"]["failure"] == 1

    @pytest.mark.asyncio
    async def test_无可用源_抛出DataUnavailableError(self) -> None:
        f1 = MockFetcher(name="unavailable", prio=0, available=False)
        mgr = self._make_manager(f1)

        with pytest.raises(DataUnavailableError) as exc_info:
            await mgr.get_realtime_quote("000001")
        assert "没有可用的数据源" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_优先级排序(self) -> None:
        low = MockFetcher(name="low_prio", prio=3)
        high = MockFetcher(name="high_prio", prio=0)
        mgr = self._make_manager(low, high)

        quote = await mgr.get_realtime_quote("000001")
        # 应该使用高优先级源
        assert quote.name == "high_prio_stock"
        assert mgr.get_stats()["high_prio"]["success"] == 1
        assert mgr.get_stats()["low_prio"]["success"] == 0

    @pytest.mark.asyncio
    async def test_需要token的源不可用时跳过(self) -> None:
        token_source = MockFetcher(name="needs_token", prio=0, needs_token=True, available=False)
        free_source = MockFetcher(name="free", prio=1)
        mgr = self._make_manager(token_source, free_source)

        quote = await mgr.get_realtime_quote("000001")
        assert quote.name == "free_stock"

    @pytest.mark.asyncio
    async def test_get_kline_failover(self) -> None:
        primary = MockFetcher(name="primary", prio=0)
        primary.should_fail = True
        fallback = MockFetcher(name="fallback", prio=1)
        mgr = self._make_manager(primary, fallback)

        bars = await mgr.get_kline("000001", "daily", 10)
        assert len(bars) == 1
        assert bars[0].close == 10.2

    @pytest.mark.asyncio
    async def test_get_fundamentals_failover(self) -> None:
        primary = MockFetcher(name="primary", prio=0)
        primary.should_fail = True
        fallback = MockFetcher(name="fallback", prio=1)
        mgr = self._make_manager(primary, fallback)

        fund = await mgr.get_fundamentals("000001")
        assert fund.code == "000001"

    @pytest.mark.asyncio
    async def test_未预期异常也触发failover(self) -> None:
        primary = MockFetcher(name="primary", prio=0)
        primary.should_fail = True
        primary.fail_error = RuntimeError("未预期的错误")
        fallback = MockFetcher(name="fallback", prio=1)
        mgr = self._make_manager(primary, fallback)

        quote = await mgr.get_realtime_quote("000001")
        assert quote.name == "fallback_stock"
        assert mgr.get_stats()["primary"]["failure"] == 1

    def test_注册后按优先级排序(self) -> None:
        mgr = DataFetcherManager()
        mgr.register(MockFetcher(name="c", prio=2))
        mgr.register(MockFetcher(name="a", prio=0))
        mgr.register(MockFetcher(name="b", prio=1))
        names = [f.source_name for f in mgr._fetchers]
        assert names == ["a", "b", "c"]

    def test_fetcher_count(self) -> None:
        mgr = DataFetcherManager()
        assert mgr.fetcher_count == 0
        mgr.register(MockFetcher(name="a"))
        assert mgr.fetcher_count == 1

    def test_get_stats(self) -> None:
        mgr = DataFetcherManager()
        mgr.register(MockFetcher(name="src1"))
        stats = mgr.get_stats()
        assert stats["src1"] == {"success": 0, "failure": 0}


# ===================== 具体 Fetcher 基础测试 =====================


class TestEfinanceFetcher:
    """efinance 适配器基础测试（使用 mock）。"""

    @pytest.mark.asyncio
    async def test_属性(self) -> None:
        from src.data.a_share.efinance_fetcher import EfinanceFetcher

        f = EfinanceFetcher()
        assert f.source_name == "efinance"
        assert f.priority == 0
        assert f.requires_token is False

    @pytest.mark.asyncio
    async def test_库未安装时不可用(self) -> None:
        from src.data.a_share.efinance_fetcher import EfinanceFetcher

        f = EfinanceFetcher()
        with patch.dict("sys.modules", {"efinance": None}):
            result = await f.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_fundamentals_不支持(self) -> None:
        from src.data.a_share.efinance_fetcher import EfinanceFetcher

        f = EfinanceFetcher()
        with pytest.raises(DataSourceError) as exc_info:
            await f.get_fundamentals("000001")
        assert "不支持" in exc_info.value.error_msg


class TestAkshareFetcher:
    """AkShare 适配器基础测试。"""

    @pytest.mark.asyncio
    async def test_属性(self) -> None:
        from src.data.a_share.akshare_fetcher import AkshareFetcher

        f = AkshareFetcher()
        assert f.source_name == "akshare"
        assert f.priority == 1
        assert f.requires_token is False

    @pytest.mark.asyncio
    async def test_库未安装时不可用(self) -> None:
        from src.data.a_share.akshare_fetcher import AkshareFetcher

        f = AkshareFetcher()
        with patch.dict("sys.modules", {"akshare": None}):
            result = await f.is_available()
            assert result is False


class TestTushareFetcher:
    """Tushare 适配器基础测试。"""

    @pytest.mark.asyncio
    async def test_属性(self) -> None:
        from src.data.a_share.tushare_fetcher import TushareFetcher

        f = TushareFetcher()
        assert f.source_name == "tushare"
        assert f.priority == 0
        assert f.requires_token is True

    @pytest.mark.asyncio
    async def test_无token时不可用(self) -> None:
        from src.data.a_share.tushare_fetcher import TushareFetcher

        f = TushareFetcher()
        with patch(
            "src.data.a_share.tushare_fetcher._get_tushare_token", return_value=""
        ):
            # 即使 tushare 库可导入，无 token 时也不可用
            with patch.dict("sys.modules", {"tushare": MagicMock()}):
                result = await f.is_available()
                assert result is False


class TestBaostockFetcher:
    """Baostock 适配器基础测试。"""

    @pytest.mark.asyncio
    async def test_属性(self) -> None:
        from src.data.a_share.baostock_fetcher import BaostockFetcher

        f = BaostockFetcher()
        assert f.source_name == "baostock"
        assert f.priority == 3
        assert f.requires_token is False

    @pytest.mark.asyncio
    async def test_实时行情不支持(self) -> None:
        from src.data.a_share.baostock_fetcher import BaostockFetcher

        f = BaostockFetcher()
        with pytest.raises(DataSourceError) as exc_info:
            await f.get_realtime_quote("000001")
        assert "不支持" in exc_info.value.error_msg

    @pytest.mark.asyncio
    async def test_库未安装时不可用(self) -> None:
        from src.data.a_share.baostock_fetcher import BaostockFetcher

        f = BaostockFetcher()
        with patch.dict("sys.modules", {"baostock": None}):
            result = await f.is_available()
            assert result is False


# ===================== 代码转换工具函数测试 =====================


class TestCodeConversion:
    """股票代码转换测试。"""

    def test_tushare代码转换(self) -> None:
        from src.data.a_share.tushare_fetcher import _to_ts_code

        assert _to_ts_code("000001") == "000001.SZ"
        assert _to_ts_code("600000") == "600000.SH"
        assert _to_ts_code("000001.SZ") == "000001.SZ"

    def test_baostock代码转换(self) -> None:
        from src.data.a_share.baostock_fetcher import _to_bs_code

        assert _to_bs_code("000001") == "sz.000001"
        assert _to_bs_code("600000") == "sh.600000"
        assert _to_bs_code("sh.600000") == "sh.600000"

"""国际市场数据源适配器单元测试。

测试策略：
- Mock 所有外部数据源调用（Longbridge SDK / yfinance）
- 测试数据模型校验
- 测试 symbol 解析
- 测试 failover 逻辑（primary fail -> fallback success）
- 测试全部失败时返回 DataUnavailableError
- 测试 rate limit 控制
- 测试市场过滤逻辑
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.a_share.base import DataUnavailableError
from src.data.international.base import (
    MAJOR_INDICES,
    BaseIntlFetcher,
    IntlKlineBar,
    IntlQuote,
    parse_symbol,
)
from src.data.international.manager import IntlDataManager
from src.network.errors import DataSourceError


# ===================== 数据模型测试 =====================


class TestIntlQuote:
    """IntlQuote 数据模型测试。"""

    def test_创建完整行情(self) -> None:
        quote = IntlQuote(
            symbol="AAPL.US",
            name="Apple Inc.",
            market="US",
            currency="USD",
            price=175.5,
            change=2.3,
            change_pct=1.33,
            volume=50000000,
            turnover=8775000000,
            high=176.0,
            low=173.0,
            open=174.0,
            prev_close=173.2,
            timestamp=datetime(2026, 3, 30, 16, 0),
        )
        assert quote.symbol == "AAPL.US"
        assert quote.name == "Apple Inc."
        assert quote.market == "US"
        assert quote.currency == "USD"
        assert quote.price == 175.5

    def test_创建最小行情(self) -> None:
        quote = IntlQuote(symbol="700.HK", price=350.0)
        assert quote.symbol == "700.HK"
        assert quote.price == 350.0
        assert quote.name == ""
        assert quote.market == ""
        assert quote.change == 0.0
        assert quote.timestamp is None


class TestIntlKlineBar:
    """IntlKlineBar 数据模型测试。"""

    def test_创建完整K线(self) -> None:
        bar = IntlKlineBar(
            symbol="AAPL.US",
            date="2026-03-30",
            open=174.0,
            high=176.0,
            low=173.0,
            close=175.5,
            volume=50000000,
            turnover=8775000000,
        )
        assert bar.symbol == "AAPL.US"
        assert bar.date == "2026-03-30"
        assert bar.close == 175.5

    def test_创建最小K线(self) -> None:
        bar = IntlKlineBar(
            symbol="700.HK",
            date="2026-03-30",
            open=350.0,
            high=355.0,
            low=348.0,
            close=352.0,
        )
        assert bar.volume == 0.0
        assert bar.turnover == 0.0


# ===================== Symbol 解析测试 =====================


class TestParseSymbol:
    """parse_symbol 函数测试。"""

    def test_解析美股(self) -> None:
        code, market = parse_symbol("AAPL.US")
        assert code == "AAPL"
        assert market == "US"

    def test_解析港股(self) -> None:
        code, market = parse_symbol("700.HK")
        assert code == "700"
        assert market == "HK"

    def test_解析新加坡(self) -> None:
        code, market = parse_symbol("D05.SG")
        assert code == "D05"
        assert market == "SG"

    def test_解析指数(self) -> None:
        code, market = parse_symbol(".DJI.US")
        assert code == ".DJI"
        assert market == "US"

    def test_小写市场自动转大写(self) -> None:
        code, market = parse_symbol("AAPL.us")
        assert market == "US"

    def test_无效格式_无点号(self) -> None:
        with pytest.raises(ValueError, match="无效的 symbol 格式"):
            parse_symbol("AAPL")

    def test_无效格式_空代码(self) -> None:
        with pytest.raises(ValueError, match="无效的 symbol 格式"):
            parse_symbol(".US")

    def test_不支持的市场(self) -> None:
        with pytest.raises(ValueError, match="不支持的市场"):
            parse_symbol("000001.SH")


# ===================== Mock Fetcher =====================


class MockIntlFetcher(BaseIntlFetcher):
    """测试用 Mock 数据源。"""

    def __init__(
        self,
        name: str,
        priority: int,
        markets: set[str],
        available: bool = True,
    ) -> None:
        self._name = name
        self._priority = priority
        self._markets = markets
        self._available = available
        self._get_quote = AsyncMock()
        self._get_kline = AsyncMock()
        self._get_market_indices = AsyncMock()

    async def get_quote(self, symbol: str) -> IntlQuote:
        return await self._get_quote(symbol=symbol)

    async def get_kline(
        self, symbol: str, period: str = "daily", count: int = 100
    ) -> list[IntlKlineBar]:
        return await self._get_kline(symbol=symbol, period=period, count=count)

    async def get_market_indices(self) -> list[IntlQuote]:
        return await self._get_market_indices()

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def supported_markets(self) -> set[str]:
        return self._markets

    async def is_available(self) -> bool:
        return self._available


# ===================== IntlDataManager 测试 =====================


class TestIntlDataManager:
    """IntlDataManager 管理器测试。"""

    def test_注册排序(self) -> None:
        manager = IntlDataManager()
        low = MockIntlFetcher("low", 1, {"US"})
        high = MockIntlFetcher("high", 0, {"US", "HK"})
        manager.register(low)
        manager.register(high)
        assert manager.fetcher_count == 2
        assert manager._fetchers[0].source_name == "high"
        assert manager._fetchers[1].source_name == "low"

    @pytest.mark.asyncio
    async def test_获取行情_成功(self) -> None:
        manager = IntlDataManager()
        fetcher = MockIntlFetcher("test", 0, {"US"})
        expected = IntlQuote(symbol="AAPL.US", price=175.0, market="US")
        fetcher._get_quote.return_value = expected
        manager.register(fetcher)

        result = await manager.get_quote("AAPL.US")
        assert result.symbol == "AAPL.US"
        assert result.price == 175.0
        fetcher._get_quote.assert_called_once_with(symbol="AAPL.US")

    @pytest.mark.asyncio
    async def test_获取行情_failover(self) -> None:
        manager = IntlDataManager()
        primary = MockIntlFetcher("primary", 0, {"US"})
        fallback = MockIntlFetcher("fallback", 1, {"US"})
        expected = IntlQuote(symbol="AAPL.US", price=175.0, market="US")

        primary._get_quote.side_effect = DataSourceError(
            step="获取行情",
            source="primary",
            url="AAPL.US",
            error_type="连接失败",
            error_msg="timeout",
            suggestion="重试",
        )
        fallback._get_quote.return_value = expected

        manager.register(primary)
        manager.register(fallback)

        result = await manager.get_quote("AAPL.US")
        assert result.symbol == "AAPL.US"
        assert manager.get_stats()["primary"]["failure"] == 1
        assert manager.get_stats()["fallback"]["success"] == 1

    @pytest.mark.asyncio
    async def test_全部失败_抛出异常(self) -> None:
        manager = IntlDataManager()
        fetcher = MockIntlFetcher("test", 0, {"US"})
        fetcher._get_quote.side_effect = DataSourceError(
            step="获取行情",
            source="test",
            url="AAPL.US",
            error_type="连接失败",
            error_msg="timeout",
            suggestion="重试",
        )
        manager.register(fetcher)

        with pytest.raises(DataUnavailableError, match="所有数据源均无法完成"):
            await manager.get_quote("AAPL.US")

    @pytest.mark.asyncio
    async def test_无可用数据源_抛出异常(self) -> None:
        manager = IntlDataManager()
        with pytest.raises(DataUnavailableError, match="没有可用的国际市场数据源"):
            await manager.get_quote("AAPL.US")

    @pytest.mark.asyncio
    async def test_市场过滤_港股不走yfinance(self) -> None:
        manager = IntlDataManager()
        us_only = MockIntlFetcher("us_only", 1, {"US"})
        all_markets = MockIntlFetcher("all_markets", 0, {"US", "HK", "SG"})
        expected = IntlQuote(symbol="700.HK", price=350.0, market="HK")
        all_markets._get_quote.return_value = expected
        us_only._get_quote.return_value = IntlQuote(
            symbol="700.HK", price=999.0
        )

        manager.register(us_only)
        manager.register(all_markets)

        result = await manager.get_quote("700.HK")
        assert result.price == 350.0
        # us_only 不应被调用（不支持 HK）
        us_only._get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_不可用数据源被跳过(self) -> None:
        manager = IntlDataManager()
        unavailable = MockIntlFetcher("unavailable", 0, {"US"}, available=False)
        available = MockIntlFetcher("available", 1, {"US"})
        expected = IntlQuote(symbol="AAPL.US", price=175.0, market="US")
        available._get_quote.return_value = expected

        manager.register(unavailable)
        manager.register(available)

        result = await manager.get_quote("AAPL.US")
        assert result.price == 175.0
        unavailable._get_quote.assert_not_called()

    @pytest.mark.asyncio
    async def test_获取K线_成功(self) -> None:
        manager = IntlDataManager()
        fetcher = MockIntlFetcher("test", 0, {"US"})
        expected = [
            IntlKlineBar(
                symbol="AAPL.US",
                date="2026-03-30",
                open=174.0,
                high=176.0,
                low=173.0,
                close=175.5,
            )
        ]
        fetcher._get_kline.return_value = expected
        manager.register(fetcher)

        result = await manager.get_kline("AAPL.US", "daily", 100)
        assert len(result) == 1
        assert result[0].close == 175.5
        fetcher._get_kline.assert_called_once_with(
            symbol="AAPL.US", period="daily", count=100
        )

    @pytest.mark.asyncio
    async def test_获取指数_成功(self) -> None:
        manager = IntlDataManager()
        fetcher = MockIntlFetcher("test", 0, {"US", "HK"})
        expected = [
            IntlQuote(symbol=".DJI.US", price=40000.0, market="US"),
            IntlQuote(symbol=".HSI.HK", price=20000.0, market="HK"),
        ]
        fetcher._get_market_indices.return_value = expected
        manager.register(fetcher)

        result = await manager.get_market_indices()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_未预期异常也触发failover(self) -> None:
        manager = IntlDataManager()
        primary = MockIntlFetcher("primary", 0, {"US"})
        fallback = MockIntlFetcher("fallback", 1, {"US"})
        expected = IntlQuote(symbol="AAPL.US", price=175.0, market="US")

        primary._get_quote.side_effect = RuntimeError("意外错误")
        fallback._get_quote.return_value = expected

        manager.register(primary)
        manager.register(fallback)

        result = await manager.get_quote("AAPL.US")
        assert result.price == 175.0
        assert manager.get_stats()["primary"]["failure"] == 1

    def test_获取统计(self) -> None:
        manager = IntlDataManager()
        fetcher = MockIntlFetcher("test", 0, {"US"})
        manager.register(fetcher)
        stats = manager.get_stats()
        assert stats["test"] == {"success": 0, "failure": 0}

    @pytest.mark.asyncio
    async def test_无效symbol格式(self) -> None:
        manager = IntlDataManager()
        fetcher = MockIntlFetcher("test", 0, {"US"})
        manager.register(fetcher)
        with pytest.raises(ValueError, match="无效的 symbol 格式"):
            await manager.get_quote("INVALID")


# ===================== Longbridge 适配器测试 =====================


class TestLongbridgeFetcher:
    """Longbridge 适配器测试（全部 mock SDK 调用）。"""

    @pytest.fixture
    def _mock_longbridge_available(self) -> None:
        """Patch Longbridge SDK 为可用状态。"""
        import src.data.international.longbridge_fetcher as mod

        mod._HAS_LONGBRIDGE = True

    @pytest.fixture
    def _mock_longbridge_unavailable(self) -> None:
        """Patch Longbridge SDK 为不可用状态。"""
        import src.data.international.longbridge_fetcher as mod

        mod._HAS_LONGBRIDGE = False

    def test_属性(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        assert fetcher.source_name == "longbridge"
        assert fetcher.priority == 0
        assert fetcher.supported_markets == {"US", "HK", "SG"}

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_unavailable")
    async def test_SDK不可用时is_available返回False(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        assert await fetcher.is_available() is False

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_无client_id时is_available返回False(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        with patch(
            "src.data.international.longbridge_fetcher._get_longbridge_client_id",
            return_value="",
        ):
            fetcher = LongbridgeFetcher()
            assert await fetcher.is_available() is False

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_有client_id时is_available返回True(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        with patch(
            "src.data.international.longbridge_fetcher._get_longbridge_client_id",
            return_value="test-client-id",
        ):
            fetcher = LongbridgeFetcher()
            assert await fetcher.is_available() is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_获取行情_成功(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()

        mock_quote = SimpleNamespace(
            name_en="Apple Inc.",
            currency="USD",
            last_done=175.5,
            prev_close_price=173.2,
            volume=50000000,
            turnover=8775000000,
            high=176.0,
            low=173.0,
            open=174.0,
        )

        mock_ctx = AsyncMock()
        mock_ctx.quote = AsyncMock(return_value=[mock_quote])
        fetcher._ctx = mock_ctx
        fetcher._initialized = True

        result = await fetcher.get_quote("AAPL.US")
        assert result.symbol == "AAPL.US"
        assert result.price == 175.5
        assert result.market == "US"
        assert result.name == "Apple Inc."
        assert result.change == pytest.approx(2.3, abs=0.01)
        assert result.change_pct == pytest.approx(1.33, abs=0.01)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_获取行情_空数据(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        mock_ctx = AsyncMock()
        mock_ctx.quote = AsyncMock(return_value=[])
        fetcher._ctx = mock_ctx
        fetcher._initialized = True

        with pytest.raises(DataSourceError, match="数据为空"):
            await fetcher.get_quote("AAPL.US")

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_获取K线_成功(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher
        import src.data.international.longbridge_fetcher as lb_mod

        fetcher = LongbridgeFetcher()

        mock_candle = SimpleNamespace(
            timestamp=datetime(2026, 3, 30),
            open=174.0,
            high=176.0,
            low=173.0,
            close=175.5,
            volume=50000000,
            turnover=8775000000,
        )

        mock_ctx = AsyncMock()
        mock_ctx.candlesticks = AsyncMock(return_value=[mock_candle])
        fetcher._ctx = mock_ctx
        fetcher._initialized = True

        # 当 longbridge 未安装时 _PERIOD_MAP 为空，需要 mock
        sentinel_period = object()
        original_map = lb_mod._PERIOD_MAP
        lb_mod._PERIOD_MAP = {"daily": sentinel_period}
        try:
            result = await fetcher.get_kline("AAPL.US", "daily", 100)
        finally:
            lb_mod._PERIOD_MAP = original_map
        assert len(result) == 1
        assert result[0].close == 175.5
        assert result[0].date == "2026-03-30"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_获取K线_不支持的周期(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        fetcher._ctx = AsyncMock()
        fetcher._initialized = True

        with pytest.raises(DataSourceError, match="不支持的K线周期"):
            await fetcher.get_kline("AAPL.US", "invalid_period", 100)

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_获取指数_成功(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()

        mock_quotes = []
        for _ in MAJOR_INDICES:
            mock_quotes.append(
                SimpleNamespace(
                    name_en="Index",
                    currency="",
                    last_done=40000.0,
                    prev_close_price=39500.0,
                    volume=100000,
                    turnover=0,
                    high=40100.0,
                    low=39800.0,
                    open=39900.0,
                )
            )

        mock_ctx = AsyncMock()
        mock_ctx.quote = AsyncMock(return_value=mock_quotes)
        fetcher._ctx = mock_ctx
        fetcher._initialized = True

        result = await fetcher.get_market_indices()
        assert len(result) == len(MAJOR_INDICES)
        assert result[0].symbol == MAJOR_INDICES[0]

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_无效symbol格式(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        fetcher._ctx = AsyncMock()
        fetcher._initialized = True

        with pytest.raises(ValueError, match="无效的 symbol 格式"):
            await fetcher.get_quote("INVALID")

    def test_rate_limit_初始化(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        assert fetcher._max_calls_per_second == 10
        assert fetcher._call_timestamps == []

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_longbridge_available")
    async def test_初始化_无client_id(self) -> None:
        from src.data.international.longbridge_fetcher import LongbridgeFetcher

        fetcher = LongbridgeFetcher()
        with patch(
            "src.data.international.longbridge_fetcher._get_longbridge_client_id",
            return_value="",
        ):
            with pytest.raises(DataSourceError, match="配置缺失"):
                await fetcher._ensure_initialized()


# ===================== yfinance 适配器测试 =====================


class TestYFinanceFetcher:
    """yfinance 适配器测试（全部 mock yfinance 调用）。"""

    @pytest.fixture
    def _mock_yfinance_available(self) -> None:
        """Patch yfinance 为可用状态。"""
        import src.data.international.yfinance_fetcher as mod

        mod._HAS_YFINANCE = True

    @pytest.fixture
    def _mock_yfinance_unavailable(self) -> None:
        """Patch yfinance 为不可用状态。"""
        import src.data.international.yfinance_fetcher as mod

        mod._HAS_YFINANCE = False

    def test_属性(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()
        assert fetcher.source_name == "yfinance"
        assert fetcher.priority == 1
        assert fetcher.supported_markets == {"US"}

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_yfinance_unavailable")
    async def test_SDK不可用时is_available返回False(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()
        assert await fetcher.is_available() is False

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_mock_yfinance_available")
    async def test_SDK可用时is_available返回True(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()
        assert await fetcher.is_available() is True

    @pytest.mark.asyncio
    async def test_非US市场_获取行情_报错(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()
        with pytest.raises(DataSourceError, match="仅支持 US 市场"):
            await fetcher.get_quote("700.HK")

    @pytest.mark.asyncio
    async def test_非US市场_获取K线_报错(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()
        with pytest.raises(DataSourceError, match="仅支持 US 市场"):
            await fetcher.get_kline("700.HK")

    @pytest.mark.asyncio
    async def test_获取行情_成功(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()

        mock_fast_info = SimpleNamespace(
            last_price=175.5,
            previous_close=173.2,
            last_volume=50000000,
            day_high=176.0,
            day_low=173.0,
            open=174.0,
        )
        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_fast_info

        with patch(
            "src.data.international.yfinance_fetcher.yf.Ticker",
            return_value=mock_ticker,
        ):
            result = await fetcher.get_quote("AAPL.US")
            assert result.symbol == "AAPL.US"
            assert result.price == 175.5
            assert result.market == "US"
            assert result.currency == "USD"
            assert result.change == pytest.approx(2.3, abs=0.01)

    @pytest.mark.asyncio
    async def test_获取K线_成功(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()

        # 构建 mock DataFrame
        import pandas as pd

        mock_df = pd.DataFrame(
            {
                "Open": [174.0, 175.0],
                "High": [176.0, 177.0],
                "Low": [173.0, 174.0],
                "Close": [175.5, 176.5],
                "Volume": [50000000, 45000000],
            },
            index=pd.to_datetime(["2026-03-29", "2026-03-30"]),
        )
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df

        with patch(
            "src.data.international.yfinance_fetcher.yf.Ticker",
            return_value=mock_ticker,
        ):
            result = await fetcher.get_kline("AAPL.US", "daily", 100)
            assert len(result) == 2
            assert result[0].close == 175.5
            assert result[1].date == "2026-03-30"

    @pytest.mark.asyncio
    async def test_获取K线_空数据(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()

        import pandas as pd

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        with patch(
            "src.data.international.yfinance_fetcher.yf.Ticker",
            return_value=mock_ticker,
        ):
            result = await fetcher.get_kline("AAPL.US", "daily", 100)
            assert result == []

    @pytest.mark.asyncio
    async def test_获取K线_不支持的周期(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()
        with pytest.raises(DataSourceError, match="不支持的K线周期"):
            await fetcher.get_kline("AAPL.US", "invalid_period", 100)

    @pytest.mark.asyncio
    async def test_获取指数_成功(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()

        mock_fast_info = SimpleNamespace(
            last_price=40000.0,
            previous_close=39500.0,
        )
        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_fast_info

        with patch(
            "src.data.international.yfinance_fetcher.yf.Ticker",
            return_value=mock_ticker,
        ):
            result = await fetcher.get_market_indices()
            assert len(result) >= 1
            # yfinance 支持 4 个指数
            assert any(q.symbol == ".DJI.US" for q in result)

    @pytest.mark.asyncio
    async def test_获取行情_异常处理(self) -> None:
        from src.data.international.yfinance_fetcher import YFinanceFetcher

        fetcher = YFinanceFetcher()

        with patch(
            "src.data.international.yfinance_fetcher.yf.Ticker",
            side_effect=Exception("网络错误"),
        ):
            with pytest.raises(DataSourceError, match="网络错误"):
                await fetcher.get_quote("AAPL.US")

"""技术分析引擎单元测试。"""

import math

import pytest

from src.analysis.technical.analyzer import TechnicalAnalyzer
from src.analysis.technical.indicators import (
    calc_ema,
    calc_ma,
    calc_macd,
    calc_rsi,
    calc_volume_ratio,
)
from src.analysis.technical.models import TechnicalSummary
from src.data.a_share.base import KlineBar


# ============================================================
# 辅助函数
# ============================================================


def _make_klines(
    closes: list[float],
    volumes: list[float] | None = None,
) -> list[KlineBar]:
    """根据收盘价列表生成KlineBar列表。"""
    if volumes is None:
        volumes = [1000.0] * len(closes)
    return [
        KlineBar(
            date=f"2024-01-{i + 1:02d}",
            open=c,
            high=c * 1.01,
            low=c * 0.99,
            close=c,
            volume=volumes[i],
        )
        for i, c in enumerate(closes)
    ]


def _is_nan(v: float) -> bool:
    return math.isnan(v)


# ============================================================
# calc_ma 测试
# ============================================================


class TestCalcMA:
    """MA计算测试。"""

    def test_basic_ma(self) -> None:
        """基本MA计算。"""
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calc_ma(prices, 3)
        assert len(result) == 5
        assert _is_nan(result[0])
        assert _is_nan(result[1])
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_ma_period_equals_length(self) -> None:
        """周期等于数据长度。"""
        prices = [10.0, 20.0, 30.0]
        result = calc_ma(prices, 3)
        assert len(result) == 3
        assert result[2] == pytest.approx(20.0)

    def test_ma_data_shorter_than_period(self) -> None:
        """数据长度不足周期。"""
        prices = [1.0, 2.0]
        result = calc_ma(prices, 5)
        assert len(result) == 2
        assert all(_is_nan(v) for v in result)

    def test_ma_period_1(self) -> None:
        """周期为1时等于原始价格。"""
        prices = [5.0, 10.0, 15.0]
        result = calc_ma(prices, 1)
        assert result == pytest.approx(prices)


# ============================================================
# calc_ema 测试
# ============================================================


class TestCalcEMA:
    """EMA计算测试。"""

    def test_basic_ema(self) -> None:
        """基本EMA计算。"""
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = calc_ema(prices, 3)
        assert len(result) == 5
        assert _is_nan(result[0])
        assert _is_nan(result[1])
        # 首个EMA = SMA(10, 11, 12) = 11
        assert result[2] == pytest.approx(11.0)
        # EMA = (13 - 11) * 0.5 + 11 = 12.0
        assert result[3] == pytest.approx(12.0)

    def test_ema_data_shorter_than_period(self) -> None:
        """数据长度不足。"""
        result = calc_ema([1.0], 5)
        assert len(result) == 1
        assert _is_nan(result[0])


# ============================================================
# calc_macd 测试
# ============================================================


class TestCalcMACD:
    """MACD计算测试。"""

    def test_macd_insufficient_data(self) -> None:
        """数据不足时返回NaN。"""
        prices = list(range(1, 10))  # 9个数据，少于slow=26
        macd_line, signal_line, histogram = calc_macd(prices)
        assert len(macd_line) == len(prices)
        assert all(_is_nan(v) for v in macd_line)

    def test_macd_sufficient_data(self) -> None:
        """足够数据时MACD有有效值。"""
        # 生成60个递增价格
        prices = [100.0 + i * 0.5 for i in range(60)]
        macd_line, signal_line, histogram = calc_macd(prices)
        assert len(macd_line) == 60
        assert len(signal_line) == 60
        assert len(histogram) == 60
        # 最后一个值应该是有效的
        assert not _is_nan(macd_line[-1])
        assert not _is_nan(signal_line[-1])
        assert not _is_nan(histogram[-1])
        # 持续上涨时，MACD线应为正
        assert macd_line[-1] > 0

    def test_macd_downtrend(self) -> None:
        """下跌趋势MACD应为负。"""
        prices = [100.0 - i * 0.5 for i in range(60)]
        macd_line, _, _ = calc_macd(prices)
        assert macd_line[-1] < 0


# ============================================================
# calc_rsi 测试
# ============================================================


class TestCalcRSI:
    """RSI计算测试。"""

    def test_rsi_insufficient_data(self) -> None:
        """数据不足时返回NaN。"""
        result = calc_rsi([1.0, 2.0, 3.0], 14)
        assert all(_is_nan(v) for v in result)

    def test_rsi_continuous_rise(self) -> None:
        """持续上涨RSI应接近100。"""
        prices = [float(i) for i in range(1, 30)]
        result = calc_rsi(prices, 14)
        valid = [v for v in result if not _is_nan(v)]
        assert len(valid) > 0
        assert valid[-1] == pytest.approx(100.0)

    def test_rsi_continuous_fall(self) -> None:
        """持续下跌RSI应接近0。"""
        prices = [100.0 - i for i in range(30)]
        result = calc_rsi(prices, 14)
        valid = [v for v in result if not _is_nan(v)]
        assert len(valid) > 0
        assert valid[-1] == pytest.approx(0.0, abs=0.1)

    def test_rsi_range(self) -> None:
        """RSI值应在0-100范围内。"""
        prices = [10.0, 12.0, 11.0, 13.0, 12.5, 14.0, 13.0, 15.0,
                  14.5, 16.0, 15.5, 17.0, 16.0, 18.0, 17.5, 19.0,
                  18.0, 17.0, 19.0, 20.0]
        result = calc_rsi(prices, 14)
        for v in result:
            if not _is_nan(v):
                assert 0 <= v <= 100


# ============================================================
# calc_volume_ratio 测试
# ============================================================


class TestCalcVolumeRatio:
    """成交量比率测试。"""

    def test_volume_ratio_equal(self) -> None:
        """均匀成交量，量比接近1。"""
        volumes = [100.0] * 30
        assert calc_volume_ratio(volumes) == pytest.approx(1.0)

    def test_volume_ratio_increase(self) -> None:
        """近期放量。"""
        volumes = [100.0] * 20 + [200.0] * 5
        ratio = calc_volume_ratio(volumes)
        assert ratio > 1.0

    def test_volume_ratio_decrease(self) -> None:
        """近期缩量。"""
        volumes = [200.0] * 20 + [50.0] * 5
        ratio = calc_volume_ratio(volumes)
        assert ratio < 1.0

    def test_volume_ratio_insufficient_data(self) -> None:
        """数据不足返回1.0。"""
        assert calc_volume_ratio([100.0] * 5) == pytest.approx(1.0)


# ============================================================
# TechnicalAnalyzer 测试
# ============================================================


class TestTechnicalAnalyzer:
    """技术分析器综合测试。"""

    def setup_method(self) -> None:
        self.analyzer = TechnicalAnalyzer()

    def test_empty_klines(self) -> None:
        """空K线列表返回默认结果。"""
        result = self.analyzer.analyze([])
        assert isinstance(result, TechnicalSummary)
        assert result.ma_alignment == "混乱"
        assert result.overall_score == 0
        assert "数据不足" in result.summary

    def test_uptrend_analysis(self) -> None:
        """上涨趋势分析。"""
        # 生成250个持续上涨的价格
        closes = [10.0 + i * 0.1 for i in range(250)]
        volumes = [1000.0] * 250
        klines = _make_klines(closes, volumes)

        result = self.analyzer.analyze(klines)
        assert result.ma_alignment == "多头排列"
        assert result.overall_score > 0

    def test_downtrend_analysis(self) -> None:
        """下跌趋势分析。"""
        closes = [50.0 - i * 0.1 for i in range(250)]
        volumes = [1000.0] * 250
        klines = _make_klines(closes, volumes)

        result = self.analyzer.analyze(klines)
        assert result.ma_alignment == "空头排列"
        assert result.overall_score < 0

    def test_result_fields_complete(self) -> None:
        """结果字段完整性。"""
        closes = [10.0 + i * 0.05 for i in range(60)]
        klines = _make_klines(closes)

        result = self.analyzer.analyze(klines)
        assert result.ma_alignment in ("多头排列", "空头排列", "混乱")
        assert result.macd_signal in ("金叉", "死叉", "中性")
        assert result.rsi_status in ("超买", "超卖", "正常")
        assert result.volume_trend in ("放量", "缩量", "正常")
        assert -100 <= result.overall_score <= 100
        assert len(result.summary) > 0

    def test_score_range(self) -> None:
        """评分在-100到100之间。"""
        # 极端上涨 + 放量
        closes = [10.0 + i * 0.5 for i in range(250)]
        volumes = [100.0] * 245 + [500.0] * 5
        klines = _make_klines(closes, volumes)

        result = self.analyzer.analyze(klines)
        assert -100 <= result.overall_score <= 100

    def test_summary_in_chinese(self) -> None:
        """中文描述。"""
        closes = [10.0 + i * 0.05 for i in range(60)]
        klines = _make_klines(closes)

        result = self.analyzer.analyze(klines)
        # 应包含中文关键词
        assert any(
            kw in result.summary
            for kw in ["技术面", "均线", "MACD", "RSI", "成交量"]
        )

    def test_short_data(self) -> None:
        """少量数据也不报错。"""
        closes = [10.0, 11.0, 10.5]
        klines = _make_klines(closes)

        result = self.analyzer.analyze(klines)
        assert isinstance(result, TechnicalSummary)
        # 数据少，MA排列应为混乱
        assert result.ma_alignment == "混乱"

    def test_rsi_overbought(self) -> None:
        """RSI超买判断。"""
        # 先平后急涨
        closes = [10.0] * 20 + [10.0 + i * 2.0 for i in range(1, 20)]
        klines = _make_klines(closes)

        result = self.analyzer.analyze(klines)
        # RSI在急涨后应该较高
        assert result.rsi_value > 50

    def test_volume_increase(self) -> None:
        """放量检测。"""
        closes = [10.0 + i * 0.05 for i in range(30)]
        volumes = [100.0] * 25 + [500.0] * 5
        klines = _make_klines(closes, volumes)

        result = self.analyzer.analyze(klines)
        assert result.volume_trend == "放量"

    def test_volume_decrease(self) -> None:
        """缩量检测。"""
        closes = [10.0 + i * 0.05 for i in range(30)]
        volumes = [500.0] * 25 + [50.0] * 5
        klines = _make_klines(closes, volumes)

        result = self.analyzer.analyze(klines)
        assert result.volume_trend == "缩量"

    def test_macd_golden_cross(self) -> None:
        """MACD金叉场景。"""
        # 先跌后涨，制造金叉
        closes = [50.0 - i * 0.5 for i in range(40)] + [
            30.0 + i * 1.0 for i in range(30)
        ]
        klines = _make_klines(closes)

        result = self.analyzer.analyze(klines)
        # 后段大幅上涨，MACD应为金叉
        assert result.macd_signal == "金叉"

    def test_macd_death_cross(self) -> None:
        """MACD死叉场景。"""
        # 先涨后跌，制造死叉
        closes = [10.0 + i * 1.0 for i in range(40)] + [
            50.0 - i * 1.0 for i in range(30)
        ]
        klines = _make_klines(closes)

        result = self.analyzer.analyze(klines)
        assert result.macd_signal == "死叉"

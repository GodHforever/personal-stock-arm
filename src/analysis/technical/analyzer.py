"""技术分析器。

综合MA、MACD、RSI、成交量等指标进行技术分析。
"""

from src.analysis.technical.indicators import (
    _is_nan,
    calc_ma,
    calc_macd,
    calc_rsi,
    calc_volume_ratio,
)
from src.analysis.technical.models import (
    MACDResult,
    MAResult,
    RSIResult,
    TechnicalSummary,
)
from src.data.a_share.base import KlineBar

# MA周期配置
MA_PERIODS = [5, 10, 20, 60, 120, 250]

# RSI阈值
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0

# 量比阈值
VOLUME_RATIO_HIGH = 1.5
VOLUME_RATIO_LOW = 0.7


class TechnicalAnalyzer:
    """技术分析器，综合多个技术指标给出分析结果。"""

    def analyze(self, klines: list[KlineBar]) -> TechnicalSummary:
        """对K线数据进行综合技术分析。

        Args:
            klines: K线数据列表（从旧到新排列）

        Returns:
            技术分析综合结果
        """
        if not klines:
            return self._empty_summary()

        closes = [k.close for k in klines]
        volumes = [k.volume for k in klines]

        # 计算各指标
        ma_results = self._calc_ma_series(closes)
        ma_alignment = self._judge_ma_alignment(ma_results)

        macd_result = self._calc_macd_result(closes)
        macd_signal = self._judge_macd_signal(macd_result)

        rsi_result = self._calc_rsi_result(closes)
        rsi_value, rsi_status = self._judge_rsi(rsi_result)

        volume_trend = self._judge_volume_trend(volumes)

        # 综合评分
        overall_score = self._calc_overall_score(
            ma_alignment, macd_signal, rsi_value, rsi_status, volume_trend
        )

        # 生成描述
        summary_text = self._generate_summary(
            ma_alignment, macd_signal, rsi_value, rsi_status, volume_trend, overall_score
        )

        return TechnicalSummary(
            ma_alignment=ma_alignment,
            macd_signal=macd_signal,
            rsi_value=rsi_value,
            rsi_status=rsi_status,
            volume_trend=volume_trend,
            overall_score=overall_score,
            summary=summary_text,
            ma_results=ma_results,
            macd_result=macd_result,
            rsi_result=rsi_result,
        )

    def _empty_summary(self) -> TechnicalSummary:
        """数据不足时返回空结果。"""
        return TechnicalSummary(
            ma_alignment="混乱",
            macd_signal="中性",
            rsi_value=50.0,
            rsi_status="正常",
            volume_trend="正常",
            overall_score=0,
            summary="数据不足，无法进行技术分析。",
        )

    def _calc_ma_series(self, closes: list[float]) -> list[MAResult]:
        """计算多周期MA。"""
        results: list[MAResult] = []
        for period in MA_PERIODS:
            values = calc_ma(closes, period)
            current = values[-1] if values and not _is_nan(values[-1]) else None
            results.append(MAResult(period=period, values=values, current=current))
        return results

    def _judge_ma_alignment(self, ma_results: list[MAResult]) -> str:
        """判断MA排列状态。

        多头排列：短期均线在上，长期均线在下（MA5 > MA10 > MA20 > MA60）
        空头排列：短期均线在下，长期均线在上
        """
        # 取有当前值的MA
        current_values = [(r.period, r.current) for r in ma_results if r.current is not None]
        if len(current_values) < 3:
            return "混乱"

        # 按周期排序
        current_values.sort(key=lambda x: x[0])
        values_only = [v for _, v in current_values]

        # 检查是否严格递减（多头排列：短周期值 > 长周期值）
        is_bullish = all(values_only[i] > values_only[i + 1] for i in range(len(values_only) - 1))
        if is_bullish:
            return "多头排列"

        # 检查是否严格递增（空头排列：短周期值 < 长周期值）
        is_bearish = all(values_only[i] < values_only[i + 1] for i in range(len(values_only) - 1))
        if is_bearish:
            return "空头排列"

        return "混乱"

    def _calc_macd_result(self, closes: list[float]) -> MACDResult:
        """计算MACD。"""
        macd_line, signal_line, histogram = calc_macd(closes)
        current_macd = macd_line[-1] if macd_line and not _is_nan(macd_line[-1]) else None
        current_signal = signal_line[-1] if signal_line and not _is_nan(signal_line[-1]) else None
        current_hist = histogram[-1] if histogram and not _is_nan(histogram[-1]) else None

        return MACDResult(
            macd_line=macd_line,
            signal_line=signal_line,
            histogram=histogram,
            current_macd=current_macd,
            current_signal=current_signal,
            current_histogram=current_hist,
        )

    def _judge_macd_signal(self, result: MACDResult) -> str:
        """判断MACD信号。

        金叉：MACD线从下方穿越信号线（柱状图由负转正）
        死叉：MACD线从上方穿越信号线（柱状图由正转负）
        当柱状图绝对值极小（相对MACD线）时视为中性。
        """
        hist = result.histogram
        # 找最近两个有效值
        valid_hist: list[float] = []
        for v in reversed(hist):
            if not _is_nan(v):
                valid_hist.append(v)
                if len(valid_hist) == 2:
                    break

        if len(valid_hist) < 2:
            return "中性"

        current_hist = valid_hist[0]
        prev_hist = valid_hist[1]

        # 柱状图极小时视为中性（MACD线和信号线高度收敛）
        macd_abs = abs(result.current_macd) if result.current_macd is not None else 0.0
        threshold = max(macd_abs * 0.05, 0.001)
        if abs(current_hist) < threshold and abs(prev_hist) < threshold:
            return "中性"

        if prev_hist <= 0 < current_hist:
            return "金叉"
        if prev_hist >= 0 > current_hist:
            return "死叉"

        # 未发生交叉，根据当前柱状图方向判断
        if current_hist > 0:
            return "金叉"
        if current_hist < 0:
            return "死叉"
        return "中性"

    def _calc_rsi_result(self, closes: list[float]) -> RSIResult:
        """计算RSI。"""
        values = calc_rsi(closes)
        current = values[-1] if values and not _is_nan(values[-1]) else None
        return RSIResult(values=values, current=current)

    def _judge_rsi(self, result: RSIResult) -> tuple[float, str]:
        """判断RSI状态。"""
        if result.current is None:
            return 50.0, "正常"

        rsi = result.current
        if rsi >= RSI_OVERBOUGHT:
            return rsi, "超买"
        if rsi <= RSI_OVERSOLD:
            return rsi, "超卖"
        return rsi, "正常"

    def _judge_volume_trend(self, volumes: list[float]) -> str:
        """判断成交量趋势。"""
        ratio = calc_volume_ratio(volumes)
        if ratio >= VOLUME_RATIO_HIGH:
            return "放量"
        if ratio <= VOLUME_RATIO_LOW:
            return "缩量"
        return "正常"

    def _calc_overall_score(
        self,
        ma_alignment: str,
        macd_signal: str,
        rsi_value: float,
        rsi_status: str,
        volume_trend: str,
    ) -> int:
        """计算综合多空信号评分（-100到100）。

        评分权重：
        - MA排列: 30分
        - MACD信号: 30分
        - RSI状态: 20分
        - 成交量趋势: 20分（作为辅助确认）
        """
        score = 0.0

        # MA排列评分 (±30)
        ma_scores = {"多头排列": 30, "空头排列": -30, "混乱": 0}
        score += ma_scores.get(ma_alignment, 0)

        # MACD信号评分 (±30)
        macd_scores = {"金叉": 30, "死叉": -30, "中性": 0}
        score += macd_scores.get(macd_signal, 0)

        # RSI评分 (±20)
        # RSI在50以上偏多，以下偏空；超买超卖时分数达到极值
        if rsi_status == "超买":
            score += -10  # 超买反而是风险信号
        elif rsi_status == "超卖":
            score += 10  # 超卖可能是机会
        else:
            # 正常区间，根据RSI值线性映射
            score += (rsi_value - 50) * 0.4  # 50为中性，30-70映射到±8

        # 成交量趋势评分 (±20，作为方向确认)
        # 放量配合上涨信号加分，放量配合下跌信号也加分（确认趋势）
        trend_base = score  # 当前得分方向
        if volume_trend == "放量":
            if trend_base > 0:
                score += 20  # 放量上涨，确认多头
            elif trend_base < 0:
                score -= 20  # 放量下跌，确认空头
        elif volume_trend == "缩量":
            if trend_base > 0:
                score -= 10  # 缩量上涨，多头动能不足
            elif trend_base < 0:
                score += 10  # 缩量下跌，空头动能减弱

        # 限制在-100到100
        return max(-100, min(100, int(score)))

    def _generate_summary(
        self,
        ma_alignment: str,
        macd_signal: str,
        rsi_value: float,
        rsi_status: str,
        volume_trend: str,
        overall_score: int,
    ) -> str:
        """生成中文综合描述。"""
        parts: list[str] = []

        # 总体判断
        if overall_score >= 50:
            parts.append("技术面强势看多。")
        elif overall_score >= 20:
            parts.append("技术面偏多。")
        elif overall_score > -20:
            parts.append("技术面中性震荡。")
        elif overall_score > -50:
            parts.append("技术面偏空。")
        else:
            parts.append("技术面强势看空。")

        # MA描述
        ma_desc = {
            "多头排列": "均线呈多头排列，趋势向上",
            "空头排列": "均线呈空头排列，趋势向下",
            "混乱": "均线交织，趋势不明",
        }
        parts.append(ma_desc.get(ma_alignment, "均线状态未知") + "；")

        # MACD描述
        macd_desc = {
            "金叉": "MACD金叉，多头动能增强",
            "死叉": "MACD死叉，空头动能增强",
            "中性": "MACD中性",
        }
        parts.append(macd_desc.get(macd_signal, "MACD状态未知") + "；")

        # RSI描述
        parts.append(f"RSI为{rsi_value:.1f}，{rsi_status}；")

        # 成交量描述
        vol_desc = {
            "放量": "成交量放大，市场活跃度高",
            "缩量": "成交量萎缩，市场观望情绪浓",
            "正常": "成交量正常",
        }
        parts.append(vol_desc.get(volume_trend, "成交量状态未知") + "。")

        return "".join(parts)

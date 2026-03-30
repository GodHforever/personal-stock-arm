"""技术分析数据模型。"""

from pydantic import BaseModel


class MAResult(BaseModel):
    """移动平均线计算结果。"""

    period: int
    values: list[float]
    current: float | None = None


class MACDResult(BaseModel):
    """MACD计算结果。"""

    macd_line: list[float]
    signal_line: list[float]
    histogram: list[float]
    current_macd: float | None = None
    current_signal: float | None = None
    current_histogram: float | None = None


class RSIResult(BaseModel):
    """RSI计算结果。"""

    values: list[float]
    current: float | None = None


class TechnicalSummary(BaseModel):
    """技术分析综合结果。"""

    # MA分析
    ma_alignment: str
    """多头排列 / 空头排列 / 混乱"""

    # MACD分析
    macd_signal: str
    """金叉 / 死叉 / 中性"""

    # RSI分析
    rsi_value: float
    rsi_status: str
    """超买 / 超卖 / 正常"""

    # 成交量分析
    volume_trend: str
    """放量 / 缩量 / 正常"""

    # 综合评分
    overall_score: int
    """-100到100，正值偏多，负值偏空"""

    # 中文综合描述
    summary: str

    # 详细数据（可选）
    ma_results: list[MAResult] = []
    macd_result: MACDResult | None = None
    rsi_result: RSIResult | None = None

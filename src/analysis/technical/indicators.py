"""技术指标计算函数。

纯函数实现，不依赖外部数值计算库。
"""


def calc_ma(prices: list[float], period: int) -> list[float]:
    """计算简单移动平均线（SMA）。

    Args:
        prices: 价格序列（从旧到新）
        period: 移动平均周期

    Returns:
        移动平均值列表，前 period-1 个位置为 NaN
    """
    if len(prices) < period:
        return [float("nan")] * len(prices)

    result: list[float] = [float("nan")] * (period - 1)
    window_sum = sum(prices[:period])
    result.append(window_sum / period)

    for i in range(period, len(prices)):
        window_sum += prices[i] - prices[i - period]
        result.append(window_sum / period)

    return result


def calc_ema(prices: list[float], period: int) -> list[float]:
    """计算指数移动平均线（EMA）。

    Args:
        prices: 价格序列（从旧到新）
        period: EMA周期

    Returns:
        EMA值列表，前 period-1 个位置为 NaN
    """
    if len(prices) < period:
        return [float("nan")] * len(prices)

    result: list[float] = [float("nan")] * (period - 1)
    # 首个EMA值用SMA初始化
    sma = sum(prices[:period]) / period
    result.append(sma)

    multiplier = 2.0 / (period + 1)
    prev_ema = sma
    for i in range(period, len(prices)):
        ema = (prices[i] - prev_ema) * multiplier + prev_ema
        result.append(ema)
        prev_ema = ema

    return result


def calc_macd(
    prices: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    """计算MACD指标。

    Args:
        prices: 价格序列（从旧到新）
        fast: 快线EMA周期，默认12
        slow: 慢线EMA周期，默认26
        signal: 信号线EMA周期，默认9

    Returns:
        (MACD线, 信号线, 柱状图) 三个等长列表
    """
    n = len(prices)
    if n < slow:
        nan_list = [float("nan")] * n
        return nan_list, nan_list[:], nan_list[:]

    ema_fast = calc_ema(prices, fast)
    ema_slow = calc_ema(prices, slow)

    # MACD线 = 快线EMA - 慢线EMA
    macd_line: list[float] = []
    for i in range(n):
        if _is_nan(ema_fast[i]) or _is_nan(ema_slow[i]):
            macd_line.append(float("nan"))
        else:
            macd_line.append(ema_fast[i] - ema_slow[i])

    # 对有效的MACD值计算信号线（EMA）
    valid_macd = [v for v in macd_line if not _is_nan(v)]
    if len(valid_macd) < signal:
        nan_list = [float("nan")] * n
        return macd_line, nan_list, nan_list

    signal_ema = calc_ema(valid_macd, signal)

    # 将信号线映射回原始长度
    signal_line: list[float] = []
    valid_idx = 0
    for v in macd_line:
        if _is_nan(v):
            signal_line.append(float("nan"))
        else:
            signal_line.append(signal_ema[valid_idx])
            valid_idx += 1

    # 柱状图 = MACD线 - 信号线
    histogram: list[float] = []
    for i in range(n):
        if _is_nan(macd_line[i]) or _is_nan(signal_line[i]):
            histogram.append(float("nan"))
        else:
            histogram.append(macd_line[i] - signal_line[i])

    return macd_line, signal_line, histogram


def calc_rsi(prices: list[float], period: int = 14) -> list[float]:
    """计算RSI指标。

    使用Wilder平滑方法（指数移动平均）。

    Args:
        prices: 价格序列（从旧到新）
        period: RSI周期，默认14

    Returns:
        RSI值列表，前 period 个位置为 NaN
    """
    n = len(prices)
    if n < period + 1:
        return [float("nan")] * n

    result: list[float] = [float("nan")] * period

    # 计算价格变动
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, n):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    # 首个平均涨跌幅（SMA）
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))

    # 后续用Wilder平滑
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    return result


def calc_volume_ratio(volumes: list[float], short_period: int = 5, long_period: int = 20) -> float:
    """计算量比（短期均量/长期均量）。

    Args:
        volumes: 成交量序列（从旧到新）
        short_period: 短期均量周期
        long_period: 长期均量周期

    Returns:
        量比值，大于1为放量，小于1为缩量
    """
    if len(volumes) < long_period:
        return 1.0

    short_avg = sum(volumes[-short_period:]) / short_period
    long_avg = sum(volumes[-long_period:]) / long_period

    if long_avg == 0:
        return 1.0

    return short_avg / long_avg


def _is_nan(value: float) -> bool:
    """检查值是否为NaN。"""
    return value != value  # noqa: PLR0124

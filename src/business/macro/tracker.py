"""宏观数据追踪器：拉取指标、与前值比较、LLM 分析。"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

from sqlalchemy import select

from src.analysis.llm.base import BaseLLMProvider
from src.business.macro.indicators import MACRO_INDICATORS, IndicatorDef
from src.business.macro.models import MacroIndicator, MacroRecord
from src.db.engine import Database
from src.log import get_logger

logger = get_logger(__name__)

# 单指标拉取超时（秒）
_FETCH_TIMEOUT = 10

# 分析用 Prompt 模板
_ANALYSIS_PROMPT = """你是一位资深宏观经济分析师。以下是今日拉取的宏观经济指标数据，请分析：
1. 各指标变化的含义
2. 对 A 股市场的潜在影响
3. 需要关注的风险和机会

请用中文回答，条理清晰，重点突出。

## 指标数据

{indicators_text}
"""


class MacroTracker:
    """宏观数据追踪器。

    职责：
    - 遍历预定义指标列表，调用 AkShare API 拉取最新值
    - 与数据库中的前值比较，计算变化量和变化率
    - 更新数据库（只保留最新值 + 前值）
    - 调用 LLM 分析宏观数据含义
    """

    def __init__(
        self,
        db: Database,
        llm: BaseLLMProvider,
    ) -> None:
        self._db = db
        self._llm = llm

    async def pull_daily_indicators(self) -> list[MacroIndicator]:
        """拉取当日所有宏观指标数据。

        逐个拉取指标，单个失败不影响其他指标。

        Returns:
            拉取结果列表（含成功和失败的指标）
        """
        results: list[MacroIndicator] = []
        for indicator_def in MACRO_INDICATORS:
            indicator = await self._pull_single_indicator(indicator_def)
            results.append(indicator)

        # 统计
        success_count = sum(1 for i in results if i.error is None and not i.no_update)
        no_update_count = sum(1 for i in results if i.no_update)
        error_count = sum(1 for i in results if i.error is not None)
        logger.info(
            "宏观指标拉取完成: 成功=%d, 暂无更新=%d, 失败=%d",
            success_count,
            no_update_count,
            error_count,
        )

        return results

    async def analyze(self, indicators: list[MacroIndicator]) -> str:
        """调用 LLM 分析宏观数据含义和市场影响。

        Args:
            indicators: 宏观指标列表

        Returns:
            LLM 分析文本；调用失败时返回错误提示
        """
        indicators_text = self._format_indicators_for_llm(indicators)
        prompt = _ANALYSIS_PROMPT.format(indicators_text=indicators_text)

        response = await self._llm.complete(prompt)
        if not response.success:
            error_msg = f"LLM 分析失败: {response.error}"
            logger.error(error_msg)
            return error_msg

        logger.info(
            "宏观数据 LLM 分析完成，输入=%d tokens, 输出=%d tokens",
            response.input_tokens,
            response.output_tokens,
        )
        return response.content

    async def run_daily(self) -> tuple[list[MacroIndicator], str]:
        """一键执行每日宏观数据追踪：拉取 + 分析。

        Returns:
            (指标列表, LLM 分析文本)
        """
        indicators = await self.pull_daily_indicators()
        analysis = await self.analyze(indicators)
        return indicators, analysis

    async def _pull_single_indicator(
        self, indicator_def: IndicatorDef
    ) -> MacroIndicator:
        """拉取单个指标数据。"""
        try:
            value, data_date = await asyncio.wait_for(
                self._fetch_from_akshare(indicator_def),
                timeout=_FETCH_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("指标 %s 拉取超时（%ds）", indicator_def.name, _FETCH_TIMEOUT)
            return MacroIndicator(
                name=indicator_def.name,
                category=indicator_def.category,
                unit=indicator_def.unit,
                source="akshare",
                error=f"拉取超时（{_FETCH_TIMEOUT}s）",
            )
        except Exception as exc:
            logger.warning("指标 %s 拉取失败: %s", indicator_def.name, exc)
            return MacroIndicator(
                name=indicator_def.name,
                category=indicator_def.category,
                unit=indicator_def.unit,
                source="akshare",
                error=str(exc),
            )

        if value is None:
            # 当日无更新
            prev = await self._get_previous_record(indicator_def.name)
            return MacroIndicator(
                name=indicator_def.name,
                category=indicator_def.category,
                unit=indicator_def.unit,
                source="akshare",
                value=prev.current_value if prev else None,
                prev_value=prev.previous_value if prev else None,
                updated_at=prev.data_updated_at if prev else None,
                no_update=True,
                last_available_date=(
                    prev.data_updated_at.strftime("%Y-%m-%d")
                    if prev and prev.data_updated_at
                    else "未知"
                ),
            )

        # 与前值比较并更新数据库
        prev_value, change, change_pct = await self._compare_and_update(
            indicator_def=indicator_def,
            new_value=value,
            data_date=data_date,
        )

        now = datetime.datetime.now()
        return MacroIndicator(
            name=indicator_def.name,
            category=indicator_def.category,
            value=value,
            prev_value=prev_value,
            unit=indicator_def.unit,
            updated_at=data_date or now,
            source="akshare",
            change=change,
            change_pct=change_pct,
        )

    async def _fetch_from_akshare(
        self, indicator_def: IndicatorDef
    ) -> tuple[float | None, datetime.datetime | None]:
        """调用 AkShare API 拉取指标数据。

        Returns:
            (最新值, 数据日期)。如果当日无更新，返回 (None, None)。
        """
        try:
            import akshare as ak  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("akshare 库未安装，请运行 pip install akshare") from exc

        api_func = getattr(ak, indicator_def.akshare_api, None)
        if api_func is None:
            raise RuntimeError(f"AkShare 中未找到 API: {indicator_def.akshare_api}")

        # 通过 asyncio.to_thread 调用同步 API
        kwargs = self._build_api_kwargs(indicator_def)
        df = await asyncio.to_thread(api_func, **kwargs)

        if df is None or (hasattr(df, "empty") and df.empty):
            return None, None

        return self._extract_value(df, indicator_def)

    @staticmethod
    def _build_api_kwargs(indicator_def: IndicatorDef) -> dict[str, Any]:
        """构建 AkShare API 调用参数。"""
        kwargs: dict[str, Any] = {}

        # 商品类 API 需要额外参数
        if indicator_def.akshare_api == "futures_foreign_commodity_realtime":
            if "原油" in indicator_def.name or "WTI" in indicator_def.name:
                kwargs["symbol"] = "WTI原油"
            elif "黄金" in indicator_def.name or "COMEX" in indicator_def.name:
                kwargs["symbol"] = "COMEX黄金"

        # 银行间利率需要指定市场
        if indicator_def.akshare_api == "rate_interbank":
            kwargs["market"] = "上海银行间同业拆放利率"
            kwargs["symbol"] = "Shibor人民币"
            kwargs["indicator"] = "隔夜"

        return kwargs

    @staticmethod
    def _extract_value(
        df: Any, indicator_def: IndicatorDef
    ) -> tuple[float | None, datetime.datetime | None]:
        """从 DataFrame 中提取最新值和日期。"""
        if indicator_def.value_column not in df.columns:
            # 尝试模糊匹配列名
            for col in df.columns:
                if indicator_def.value_column in str(col):
                    indicator_def = IndicatorDef(
                        name=indicator_def.name,
                        category=indicator_def.category,
                        akshare_api=indicator_def.akshare_api,
                        frequency=indicator_def.frequency,
                        unit=indicator_def.unit,
                        value_column=str(col),
                        description=indicator_def.description,
                    )
                    break
            else:
                raise RuntimeError(
                    f"列 '{indicator_def.value_column}' 不在返回数据中，"
                    f"可用列: {list(df.columns)}"
                )

        # 取最新一行
        last_row = df.iloc[-1]
        raw_value = last_row[indicator_def.value_column]

        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            return None, None

        # 尝试提取日期
        data_date: datetime.datetime | None = None
        for date_col in ["日期", "date", "月份", "报告日期"]:
            if date_col in df.columns:
                try:
                    import pandas as pd  # type: ignore[import-untyped]

                    data_date = pd.Timestamp(last_row[date_col]).to_pydatetime()
                except Exception:
                    pass
                break

        return value, data_date

    async def _get_previous_record(self, indicator_name: str) -> MacroRecord | None:
        """从数据库获取指标的前值记录。"""
        async with self._db.session() as session:
            result = await session.execute(
                select(MacroRecord).where(
                    MacroRecord.indicator_name == indicator_name
                )
            )
            return result.scalar_one_or_none()

    async def _compare_and_update(
        self,
        *,
        indicator_def: IndicatorDef,
        new_value: float,
        data_date: datetime.datetime | None,
    ) -> tuple[float | None, float | None, float | None]:
        """与前值比较并更新数据库记录。

        Returns:
            (前值, 变化量, 变化率%)
        """
        async with self._db.session() as session:
            result = await session.execute(
                select(MacroRecord).where(
                    MacroRecord.indicator_name == indicator_def.name
                )
            )
            record = result.scalar_one_or_none()

            prev_value: float | None = None
            change: float | None = None
            change_pct: float | None = None

            if record is not None:
                prev_value = record.current_value
                if prev_value is not None:
                    change = new_value - prev_value
                    if abs(prev_value) > 1e-10:
                        change_pct = round(change / abs(prev_value) * 100, 4)

                # 更新记录：当前值变为前值，新值写入当前值
                record.previous_value = prev_value
                record.current_value = new_value
                record.change = change
                record.change_pct = change_pct
                record.unit = indicator_def.unit
                record.source = "akshare"
                record.data_updated_at = data_date
            else:
                # 首次记录
                record = MacroRecord(
                    indicator_name=indicator_def.name,
                    current_value=new_value,
                    previous_value=None,
                    change=None,
                    change_pct=None,
                    unit=indicator_def.unit,
                    source="akshare",
                    data_updated_at=data_date,
                )
                session.add(record)

            return prev_value, change, change_pct

    @staticmethod
    def _format_indicators_for_llm(indicators: list[MacroIndicator]) -> str:
        """将指标列表格式化为 LLM 可读的文本。"""
        lines: list[str] = []
        for ind in indicators:
            if ind.error:
                lines.append(f"- {ind.name}（{ind.category}）：拉取失败 — {ind.error}")
            elif ind.no_update:
                val_str = f"{ind.value}{ind.unit}" if ind.value is not None else "无数据"
                lines.append(
                    f"- {ind.name}（{ind.category}）：暂无更新，"
                    f"最近数据 {ind.last_available_date}: {val_str}"
                )
            else:
                val_str = f"{ind.value}{ind.unit}" if ind.value is not None else "N/A"
                change_str = ""
                if ind.change is not None:
                    direction = "+" if ind.change >= 0 else ""
                    change_str = f"，变化 {direction}{ind.change}{ind.unit}"
                    if ind.change_pct is not None:
                        change_str += f"（{direction}{ind.change_pct}%）"
                prev_str = ""
                if ind.prev_value is not None:
                    prev_str = f"，前值 {ind.prev_value}{ind.unit}"
                lines.append(
                    f"- {ind.name}（{ind.category}）：{val_str}{change_str}{prev_str}"
                )

        return "\n".join(lines)

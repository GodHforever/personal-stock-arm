"""财报处理器：扫描财报并通过 LLM 生成摘要。"""

from __future__ import annotations

from datetime import date

from src.analysis.llm.base import BaseLLMProvider
from src.business.earnings.models import EarningsSummary
from src.data.news.manager import NewsManager
from src.log import get_logger

logger = get_logger(__name__)

# 财报季月份
_EARNINGS_SEASON_MONTHS = {4, 8, 10}

_EARNINGS_PROMPT_TEMPLATE = """请分析以下财报相关信息，生成一份简洁的中文财报摘要。

股票代码：{stock_code}
相关新闻和公告：
{news_text}

请按以下格式输出 Markdown 摘要：
## {stock_code} 财报摘要

### 关键指标
- 营收：（如有数据请填写）
- 净利润：（如有数据请填写）
- 毛利率：（如有数据请填写）
- 净利率：（如有数据请填写）

### 同比变化
- 营收同比：（如有数据请填写）
- 净利润同比：（如有数据请填写）

### 要点分析
（分析财报亮点和风险点，2-3句话）

### 投资者关注
（投资者应关注的要点，1-2句话）
"""


class EarningsProcessor:
    """财报处理器：扫描财报并通过 LLM 生成摘要。

    在财报季（4/8/10月）扫描新发布的财报，通过 LLM 生成包含
    营收、净利润、毛利率等关键指标的 Markdown 摘要。
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        news_manager: NewsManager,
        watchlist_codes: list[str] | None = None,
    ) -> None:
        """初始化财报处理器。

        Args:
            llm: LLM 调用接口
            news_manager: 新闻数据管理器
            watchlist_codes: 自选股代码列表（用于 watchlist 范围扫描）
        """
        self._llm = llm
        self._news = news_manager
        self._watchlist_codes = watchlist_codes or []

    @staticmethod
    def is_earnings_season(check_date: date | None = None) -> bool:
        """判断指定日期是否在财报季。

        Args:
            check_date: 待检查日期，默认今天
        """
        target = check_date or date.today()
        return target.month in _EARNINGS_SEASON_MONTHS

    async def scan_reports(
        self, scope: str = "watchlist"
    ) -> list[EarningsSummary]:
        """扫描财报并生成摘要。

        Args:
            scope: 扫描范围，"watchlist" 仅扫描自选股，"all" 扫描所有

        Returns:
            EarningsSummary 列表
        """
        if scope == "watchlist":
            codes = list(self._watchlist_codes)
        elif scope == "all":
            # "all" 模式下使用自选股列表作为基础范围
            # 实际生产中可扩展为从数据源获取全部股票列表
            codes = list(self._watchlist_codes)
        else:
            logger.warning("未知的扫描范围: %s，使用 watchlist", scope)
            codes = list(self._watchlist_codes)

        if not codes:
            logger.info("无待扫描股票列表，跳过财报扫描")
            return []

        logger.info("开始财报扫描，范围=%s，股票数=%d", scope, len(codes))

        results: list[EarningsSummary] = []
        for code in codes:
            try:
                summary = await self.summarize_single(code)
                results.append(summary)
            except Exception as exc:
                logger.error("股票 %s 财报扫描失败: %s", code, exc)
                results.append(
                    EarningsSummary(
                        stock_code=code,
                        errors=[f"扫描失败: {exc}"],
                    )
                )

        logger.info("财报扫描完成，成功=%d，总数=%d", len(results), len(codes))
        return results

    async def summarize_single(self, stock_code: str) -> EarningsSummary:
        """对单只股票生成财报摘要。

        Args:
            stock_code: 股票代码

        Returns:
            EarningsSummary 摘要对象
        """
        logger.info("开始生成 %s 财报摘要", stock_code)

        # 获取该股票的财报相关新闻
        news_items = await self._news.search(
            f"{stock_code} 财报 业绩", limit=10
        )

        news_text = "\n".join(
            f"- [{item.title}]({item.url})" if item.url else f"- {item.title}"
            for item in news_items
        ) or "暂无相关新闻数据"

        # 调用 LLM 生成摘要
        prompt = _EARNINGS_PROMPT_TEMPLATE.format(
            stock_code=stock_code,
            news_text=news_text,
        )

        response = await self._llm.complete(prompt, max_tokens=2048)

        errors: list[str] = []
        summary_md = ""
        if response.success:
            summary_md = response.content
        else:
            error_msg = f"LLM 调用失败: {response.error}"
            logger.warning("股票 %s %s", stock_code, error_msg)
            errors.append(error_msg)

        return EarningsSummary(
            stock_code=stock_code,
            summary_markdown=summary_md,
            errors=errors,
        )

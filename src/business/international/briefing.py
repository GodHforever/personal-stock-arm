"""国际金融简报生成器：每日隔夜市场 + 事件影响 + 未来日程。"""

from __future__ import annotations

from datetime import date

from src.analysis.llm.base import BaseLLMProvider
from src.business.international.models import BriefingResult, MarketSnapshot
from src.data.international.manager import IntlDataManager
from src.data.news.manager import NewsManager
from src.log import get_logger

logger = get_logger(__name__)

_BRIEFING_PROMPT_TEMPLATE = """请根据以下国际市场数据和新闻，生成一份中文国际金融简报。

日期：{briefing_date}

## 市场数据
{market_data}

## 相关新闻
{news_text}

请按以下格式输出 Markdown 简报：

# 国际金融简报（{briefing_date}）

## 一、隔夜市场回顾
（概述各主要市场表现，指出涨跌幅较大的市场及原因）

## 二、重大事件与影响
（分析影响市场的关键事件，评估对A股可能的影响）

## 三、未来7天关注日程
（列出未来一周值得关注的国际金融事件和数据发布）

## 四、对A股影响评估
（综合判断国际市场对A股的影响，给出简要建议）
"""


class InternationalBriefingGenerator:
    """国际金融简报生成器。

    每日生成包含隔夜市场表现、重大事件影响分析和未来7天
    全球金融日程的中文简报。
    """

    def __init__(
        self,
        llm: BaseLLMProvider,
        intl_data: IntlDataManager,
        news_manager: NewsManager,
    ) -> None:
        """初始化简报生成器。

        Args:
            llm: LLM 调用接口
            intl_data: 国际市场数据管理器
            news_manager: 新闻数据管理器
        """
        self._llm = llm
        self._intl_data = intl_data
        self._news = news_manager

    async def generate(
        self, briefing_date: date | None = None
    ) -> BriefingResult:
        """生成国际金融简报。

        Args:
            briefing_date: 简报日期，默认今天

        Returns:
            BriefingResult 简报结果
        """
        target_date = briefing_date or date.today()
        logger.info("开始生成 %s 国际金融简报", target_date)

        errors: list[str] = []

        # 获取国际指数数据
        snapshots = await self._fetch_market_data(errors)

        # 获取国际金融新闻
        news_items = await self._fetch_news(errors)

        # 组装 LLM prompt
        market_data = self._format_market_data(snapshots)
        news_text = "\n".join(
            f"- {item.title}" for item in news_items
        ) or "暂无相关新闻数据"

        prompt = _BRIEFING_PROMPT_TEMPLATE.format(
            briefing_date=target_date.isoformat(),
            market_data=market_data,
            news_text=news_text,
        )

        # 调用 LLM 生成简报
        response = await self._llm.complete(prompt, max_tokens=4096)

        briefing_md = ""
        if response.success:
            briefing_md = response.content
        else:
            error_msg = f"LLM 调用失败: {response.error}"
            logger.warning(error_msg)
            errors.append(error_msg)

        result = BriefingResult(
            briefing_date=target_date,
            market_snapshots=snapshots,
            briefing_markdown=briefing_md,
            news_count=len(news_items),
            errors=errors,
        )

        logger.info(
            "国际金融简报生成完成: 日期=%s, 指数=%d, 新闻=%d, 错误=%d",
            target_date,
            len(snapshots),
            len(news_items),
            len(errors),
        )
        return result

    async def _fetch_market_data(
        self, errors: list[str]
    ) -> list[MarketSnapshot]:
        """获取国际指数数据，失败时降级为空列表。"""
        try:
            quotes = await self._intl_data.get_market_indices()
            return [
                MarketSnapshot(
                    index_name=q.name or q.symbol,
                    symbol=q.symbol,
                    price=q.price,
                    change_pct=q.change_pct,
                )
                for q in quotes
            ]
        except Exception as exc:
            error_msg = f"获取国际指数数据失败: {exc}"
            logger.warning(error_msg)
            errors.append(error_msg)
            return []

    async def _fetch_news(
        self, errors: list[str]
    ) -> list:
        """获取国际金融新闻，失败时降级为空列表。"""
        try:
            return await self._news.search("国际金融 隔夜市场 美股", limit=15)
        except Exception as exc:
            error_msg = f"获取国际金融新闻失败: {exc}"
            logger.warning(error_msg)
            errors.append(error_msg)
            return []

    @staticmethod
    def _format_market_data(snapshots: list[MarketSnapshot]) -> str:
        """将市场快照格式化为文本。"""
        if not snapshots:
            return "暂无市场数据"
        lines: list[str] = []
        for s in snapshots:
            direction = "↑" if s.change_pct >= 0 else "↓"
            lines.append(
                f"- {s.index_name}（{s.symbol}）：{s.price:.2f} "
                f"{direction}{abs(s.change_pct):.2f}%"
            )
        return "\n".join(lines)

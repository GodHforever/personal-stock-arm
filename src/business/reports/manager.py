"""研报管理器：研报搜索、LLM 摘要生成、评级追踪。"""

from __future__ import annotations

from src.analysis.llm.base import BaseLLMProvider
from src.business.reports.models import ReportFilter, ResearchReportSummary
from src.data.news.manager import NewsManager
from src.log import get_logger

logger = get_logger(__name__)

_REPORT_SEARCH_KEYWORDS = {
    "": "券商研报 研究报告",
    "买入": "研报 买入评级",
    "增持": "研报 增持评级",
    "中性": "研报 中性评级",
    "减持": "研报 减持评级",
    "卖出": "研报 卖出评级",
}

_SUMMARIZE_PROMPT_TEMPLATE = """请分析以下研报相关信息，生成一份结构化的中文研报摘要。

研报标题：{title}
来源：{source}
内容：
{content}

请按以下格式输出 Markdown 摘要：

## 研报摘要：{title}

### 核心观点
（提取 2-4 个核心观点，每个一行）

### 目标价与评级
- 评级：（买入/增持/中性/减持/卖出）
- 目标价：（如有）
- 评级变化：（上调/下调/维持/首次覆盖）

### 逻辑链
（分析研报的投资逻辑链，从行业趋势到公司竞争优势到业绩预期）

### 风险提示
（提取研报中的风险提示，每条一行）

### 一句话总结
（用一句话概括研报核心结论）
"""


class ReportManager:
    """研报管理器：搜索研报、生成 LLM 摘要、追踪评级变化。"""

    def __init__(
        self,
        llm: BaseLLMProvider,
        news_manager: NewsManager,
    ) -> None:
        """初始化研报管理器。

        Args:
            llm: LLM 调用接口
            news_manager: 新闻数据管理器（用于搜索研报信息）
        """
        self._llm = llm
        self._news = news_manager

    async def search_reports(
        self, filters: ReportFilter | None = None
    ) -> list[ResearchReportSummary]:
        """搜索研报列表。

        Args:
            filters: 筛选条件（行业/个股/评级）

        Returns:
            ResearchReportSummary 列表
        """
        if filters is None:
            filters = ReportFilter()

        # 构建搜索关键词
        query = self._build_search_query(filters)
        logger.info("搜索研报: query=%s, limit=%d", query, filters.limit)

        # 从新闻源搜索研报相关信息
        try:
            news_items = await self._news.search(query, limit=filters.limit)
        except Exception as exc:
            logger.error("搜索研报失败: %s", exc)
            return []

        # 将新闻条目转换为研报摘要（基本信息）
        results: list[ResearchReportSummary] = []
        for item in news_items:
            report = ResearchReportSummary(
                title=item.title,
                source=item.source,
                url=item.url,
                published_at=item.published_at,
                stock_code=filters.stock_code,
                industry=filters.industry,
            )
            results.append(report)

        logger.info("搜索研报完成: 找到 %d 条", len(results))
        return results

    async def summarize(self, report_url: str) -> ResearchReportSummary:
        """对单条研报生成 LLM 摘要。

        Args:
            report_url: 研报链接

        Returns:
            ResearchReportSummary 含 LLM 摘要
        """
        logger.info("开始生成研报摘要: %s", report_url)

        # 通过新闻源搜索该研报的相关信息
        try:
            news_items = await self._news.search(report_url, limit=5)
        except Exception as exc:
            logger.error("获取研报信息失败: %s", exc)
            return ResearchReportSummary(
                url=report_url,
                errors=[f"获取研报信息失败: {exc}"],
            )

        # 组装内容
        title = news_items[0].title if news_items else "未知研报"
        source = news_items[0].source if news_items else "未知来源"
        content = "\n".join(
            f"- {item.title}: {item.summary}" for item in news_items
        ) or "暂无详细内容"

        # 调用 LLM 生成摘要
        prompt = _SUMMARIZE_PROMPT_TEMPLATE.format(
            title=title,
            source=source,
            content=content,
        )

        response = await self._llm.complete(prompt, max_tokens=2048)

        errors: list[str] = []
        summary_md = ""
        if response.success:
            summary_md = response.content
        else:
            error_msg = f"LLM 调用失败: {response.error}"
            logger.warning(error_msg)
            errors.append(error_msg)

        return ResearchReportSummary(
            title=title,
            source=source,
            url=report_url,
            published_at=news_items[0].published_at if news_items else None,
            summary_markdown=summary_md,
            errors=errors,
        )

    @staticmethod
    def _build_search_query(filters: ReportFilter) -> str:
        """根据筛选条件构建搜索关键词。"""
        parts: list[str] = []

        # 评级关键词
        rating_kw = _REPORT_SEARCH_KEYWORDS.get(
            filters.rating, "券商研报 研究报告"
        )
        parts.append(rating_kw)

        # 个股代码
        if filters.stock_code:
            parts.append(filters.stock_code)

        # 行业
        if filters.industry:
            parts.append(filters.industry)

        return " ".join(parts)

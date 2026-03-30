"""每日个股分析流水线：技术面+基本面+新闻+LLM 综合判断。"""

from __future__ import annotations

import asyncio
import datetime
import json

from src.analysis.llm.base import BaseLLMProvider
from src.analysis.llm.prompt_manager import PromptManager
from src.analysis.technical.analyzer import TechnicalAnalyzer
from src.business.watchlist.manager import WatchlistManager
from src.business.watchlist.models import (
    AnalysisRecord,
    LLMVerdict,
    StockAnalysisResult,
)
from src.data.a_share.manager import DataFetcherManager
from src.data.news.manager import NewsManager
from src.db.engine import Database
from src.log import get_logger

logger = get_logger(__name__)

# 分析流水线并发上限
_MAX_CONCURRENT = 5


class StockAnalysisPipeline:
    """每日个股分析流水线。

    对单只或一组股票执行综合分析：
    1. 获取K线数据 → 技术分析
    2. 获取基本面数据
    3. 获取新闻
    4. 组装 prompt → LLM 综合判断
    5. 持久化结果到数据库

    任何单一数据源失败不阻塞整体分析，降级处理并记录错误。
    """

    def __init__(
        self,
        db: Database,
        data_manager: DataFetcherManager,
        news_manager: NewsManager,
        technical_analyzer: TechnicalAnalyzer,
        llm_provider: BaseLLMProvider,
        prompt_manager: PromptManager | None = None,
        watchlist_manager: WatchlistManager | None = None,
    ) -> None:
        self._db = db
        self._data_manager = data_manager
        self._news_manager = news_manager
        self._technical = technical_analyzer
        self._llm = llm_provider
        self._prompt_manager = prompt_manager or PromptManager()
        self._watchlist_manager = watchlist_manager

    async def analyze_stock(self, code: str) -> StockAnalysisResult:
        """对单只股票执行综合分析。

        Args:
            code: 股票代码

        Returns:
            StockAnalysisResult 综合分析结果
        """
        today = datetime.date.today().isoformat()
        result = StockAnalysisResult(stock_code=code, analysis_date=today)
        errors: list[str] = []

        # 1. 技术面分析
        technical_summary, technical_score = await self._analyze_technical(code, errors)
        result.technical_summary = technical_summary
        result.technical_score = technical_score

        # 2. 基本面数据
        await self._fetch_fundamentals(code, result, errors)

        # 3. 新闻
        news_summary, news_count = await self._fetch_news(code, errors)
        result.news_summary = news_summary
        result.news_count = news_count

        # 4. LLM 综合判断
        verdict = await self._get_llm_verdict(code, result, errors)
        result.llm_verdict = verdict

        result.errors = errors
        return result

    async def analyze_group(self, group_name: str) -> list[StockAnalysisResult]:
        """对自选股分组进行批量分析。

        Args:
            group_name: 分组名称

        Returns:
            各股票的分析结果列表

        Raises:
            ValueError: 分组不存在
        """
        if self._watchlist_manager is None:
            raise RuntimeError("未配置 WatchlistManager，无法按分组分析")

        group = await self._watchlist_manager.get_group(group_name)
        if group is None:
            raise ValueError(f"分组 '{group_name}' 不存在")

        stocks = group.stocks
        if not stocks:
            logger.info("分组 '%s' 中没有股票，跳过分析", group_name)
            return []

        logger.info("开始分析分组 '%s'，共 %d 只股票", group_name, len(stocks))

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _limited_analyze(code: str) -> StockAnalysisResult:
            async with semaphore:
                return await self._safe_analyze_stock(code)

        tasks = [_limited_analyze(code) for code in stocks]
        results = await asyncio.gather(*tasks)

        # 持久化结果
        await self._save_results(list(results), group_name)

        logger.info(
            "分组 '%s' 分析完成，成功 %d / %d",
            group_name,
            sum(1 for r in results if not r.errors),
            len(results),
        )
        return list(results)

    async def _safe_analyze_stock(self, code: str) -> StockAnalysisResult:
        """安全地分析单只股票，捕获所有异常。"""
        try:
            return await self.analyze_stock(code)
        except Exception as exc:
            logger.exception("分析股票 %s 时发生未预期异常", code)
            return StockAnalysisResult(
                stock_code=code,
                analysis_date=datetime.date.today().isoformat(),
                errors=[f"分析失败: {exc}"],
            )

    async def _analyze_technical(
        self, code: str, errors: list[str]
    ) -> tuple[str, int]:
        """获取K线数据并执行技术分析。"""
        try:
            klines = await self._data_manager.get_kline(code, period="daily", count=250)
            summary = self._technical.analyze(klines)
            return summary.summary, summary.overall_score
        except Exception as exc:
            msg = f"技术分析失败: {exc}"
            logger.warning("[%s] %s", code, msg)
            errors.append(msg)
            return "技术分析数据获取失败", 0

    async def _fetch_fundamentals(
        self, code: str, result: StockAnalysisResult, errors: list[str]
    ) -> None:
        """获取基本面数据。"""
        try:
            fundamentals = await self._data_manager.get_fundamentals(code)
            result.stock_name = fundamentals.name
            result.pe_ttm = fundamentals.pe_ttm
            result.pb = fundamentals.pb
            result.market_cap = fundamentals.market_cap
            result.revenue = fundamentals.revenue
            result.net_profit = fundamentals.net_profit
        except Exception as exc:
            msg = f"基本面数据获取失败: {exc}"
            logger.warning("[%s] %s", code, msg)
            errors.append(msg)

    async def _fetch_news(
        self, code: str, errors: list[str]
    ) -> tuple[str, int]:
        """获取个股新闻摘要。"""
        try:
            news_items = await self._news_manager.get_stock_news(code, limit=10)
            if not news_items:
                return "暂无相关新闻", 0

            # 拼接新闻标题作为摘要
            titles = [item.title for item in news_items]
            summary = "；".join(titles[:5])
            if len(titles) > 5:
                summary += f"等共 {len(titles)} 条新闻"
            return summary, len(news_items)
        except Exception as exc:
            msg = f"新闻获取失败: {exc}"
            logger.warning("[%s] %s", code, msg)
            errors.append(msg)
            return "新闻数据获取失败", 0

    async def _get_llm_verdict(
        self,
        code: str,
        result: StockAnalysisResult,
        errors: list[str],
    ) -> LLMVerdict:
        """调用 LLM 进行综合判断。"""
        try:
            # 构建分析上下文
            context_parts: list[str] = []
            if result.technical_summary:
                context_parts.append(f"技术面: {result.technical_summary}")
            if result.pe_ttm is not None:
                context_parts.append(f"PE(TTM): {result.pe_ttm:.2f}")
            if result.pb is not None:
                context_parts.append(f"PB: {result.pb:.2f}")
            if result.market_cap is not None:
                context_parts.append(f"总市值: {result.market_cap:.0f}")
            if result.news_summary:
                context_parts.append(f"近期新闻: {result.news_summary}")

            additional_context = "\n".join(context_parts) if context_parts else ""

            prompt = self._prompt_manager.render(
                "stock_analysis.j2",
                stock_code=code,
                stock_name=result.stock_name or code,
                industry="",
                additional_context=additional_context,
            )

            response = await self._llm.complete(
                prompt,
                response_schema=LLMVerdict,
                temperature=0.3,
                max_tokens=2048,
            )

            if response.success and response.parsed is not None:
                return LLMVerdict.model_validate(response.parsed.model_dump())

            if response.success and response.content:
                # LLM 返回了内容但未能解析为结构化输出
                return LLMVerdict(
                    signal="中性",
                    confidence=30,
                    reasoning=response.content[:500],
                    risk_alerts=["LLM 输出未能解析为结构化格式"],
                )

            # LLM 调用失败
            msg = f"LLM 调用失败: {response.error}"
            errors.append(msg)
            return LLMVerdict(
                signal="中性",
                confidence=0,
                reasoning="LLM 服务不可用",
                risk_alerts=[msg],
            )
        except Exception as exc:
            msg = f"LLM 综合判断异常: {exc}"
            logger.warning("[%s] %s", code, msg)
            errors.append(msg)
            return LLMVerdict(
                signal="中性",
                confidence=0,
                reasoning="LLM 分析过程异常",
                risk_alerts=[msg],
            )

    async def _save_results(
        self, results: list[StockAnalysisResult], group_name: str
    ) -> None:
        """将分析结果持久化到数据库。"""
        try:
            async with self._db.session() as session:
                for r in results:
                    record = AnalysisRecord(
                        stock_code=r.stock_code,
                        analysis_date=datetime.date.fromisoformat(r.analysis_date)
                        if r.analysis_date
                        else datetime.date.today(),
                        group_name=group_name,
                        result_json=json.dumps(
                            r.model_dump(), ensure_ascii=False, default=str
                        ),
                    )
                    session.add(record)
            logger.info(
                "保存 %d 条分析结果到数据库 (分组: %s)", len(results), group_name
            )
        except Exception as exc:
            logger.exception("保存分析结果失败: %s", exc)

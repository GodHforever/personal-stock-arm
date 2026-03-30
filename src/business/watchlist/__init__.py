"""自选股管理与分析模块。"""

from src.business.watchlist.manager import WatchlistManager
from src.business.watchlist.models import (
    AnalysisRecord,
    LLMVerdict,
    StockAnalysisResult,
    WatchlistGroup,
)
from src.business.watchlist.pipeline import StockAnalysisPipeline

__all__ = [
    "AnalysisRecord",
    "LLMVerdict",
    "StockAnalysisResult",
    "StockAnalysisPipeline",
    "WatchlistGroup",
    "WatchlistManager",
]

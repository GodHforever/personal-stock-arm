"""国际金融简报数据模型。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MarketSnapshot(BaseModel):
    """单个市场指数快照。"""

    index_name: str = Field(description="指数名称")
    symbol: str = Field(default="", description="指数代码")
    price: float = Field(default=0.0, description="最新价")
    change_pct: float = Field(default=0.0, description="涨跌幅（%）")


class BriefingResult(BaseModel):
    """国际金融简报结果。

    包含隔夜市场表现、重大事件分析和未来日程，
    由 InternationalBriefingGenerator 生成。
    """

    briefing_date: date = Field(description="简报日期")

    # 市场数据
    market_snapshots: list[MarketSnapshot] = Field(
        default_factory=list, description="主要国际指数快照"
    )

    # LLM 生成的简报内容
    briefing_markdown: str = Field(
        default="", description="LLM 生成的 Markdown 简报正文"
    )

    # 元数据
    news_count: int = Field(default=0, description="引用的新闻数量")
    errors: list[str] = Field(
        default_factory=list, description="处理过程中的错误信息"
    )

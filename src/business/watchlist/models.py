"""自选股管理与分析数据模型：DB 模型 + Pydantic Schema。"""

from __future__ import annotations

import datetime
import json

from pydantic import BaseModel, Field
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin

# ============================================================
# SQLAlchemy ORM 模型
# ============================================================


class WatchlistGroup(TimestampMixin, Base):
    """自选股分组表。"""

    __tablename__ = "watchlist_group"

    name: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="分组名称"
    )
    description: Mapped[str] = mapped_column(
        String(256), nullable=False, default="", comment="分组描述"
    )
    strategy: Mapped[str] = mapped_column(
        String(64), nullable=False, default="default", comment="分析策略"
    )
    push_frequency: Mapped[str] = mapped_column(
        String(32), nullable=False, default="daily", comment="推送频率"
    )
    stocks_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", comment="股票代码列表 JSON"
    )

    @property
    def stocks(self) -> list[str]:
        """获取股票代码列表。"""
        return json.loads(self.stocks_json)

    @stocks.setter
    def stocks(self, value: list[str]) -> None:
        """设置股票代码列表。"""
        self.stocks_json = json.dumps(value, ensure_ascii=False)


class AnalysisRecord(TimestampMixin, Base):
    """分析结果记录表。"""

    __tablename__ = "analysis_record"

    stock_code: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True, comment="股票代码"
    )
    analysis_date: Mapped[datetime.date] = mapped_column(
        nullable=False, index=True, comment="分析日期"
    )
    group_name: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="所属分组"
    )
    result_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="分析结果 JSON"
    )


# ============================================================
# Pydantic Schema（业务层数据传输）
# ============================================================


class LLMVerdict(BaseModel):
    """LLM 综合判断结果。"""

    signal: str = Field(
        default="中性",
        description="看多 / 看空 / 中性",
    )
    confidence: int = Field(
        default=50,
        ge=0,
        le=100,
        description="置信度 0-100",
    )
    reasoning: str = Field(
        default="",
        description="判断理由",
    )
    risk_alerts: list[str] = Field(
        default_factory=list,
        description="风险提示列表",
    )


class StockAnalysisResult(BaseModel):
    """单只股票的综合分析结果。"""

    stock_code: str
    stock_name: str = ""
    analysis_date: str = ""

    # 技术面摘要
    technical_summary: str = ""
    technical_score: int = 0

    # 基本面数据
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    revenue: float | None = None
    net_profit: float | None = None

    # 新闻摘要
    news_summary: str = ""
    news_count: int = 0

    # LLM 综合判断
    llm_verdict: LLMVerdict = Field(default_factory=LLMVerdict)

    # 错误信息（部分数据源失败时记录）
    errors: list[str] = Field(default_factory=list)

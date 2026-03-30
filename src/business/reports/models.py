"""研报管理数据模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResearchReportSummary(BaseModel):
    """研报摘要数据模型。

    由 ReportManager 通过 LLM 生成的研报结构化摘要。
    """

    title: str = Field(default="", description="研报标题")
    source: str = Field(default="", description="研报来源（券商名称）")
    url: str = Field(default="", description="研报链接")
    published_at: datetime | None = Field(
        default=None, description="发布时间"
    )

    # 标的信息
    stock_code: str = Field(default="", description="股票代码")
    stock_name: str = Field(default="", description="股票名称")
    industry: str = Field(default="", description="所属行业")

    # 评级信息
    rating: str = Field(default="", description="评级（买入/增持/中性/减持/卖出）")
    rating_change: str = Field(
        default="", description="评级变化（上调/下调/维持/首次覆盖）"
    )
    target_price: float | None = Field(default=None, description="目标价")

    # LLM 提取的结构化内容
    core_views: list[str] = Field(
        default_factory=list, description="核心观点列表"
    )
    logic_chain: str = Field(default="", description="逻辑链分析")
    risk_alerts: list[str] = Field(
        default_factory=list, description="风险提示列表"
    )

    # LLM 生成的 Markdown 摘要
    summary_markdown: str = Field(
        default="", description="LLM 生成的 Markdown 摘要"
    )

    # 元数据
    errors: list[str] = Field(
        default_factory=list, description="处理过程中的错误信息"
    )


class ReportFilter(BaseModel):
    """研报筛选条件。"""

    industry: str = Field(default="", description="行业筛选")
    stock_code: str = Field(default="", description="个股筛选")
    rating: str = Field(default="", description="评级筛选")
    limit: int = Field(default=20, description="返回数量上限")

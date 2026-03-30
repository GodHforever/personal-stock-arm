"""财报处理数据模型。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class EarningsSummary(BaseModel):
    """财报摘要数据模型。

    由 EarningsProcessor 扫描财报后通过 LLM 生成。
    """

    stock_code: str = Field(description="股票代码")
    stock_name: str = Field(default="", description="公司名称")
    report_period: str = Field(default="", description="报告期（如 2025Q3）")
    report_date: date | None = Field(default=None, description="报告发布日期")

    # 关键财务指标
    revenue: float | None = Field(default=None, description="营收（亿元）")
    net_profit: float | None = Field(default=None, description="净利润（亿元）")
    gross_margin: float | None = Field(default=None, description="毛利率（%）")
    net_margin: float | None = Field(default=None, description="净利率（%）")

    # 同比变化
    revenue_yoy: float | None = Field(default=None, description="营收同比变化（%）")
    net_profit_yoy: float | None = Field(default=None, description="净利润同比变化（%）")

    # LLM 生成内容
    summary_markdown: str = Field(default="", description="LLM 生成的 Markdown 摘要")

    # 元数据
    errors: list[str] = Field(default_factory=list, description="处理过程中的错误信息")

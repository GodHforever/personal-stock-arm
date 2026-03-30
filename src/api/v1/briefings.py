"""国际简报、财报摘要、研报摘要路由。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.v1.schemas import ApiResponse

router = APIRouter(tags=["简报"])


# ============================================================
# Schema
# ============================================================


class BriefingItem(BaseModel):
    """国际简报条目。"""

    id: int
    title: str = Field(description="标题")
    source: str = Field(default="", description="来源")
    summary: str = Field(default="", description="摘要")
    published_at: str = Field(default="", description="发布时间")


class EarningsItem(BaseModel):
    """财报摘要条目。"""

    id: int
    stock_code: str = Field(description="股票代码")
    stock_name: str = Field(default="", description="股票名称")
    period: str = Field(default="", description="报告期")
    revenue: str = Field(default="", description="营收")
    net_profit: str = Field(default="", description="净利润")
    summary: str = Field(default="", description="摘要")


class ReportItem(BaseModel):
    """研报摘要条目。"""

    id: int
    title: str = Field(description="标题")
    institution: str = Field(default="", description="机构")
    stock_code: str = Field(default="", description="相关股票")
    rating: str = Field(default="", description="评级")
    summary: str = Field(default="", description="摘要")
    published_at: str = Field(default="", description="发布时间")


# ============================================================
# 路由
# ============================================================


@router.get(
    "/briefings",
    summary="获取国际简报列表",
    description="获取最新的国际金融市场简报",
    response_model=ApiResponse[list[BriefingItem]],
)
async def list_briefings() -> ApiResponse[list[BriefingItem]]:
    """获取国际简报列表。"""
    # MVP 阶段返回空列表，后续对接 business/international 模块
    return ApiResponse(data=[])


@router.get(
    "/earnings",
    summary="获取财报摘要列表",
    description="获取最新的财报摘要信息",
    response_model=ApiResponse[list[EarningsItem]],
)
async def list_earnings() -> ApiResponse[list[EarningsItem]]:
    """获取财报摘要列表。"""
    # MVP 阶段返回空列表，后续对接 business/earnings 模块
    return ApiResponse(data=[])


@router.get(
    "/reports",
    summary="获取研报摘要列表",
    description="获取最新的研报摘要信息",
    response_model=ApiResponse[list[ReportItem]],
)
async def list_reports() -> ApiResponse[list[ReportItem]]:
    """获取研报摘要列表。"""
    # MVP 阶段返回空列表，后续对接 business/reports 模块
    return ApiResponse(data=[])

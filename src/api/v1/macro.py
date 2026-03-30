"""宏观数据路由。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.v1.schemas import ApiResponse

router = APIRouter(prefix="/macro", tags=["宏观数据"])


class MacroIndicator(BaseModel):
    """宏观指标数据。"""

    name: str = Field(description="指标名称")
    value: str = Field(default="", description="指标值")
    unit: str = Field(default="", description="单位")
    period: str = Field(default="", description="时间周期")
    trend: str = Field(default="", description="趋势: 上升/下降/持平")


class MacroData(BaseModel):
    """宏观数据响应。"""

    indicators: list[MacroIndicator] = Field(default_factory=list, description="宏观指标列表")
    summary: str = Field(default="", description="宏观分析摘要")
    updated_at: str = Field(default="", description="最后更新时间")


@router.get(
    "",
    summary="获取宏观数据",
    description="获取最新的宏观经济指标数据和分析摘要",
    response_model=ApiResponse[MacroData],
)
async def get_macro_data() -> ApiResponse[MacroData]:
    """获取宏观经济数据。"""
    # MVP 阶段返回空数据，后续对接 business/macro 模块
    data = MacroData()
    return ApiResponse(data=data)

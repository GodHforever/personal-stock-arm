"""健康检查路由。"""

from __future__ import annotations

import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.v1.schemas import ApiResponse

router = APIRouter(tags=["健康检查"])


class HealthData(BaseModel):
    """健康检查响应数据。"""

    status: str = Field(default="healthy", description="服务状态")
    timestamp: str = Field(description="当前时间戳")
    version: str = Field(default="0.1.0", description="服务版本")


@router.get(
    "/health",
    summary="健康检查",
    description="检查服务是否正常运行",
    response_model=ApiResponse[HealthData],
)
async def health_check() -> ApiResponse[HealthData]:
    """返回服务健康状态。"""
    data = HealthData(
        timestamp=datetime.datetime.now(tz=datetime.UTC).isoformat(),
    )
    return ApiResponse(data=data)

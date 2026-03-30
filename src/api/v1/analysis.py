"""分析路由：异步分析任务触发与状态查询。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.api.v1.schemas import ApiResponse, ErrorCodes, PaginatedData

router = APIRouter(prefix="/analysis", tags=["分析"])


# ============================================================
# 请求/响应 Schema
# ============================================================


class AnalysisRunRequest(BaseModel):
    """触发分析请求。"""

    watchlist_id: int = Field(description="自选股分组 ID")


class TaskCreated(BaseModel):
    """任务创建响应。"""

    task_id: str = Field(description="异步任务 ID")


class TaskStatus(BaseModel):
    """任务状态响应。"""

    task_id: str = Field(description="任务 ID")
    status: str = Field(description="任务状态: pending / running / completed / failed")
    progress: int = Field(default=0, ge=0, le=100, description="进度百分比")
    message: str = Field(default="", description="状态消息")


class AnalysisResultItem(BaseModel):
    """分析结果条目。"""

    id: int
    stock_code: str = Field(description="股票代码")
    stock_name: str = Field(default="", description="股票名称")
    analysis_date: str = Field(default="", description="分析日期")
    signal: str = Field(default="中性", description="信号: 看多/看空/中性")
    confidence: int = Field(default=50, ge=0, le=100, description="置信度")
    summary: str = Field(default="", description="分析摘要")


# ============================================================
# 内存存储（MVP 阶段）
# ============================================================

_tasks: dict[str, TaskStatus] = {}
_results: list[AnalysisResultItem] = []


def _reset_store() -> None:
    """重置内存存储（仅供测试使用）。"""
    _tasks.clear()
    _results.clear()


# ============================================================
# 路由
# ============================================================


@router.post(
    "/run",
    summary="触发分析任务",
    description="异步触发指定分组的股票分析任务",
    response_model=ApiResponse[TaskCreated],
    status_code=202,
)
async def run_analysis(req: AnalysisRunRequest) -> ApiResponse[TaskCreated]:
    """触发异步分析任务。"""
    task_id = str(uuid.uuid4())
    _tasks[task_id] = TaskStatus(
        task_id=task_id,
        status="pending",
        progress=0,
        message=f"分析任务已创建，分组 ID: {req.watchlist_id}",
    )
    return ApiResponse(
        data=TaskCreated(task_id=task_id),
        message="分析任务已提交",
    )


@router.get(
    "/tasks/{task_id}",
    summary="查询任务状态",
    description="查询指定异步任务的执行状态和进度",
    response_model=ApiResponse[TaskStatus],
)
async def get_task_status(task_id: str) -> ApiResponse[TaskStatus]:
    """查询异步任务状态。"""
    task = _tasks.get(task_id)
    if task is None:
        return ApiResponse(
            code=ErrorCodes.NOT_FOUND,
            message=f"任务 {task_id} 不存在",
        )
    return ApiResponse(data=task)


@router.get(
    "/results",
    summary="获取分析结果",
    description="分页获取分析结果列表",
    response_model=ApiResponse[PaginatedData[AnalysisResultItem]],
)
async def list_results(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
) -> ApiResponse[PaginatedData[AnalysisResultItem]]:
    """分页获取分析结果。"""
    total = len(_results)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    start = (page - 1) * page_size
    end = start + page_size
    items = _results[start:end]
    paginated = PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
    return ApiResponse(data=paginated)

"""自选股管理路由。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.v1.schemas import ApiResponse, ErrorCodes

router = APIRouter(prefix="/watchlists", tags=["自选股"])


# ============================================================
# 请求/响应 Schema
# ============================================================


class WatchlistCreateRequest(BaseModel):
    """创建自选股分组请求。"""

    name: str = Field(description="分组名称")
    description: str = Field(default="", description="分组描述")
    strategy: str = Field(default="default", description="分析策略")
    push_frequency: str = Field(default="daily", description="推送频率")


class WatchlistItem(BaseModel):
    """自选股分组摘要。"""

    id: int
    name: str
    description: str = ""
    stock_count: int = 0


class WatchlistDetail(BaseModel):
    """自选股分组详情。"""

    id: int
    name: str
    description: str = ""
    strategy: str = "default"
    push_frequency: str = "daily"
    stocks: list[str] = Field(default_factory=list)


class StockAddRequest(BaseModel):
    """添加股票请求。"""

    code: str = Field(description="股票代码")


# ============================================================
# 内存存储（MVP 阶段，后续切换到数据库）
# ============================================================

_watchlists: dict[int, dict] = {}
_next_id: int = 1


def _reset_store() -> None:
    """重置内存存储（仅供测试使用）。"""
    global _next_id  # noqa: PLW0603
    _watchlists.clear()
    _next_id = 1


# ============================================================
# 路由
# ============================================================


@router.get(
    "",
    summary="获取所有自选股分组",
    description="返回所有自选股分组列表",
    response_model=ApiResponse[list[WatchlistItem]],
)
async def list_watchlists() -> ApiResponse[list[WatchlistItem]]:
    """获取所有自选股分组。"""
    items = [
        WatchlistItem(
            id=wl["id"],
            name=wl["name"],
            description=wl["description"],
            stock_count=len(wl["stocks"]),
        )
        for wl in _watchlists.values()
    ]
    return ApiResponse(data=items)


@router.post(
    "",
    summary="创建自选股分组",
    description="创建一个新的自选股分组",
    response_model=ApiResponse[WatchlistItem],
    status_code=201,
)
async def create_watchlist(req: WatchlistCreateRequest) -> ApiResponse[WatchlistItem]:
    """创建自选股分组。"""
    global _next_id  # noqa: PLW0603
    wl = {
        "id": _next_id,
        "name": req.name,
        "description": req.description,
        "strategy": req.strategy,
        "push_frequency": req.push_frequency,
        "stocks": [],
    }
    wl_id = _next_id
    _watchlists[wl_id] = wl
    _next_id += 1
    item = WatchlistItem(
        id=wl_id,
        name=req.name,
        description=req.description,
        stock_count=0,
    )
    return ApiResponse(data=item, message="分组创建成功")


@router.get(
    "/{watchlist_id}",
    summary="获取分组详情",
    description="获取指定自选股分组的详细信息",
    response_model=ApiResponse[WatchlistDetail],
)
async def get_watchlist(watchlist_id: int) -> ApiResponse[WatchlistDetail]:
    """获取自选股分组详情。"""
    wl = _watchlists.get(watchlist_id)
    if wl is None:
        return ApiResponse(
            code=ErrorCodes.NOT_FOUND,
            message=f"分组 {watchlist_id} 不存在",
        )
    detail = WatchlistDetail(
        id=wl["id"],
        name=wl["name"],
        description=wl["description"],
        strategy=wl["strategy"],
        push_frequency=wl["push_frequency"],
        stocks=wl["stocks"],
    )
    return ApiResponse(data=detail)


@router.delete(
    "/{watchlist_id}",
    summary="删除分组",
    description="删除指定的自选股分组",
    response_model=ApiResponse[None],
)
async def delete_watchlist(watchlist_id: int) -> ApiResponse[None]:
    """删除自选股分组。"""
    if watchlist_id not in _watchlists:
        return ApiResponse(
            code=ErrorCodes.NOT_FOUND,
            message=f"分组 {watchlist_id} 不存在",
        )
    del _watchlists[watchlist_id]
    return ApiResponse(message="分组删除成功")


@router.post(
    "/{watchlist_id}/stocks",
    summary="添加股票",
    description="向指定分组添加股票",
    response_model=ApiResponse[WatchlistDetail],
)
async def add_stock(watchlist_id: int, req: StockAddRequest) -> ApiResponse[WatchlistDetail]:
    """向分组添加股票。"""
    wl = _watchlists.get(watchlist_id)
    if wl is None:
        return ApiResponse(
            code=ErrorCodes.NOT_FOUND,
            message=f"分组 {watchlist_id} 不存在",
        )
    if req.code not in wl["stocks"]:
        wl["stocks"].append(req.code)
    detail = WatchlistDetail(
        id=wl["id"],
        name=wl["name"],
        description=wl["description"],
        strategy=wl["strategy"],
        push_frequency=wl["push_frequency"],
        stocks=wl["stocks"],
    )
    return ApiResponse(data=detail, message="股票添加成功")


@router.delete(
    "/{watchlist_id}/stocks/{stock_code}",
    summary="移除股票",
    description="从指定分组移除股票",
    response_model=ApiResponse[WatchlistDetail],
)
async def remove_stock(watchlist_id: int, stock_code: str) -> ApiResponse[WatchlistDetail]:
    """从分组移除股票。"""
    wl = _watchlists.get(watchlist_id)
    if wl is None:
        return ApiResponse(
            code=ErrorCodes.NOT_FOUND,
            message=f"分组 {watchlist_id} 不存在",
        )
    if stock_code in wl["stocks"]:
        wl["stocks"].remove(stock_code)
    detail = WatchlistDetail(
        id=wl["id"],
        name=wl["name"],
        description=wl["description"],
        strategy=wl["strategy"],
        push_frequency=wl["push_frequency"],
        stocks=wl["stocks"],
    )
    return ApiResponse(data=detail, message="股票移除成功")

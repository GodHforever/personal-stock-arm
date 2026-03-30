"""v1 主路由注册：汇集所有子路由到统一前缀。"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import analysis, briefings, health, macro, watchlists

v1_router = APIRouter(prefix="/api/v1")

# 注册子路由
v1_router.include_router(health.router)
v1_router.include_router(watchlists.router)
v1_router.include_router(analysis.router)
v1_router.include_router(macro.router)
v1_router.include_router(briefings.router)

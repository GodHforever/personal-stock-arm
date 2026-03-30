"""FastAPI 应用工厂：创建并配置应用实例。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.v1.router import v1_router
from src.api.v1.schemas import ApiResponse, ErrorCodes
from src.config.manager import ConfigLoadError
from src.network.errors import DataSourceError

logger = logging.getLogger(__name__)


class _CatchAllMiddleware(BaseHTTPMiddleware):
    """兜底异常中间件：捕获所有未处理的异常，返回统一错误响应。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        try:
            return await call_next(request)
        except Exception as exc:
            logger.exception("未预期异常: %s", exc)
            resp: ApiResponse[None] = ApiResponse(
                code=ErrorCodes.INTERNAL_ERROR,
                message="服务内部错误，请稍后重试",
            )
            return JSONResponse(status_code=500, content=resp.model_dump())


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    注册路由、中间件和全局异常处理器。
    """
    app = FastAPI(
        title="Stock-ARM API",
        description="Stock Analysis & Research Manager — A股个人金融分析工具 API",
        version="0.1.0",
    )

    # 兜底异常中间件（最外层）
    app.add_middleware(_CatchAllMiddleware)

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(v1_router)

    # 全局异常处理器
    @app.exception_handler(DataSourceError)
    async def data_source_error_handler(
        _request: Request, exc: DataSourceError
    ) -> JSONResponse:
        """数据源异常 → 统一错误响应。"""
        logger.warning("数据源异常: %s", exc)
        resp: ApiResponse[None] = ApiResponse(
            code=ErrorCodes.DATA_SOURCE_TIMEOUT,
            message=str(exc),
        )
        return JSONResponse(status_code=502, content=resp.model_dump())

    @app.exception_handler(ConfigLoadError)
    async def config_error_handler(
        _request: Request, exc: ConfigLoadError
    ) -> JSONResponse:
        """配置加载异常 → 统一错误响应。"""
        logger.error("配置异常: %s", exc)
        resp: ApiResponse[None] = ApiResponse(
            code=ErrorCodes.CONFIG_ERROR,
            message=str(exc),
        )
        return JSONResponse(status_code=500, content=resp.model_dump())

    @app.exception_handler(ValueError)
    async def value_error_handler(
        _request: Request, exc: ValueError
    ) -> JSONResponse:
        """参数校验异常 → 统一错误响应。"""
        resp: ApiResponse[None] = ApiResponse(
            code=ErrorCodes.INVALID_PARAM,
            message=str(exc),
        )
        return JSONResponse(status_code=400, content=resp.model_dump())

    return app

"""统一响应模型、分页模型、错误码枚举。"""

from __future__ import annotations

from enum import IntEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorCodes(IntEnum):
    """错误码枚举。

    - 0: 成功
    - 1xxx: 客户端错误
    - 2xxx: 数据源错误
    - 3xxx: LLM 错误
    - 4xxx: 系统错误
    """

    # 客户端错误
    INVALID_PARAM = 1001
    MISSING_FIELD = 1002
    NOT_FOUND = 1003

    # 数据源错误
    DATA_SOURCE_TIMEOUT = 2001
    DATA_SOURCE_UNAVAILABLE = 2002
    DATA_FORMAT_ERROR = 2003

    # LLM 错误
    LLM_TIMEOUT = 3001
    LLM_RATE_LIMITED = 3002
    LLM_INVALID_RESPONSE = 3003

    # 系统错误
    DATABASE_ERROR = 4001
    CONFIG_ERROR = 4002
    INTERNAL_ERROR = 4003


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应模型。"""

    code: int = Field(default=0, description="状态码，0 表示成功")
    data: T | None = Field(default=None, description="响应数据")
    message: str = Field(default="ok", description="响应消息")


class PaginatedData(BaseModel, Generic[T]):
    """分页数据模型。"""

    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页条数")
    total_pages: int = Field(default=0, description="总页数")

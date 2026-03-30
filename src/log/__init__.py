"""日志模块：提供统一的日志初始化和 logger 获取接口。"""

from __future__ import annotations

from src.log.setup import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]

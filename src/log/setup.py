"""日志配置模块：根据运行模式配置日志输出目标和格式。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config.models import AppConfig, RuntimeMode

# 日志格式：时间戳 + 级别 + 模块名 + 消息
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# RotatingFileHandler 参数
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5
LOG_FILE_NAME = "stock_arm.log"


def setup_logging(config: AppConfig) -> None:
    """根据运行模式初始化日志系统。

    - Cloud/Docker 模式: 文件 + stdout
    - Local 模式: 仅文件

    Args:
        config: 应用配置对象
    """
    # 确定日志级别
    level = getattr(logging, config.log_level, logging.INFO)

    # 创建日志目录
    log_dir = Path(config.data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME

    # 配置格式器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 获取 root logger 并清除已有 handler（避免重复配置）
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    # 文件 handler（所有模式都有）
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # stdout handler（Cloud/Docker 模式，或显式配置 log_to_stdout）
    if config.log_to_stdout or config.runtime_env in (
        RuntimeMode.CLOUD,
        RuntimeMode.DOCKER,
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    logging.getLogger(__name__).info(
        "日志系统初始化完成，级别: %s，输出目标: %s",
        config.log_level,
        "文件 + stdout" if len(root_logger.handlers) > 1 else "仅文件",
    )


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        命名的 Logger 实例
    """
    return logging.getLogger(name)

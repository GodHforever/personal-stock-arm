"""日志模块单元测试。"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.config.models import AppConfig, RuntimeMode
from src.log.setup import BACKUP_COUNT, LOG_FILE_NAME, MAX_BYTES, get_logger, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """每个测试前后重置 root logger。"""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield  # type: ignore[misc]
    root.handlers = original_handlers
    root.level = original_level


@pytest.fixture()
def local_config(tmp_path: Path) -> AppConfig:
    """本地模式配置。"""
    return AppConfig(
        runtime_env=RuntimeMode.LOCAL,
        data_dir=str(tmp_path),
        log_level="INFO",
        log_to_stdout=False,
    )


@pytest.fixture()
def cloud_config(tmp_path: Path) -> AppConfig:
    """云端模式配置。"""
    return AppConfig(
        runtime_env=RuntimeMode.CLOUD,
        data_dir=str(tmp_path),
        log_level="DEBUG",
        log_to_stdout=True,
    )


@pytest.fixture()
def docker_config(tmp_path: Path) -> AppConfig:
    """Docker 模式配置。"""
    return AppConfig(
        runtime_env=RuntimeMode.DOCKER,
        data_dir=str(tmp_path),
        log_level="WARNING",
        log_to_stdout=True,
    )


class TestSetupLogging:
    """setup_logging 函数测试。"""

    def test_local_mode_file_only(self, local_config: AppConfig) -> None:
        """Local 模式仅创建文件 handler。"""
        setup_logging(local_config)
        root = logging.getLogger()
        handler_types = [type(h) for h in root.handlers]
        assert logging.handlers.RotatingFileHandler in handler_types
        assert logging.StreamHandler not in [
            type(h) for h in root.handlers if type(h) is logging.StreamHandler
        ]

    def test_cloud_mode_file_and_stdout(self, cloud_config: AppConfig) -> None:
        """Cloud 模式同时创建文件和 stdout handler。"""
        setup_logging(cloud_config)
        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "RotatingFileHandler" in handler_types
        assert "StreamHandler" in handler_types

    def test_docker_mode_file_and_stdout(self, docker_config: AppConfig) -> None:
        """Docker 模式同时创建文件和 stdout handler。"""
        setup_logging(docker_config)
        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert "RotatingFileHandler" in handler_types
        assert "StreamHandler" in handler_types

    def test_log_directory_created(self, local_config: AppConfig) -> None:
        """日志目录自动创建。"""
        log_dir = Path(local_config.data_dir) / "logs"
        assert not log_dir.exists()
        setup_logging(local_config)
        assert log_dir.is_dir()

    def test_log_file_created(self, local_config: AppConfig) -> None:
        """日志文件在写入后存在。"""
        setup_logging(local_config)
        logger = logging.getLogger("test_file_creation")
        logger.info("测试日志写入")
        log_file = Path(local_config.data_dir) / "logs" / LOG_FILE_NAME
        assert log_file.exists()

    def test_log_level_from_config(self, cloud_config: AppConfig) -> None:
        """日志级别从配置读取。"""
        setup_logging(cloud_config)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_log_level_warning(self, docker_config: AppConfig) -> None:
        """日志级别 WARNING。"""
        setup_logging(docker_config)
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_rotating_handler_params(self, local_config: AppConfig) -> None:
        """RotatingFileHandler 参数正确（10MB，5 备份）。"""
        setup_logging(local_config)
        root = logging.getLogger()
        rotating_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(rotating_handlers) == 1
        handler = rotating_handlers[0]
        assert handler.maxBytes == MAX_BYTES
        assert handler.backupCount == BACKUP_COUNT

    def test_log_format_contains_required_fields(self, local_config: AppConfig) -> None:
        """日志格式包含时间戳、级别、模块名、消息。"""
        setup_logging(local_config)
        logger = logging.getLogger("test_format")
        logger.info("格式测试消息")
        log_file = Path(local_config.data_dir) / "logs" / LOG_FILE_NAME
        content = log_file.read_text(encoding="utf-8")
        # 检查格式：时间戳 [级别] 模块名 - 消息
        assert "[INFO]" in content
        assert "test_format" in content
        assert "格式测试消息" in content

    def test_no_duplicate_handlers_on_repeat_setup(self, local_config: AppConfig) -> None:
        """重复调用 setup_logging 不会产生重复 handler。"""
        setup_logging(local_config)
        setup_logging(local_config)
        root = logging.getLogger()
        rotating_count = sum(
            1 for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert rotating_count == 1

    def test_log_to_stdout_explicit(self, tmp_path: Path) -> None:
        """显式设置 log_to_stdout=True 时，Local 模式也输出到 stdout。"""
        config = AppConfig(
            runtime_env=RuntimeMode.LOCAL,
            data_dir=str(tmp_path),
            log_level="INFO",
            log_to_stdout=True,
        )
        setup_logging(config)
        root = logging.getLogger()
        stream_handlers = [
            h for h in root.handlers if type(h) is logging.StreamHandler
        ]
        assert len(stream_handlers) == 1


class TestGetLogger:
    """get_logger 函数测试。"""

    def test_returns_named_logger(self) -> None:
        """返回指定名称的 logger。"""
        logger = get_logger("my_module")
        assert logger.name == "my_module"
        assert isinstance(logger, logging.Logger)

    def test_same_name_returns_same_logger(self) -> None:
        """相同名称返回相同 logger 实例。"""
        logger1 = get_logger("shared")
        logger2 = get_logger("shared")
        assert logger1 is logger2

    def test_different_name_returns_different_logger(self) -> None:
        """不同名称返回不同 logger。"""
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")
        assert logger1 is not logger2

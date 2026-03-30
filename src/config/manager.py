"""配置管理器：单例模式，统一管理配置加载与访问。"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.config.loader import load_yaml_config
from src.config.models import (
    AppConfig,
    CloudConfig,
    DatabaseConfig,
    DataConfig,
    LLMConfig,
    NetworkConfig,
    PushConfig,
    RuntimeMode,
    SchedulerConfig,
)

logger = logging.getLogger(__name__)

# 分区名 -> (模型类, 环境变量前缀)
_SECTION_REGISTRY: dict[str, tuple[type, str]] = {
    "llm": (LLMConfig, "STOCK_ARM_LLM_"),
    "data": (DataConfig, "STOCK_ARM_DATA_"),
    "db": (DatabaseConfig, "STOCK_ARM_DB_"),
    "net": (NetworkConfig, "STOCK_ARM_NET_"),
    "scheduler": (SchedulerConfig, "STOCK_ARM_SCHEDULER_"),
    "cloud": (CloudConfig, "STOCK_ARM_"),  # STOCK_ARM_AUTH_*, STOCK_ARM_SSL_*, STOCK_ARM_BACKUP_*
    "push": (PushConfig, "STOCK_ARM_PUSH_"),
}

# 特殊映射: 环境变量名 -> (分区, 字段名)。处理 cloud 分区中前缀不统一的字段
_CLOUD_ENV_MAP: dict[str, str] = {
    "STOCK_ARM_AUTH_ENABLED": "auth_enabled",
    "STOCK_ARM_AUTH_USERNAME": "auth_username",
    "STOCK_ARM_AUTH_PASSWORD": "auth_password",
    "STOCK_ARM_SSL_CERT_PATH": "ssl_cert_path",
    "STOCK_ARM_SSL_KEY_PATH": "ssl_key_path",
    "STOCK_ARM_BACKUP_ENABLED": "backup_enabled",
    "STOCK_ARM_BACKUP_PATH": "backup_path",
    "STOCK_ARM_BACKUP_CRON": "backup_cron",
}

# 调度器分区的特殊环境变量映射（STOCK_ARM_SCHEDULE_* 和 STOCK_ARM_TRADING_*）
_SCHEDULER_ENV_MAP: dict[str, str] = {
    "STOCK_ARM_SCHEDULE_DAILY_ANALYSIS": "daily_analysis",
    "STOCK_ARM_SCHEDULE_DAILY_MACRO": "daily_macro",
    "STOCK_ARM_SCHEDULE_DAILY_BRIEFING": "daily_briefing",
    "STOCK_ARM_SCHEDULE_EARNINGS_SCAN": "earnings_scan",
    "STOCK_ARM_SCHEDULE_MONTHLY_REPORT": "monthly_report",
    "STOCK_ARM_TRADING_DAY_CHECK": "trading_day_check",
}


def _load_section_from_env(env_map: dict[str, str]) -> dict[str, Any]:
    """从环境变量加载特殊映射的配置字段。"""
    result: dict[str, Any] = {}
    for env_key, field_name in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            result[field_name] = val
    return result


def _build_section(
    section_name: str,
    model_cls: type[BaseModel],
    env_prefix: str,
    yaml_data: dict[str, Any],
) -> Any:
    """构建单个配置分区：合并 yaml 默认值和环境变量。"""
    # 1. 从 yaml 获取该分区的数据
    yaml_section = yaml_data.get(section_name, {})
    if not isinstance(yaml_section, dict):
        yaml_section = {}

    # 2. 从环境变量获取值（通过标准前缀）
    env_overrides: dict[str, Any] = {}
    for field_name in model_cls.model_fields:
        env_key = f"{env_prefix}{field_name.upper()}"
        val = os.environ.get(env_key)
        if val is not None:
            env_overrides[field_name] = val

    # 3. 处理特殊映射的环境变量
    if section_name == "cloud":
        env_overrides.update(_load_section_from_env(_CLOUD_ENV_MAP))
    elif section_name == "scheduler":
        env_overrides.update(_load_section_from_env(_SCHEDULER_ENV_MAP))

    # 4. 合并：env > yaml > 模型默认值
    merged = {**yaml_section, **env_overrides}

    return model_cls(**merged)


def _detect_runtime_mode() -> RuntimeMode:
    """检测当前运行时模式。

    检测逻辑：
    1. 环境变量 STOCK_ARM_RUNTIME_ENV 明确指定（非 auto）时直接使用
    2. 检查 /.dockerenv 文件判断是否在 Docker 中
    3. 检查 /proc/1/cgroup 中是否包含 docker/containerd
    4. 以上均不匹配则为 local
    """
    env_val = os.environ.get("STOCK_ARM_RUNTIME_ENV", "auto").lower()
    if env_val != "auto":
        try:
            return RuntimeMode(env_val)
        except ValueError:
            logger.warning(
                "环境变量 STOCK_ARM_RUNTIME_ENV 值 '%s' 无效，"
                "有效值为: auto, local, docker, cloud。将使用自动检测",
                env_val,
            )

    # Docker 检测
    if Path("/.dockerenv").exists():
        return RuntimeMode.DOCKER

    try:
        cgroup_content = Path("/proc/1/cgroup").read_text(encoding="utf-8")
        if "docker" in cgroup_content or "containerd" in cgroup_content:
            return RuntimeMode.DOCKER
    except (FileNotFoundError, PermissionError):
        pass

    return RuntimeMode.LOCAL


def _apply_runtime_defaults(config: AppConfig) -> AppConfig:
    """根据运行时模式调整默认配置。"""
    mode = config.runtime_env

    if mode in (RuntimeMode.CLOUD, RuntimeMode.DOCKER):
        # 云端/Docker 模式：绑定所有接口，日志输出到 stdout
        if config.net.bind_host == "127.0.0.1":
            config.net.bind_host = "0.0.0.0"
        config.log_to_stdout = True

    if mode == RuntimeMode.DOCKER and config.data_dir == "data":
        # Docker 模式：使用容器内标准路径
        config.data_dir = "/app/data"

    return config


def _load_config(**overrides: Any) -> AppConfig:
    """加载完整配置，按优先级合并所有数据源。"""
    # 加载 YAML
    yaml_data = load_yaml_config()

    # 构建各分区
    sections: dict[str, Any] = {}
    for section_name, (model_cls, env_prefix) in _SECTION_REGISTRY.items():
        sections[section_name] = _build_section(section_name, model_cls, env_prefix, yaml_data)

    # 顶层字段
    top_level: dict[str, Any] = {}
    top_fields = {
        "runtime_env": "STOCK_ARM_RUNTIME_ENV",
        "data_dir": "STOCK_ARM_DATA_DIR",
        "log_level": "STOCK_ARM_LOG_LEVEL",
        "log_to_stdout": "STOCK_ARM_LOG_TO_STDOUT",
        "bind_host": "STOCK_ARM_BIND_HOST",
        "port": "STOCK_ARM_PORT",
    }
    for field_name, env_key in top_fields.items():
        # 先从环境变量
        val = os.environ.get(env_key)
        if val is not None:
            top_level[field_name] = val
        # 再从 yaml 顶层
        elif field_name in yaml_data:
            top_level[field_name] = yaml_data[field_name]

    # 特殊处理: STOCK_ARM_BIND_HOST 和 STOCK_ARM_PORT 映射到 net 分区
    if "bind_host" in top_level:
        sections["net"].bind_host = top_level.pop("bind_host")
    if "port" in top_level:
        sections["net"].port = int(top_level.pop("port"))

    # 合并
    config_data = {**top_level, **sections, **overrides}
    return AppConfig(**config_data)


class ConfigManager:
    """配置管理器单例。

    使用方式：
        config = ConfigManager.get_config()
        llm_config = ConfigManager.get_section("llm")
        mode = ConfigManager.get_runtime_mode()
    """

    _instance: ConfigManager | None = None
    _lock: threading.Lock = threading.Lock()
    _config: AppConfig | None = None
    _runtime_mode: RuntimeMode | None = None

    def __new__(cls) -> ConfigManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, **overrides: Any) -> AppConfig:
        """初始化配置。应用启动时调用一次。

        Args:
            **overrides: 覆盖配置项（主要用于测试）

        Returns:
            加载并校验后的 AppConfig 对象
        """
        with cls._lock:
            try:
                config = _load_config(**overrides)
            except Exception as exc:
                raise ConfigLoadError(
                    f"配置加载失败: {exc}\n"
                    f"请检查环境变量、.env 文件和 config.yaml 的格式是否正确。\n"
                    f"参考 .env.example 了解各配置项的格式和默认值"
                ) from exc

            # 运行时模式检测
            detected_mode = _detect_runtime_mode()
            if config.runtime_env == RuntimeMode.AUTO:
                config.runtime_env = detected_mode
            cls._runtime_mode = config.runtime_env

            # 应用运行时模式默认值
            config = _apply_runtime_defaults(config)

            cls._config = config
            logger.info(
                "配置加载完成，运行模式: %s，数据目录: %s",
                config.runtime_env.value,
                config.data_dir,
            )
            return config

    @classmethod
    def get_config(cls) -> AppConfig:
        """获取完整配置对象。未初始化时自动初始化。"""
        if cls._config is None:
            cls.initialize()
        assert cls._config is not None
        return cls._config

    @classmethod
    def get_section(cls, section: str) -> Any:
        """获取指定分区的配置。

        Args:
            section: 分区名称（llm, data, db, net, scheduler, cloud, push）

        Returns:
            对应分区的配置对象

        Raises:
            ValueError: 分区名称无效
        """
        config = cls.get_config()
        valid_sections = {"llm", "data", "db", "net", "scheduler", "cloud", "push"}
        if section not in valid_sections:
            raise ValueError(
                f"无效的配置分区 '{section}'，有效分区: {', '.join(sorted(valid_sections))}"
            )
        return getattr(config, section)

    @classmethod
    def get_runtime_mode(cls) -> RuntimeMode:
        """获取当前运行时模式。"""
        if cls._runtime_mode is None:
            cls.get_config()
        assert cls._runtime_mode is not None
        return cls._runtime_mode

    @classmethod
    def reset(cls) -> None:
        """重置配置（仅用于测试）。"""
        with cls._lock:
            cls._config = None
            cls._runtime_mode = None
            cls._instance = None


class ConfigLoadError(Exception):
    """配置加载异常。"""

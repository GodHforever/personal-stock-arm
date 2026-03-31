"""配置数据模型：定义所有配置分区的 Pydantic 模型。"""

from __future__ import annotations

import enum

from pydantic import BaseModel, SecretStr, field_validator


class RuntimeMode(enum.StrEnum):
    """运行时模式枚举。"""

    AUTO = "auto"
    LOCAL = "local"
    DOCKER = "docker"
    CLOUD = "cloud"


class LLMConfig(BaseModel):
    """LLM 相关配置。"""

    api_key: SecretStr = SecretStr("")
    primary_model: str = "deepseek-chat"
    fast_model: str = "glm-4-flash"
    fallback_chain: list[str] = ["qwen-plus", "gpt-4o-mini"]
    daily_token_limit: int = 500000

    @field_validator("daily_token_limit")
    @classmethod
    def _validate_token_limit(cls, v: int) -> int:
        if v < 0:
            raise ValueError("每日 Token 预算不能为负数")
        return v


class DataConfig(BaseModel):
    """数据源配置。"""

    tushare_token: SecretStr = SecretStr("")
    connect_timeout: int = 5
    read_timeout: int = 30
    max_retries: int = 3

    @field_validator("connect_timeout", "read_timeout")
    @classmethod
    def _validate_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("超时时间必须为正整数")
        return v

    @field_validator("max_retries")
    @classmethod
    def _validate_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("最大重试次数不能为负数")
        return v


class DatabaseConfig(BaseModel):
    """数据库配置。"""

    url: str = "sqlite+aiosqlite:///data/stock_arm.db"
    echo: bool = False


class NetworkConfig(BaseModel):
    """网络配置。"""

    proxy: str = ""
    bind_host: str = "127.0.0.1"
    port: int = 8000
    ssl_verify: bool = True

    @field_validator("port")
    @classmethod
    def _validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("端口号必须在 1-65535 之间")
        return v


class SchedulerConfig(BaseModel):
    """调度器配置。"""

    enabled: bool = True
    daily_analysis: str = "18:00"
    daily_macro: str = "18:30"
    daily_briefing: str = "19:00"
    earnings_scan: str = "20:00"
    monthly_report: str = "09:00"
    trading_day_check: bool = True
    data_retention_days: int = 90
    cleanup_cron: str = "0 3 1 * *"

    @field_validator("data_retention_days")
    @classmethod
    def _validate_retention(cls, v: int) -> int:
        if v < 1:
            raise ValueError("数据保留天数必须至少为 1")
        return v


class CloudConfig(BaseModel):
    """云端部署配置。"""

    auth_enabled: bool = False
    auth_username: str = "admin"
    auth_password: SecretStr = SecretStr("")
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    backup_enabled: bool = False
    backup_path: str = ""
    backup_cron: str = "0 3 * * *"


class PushConfig(BaseModel):
    """推送通知配置。"""

    wechat_webhook_url: SecretStr = SecretStr("")
    feishu_webhook_url: SecretStr = SecretStr("")
    email_smtp_host: str = ""
    email_smtp_port: int = 465
    email_sender: str = ""
    email_password: SecretStr = SecretStr("")
    email_receivers: str = ""
    custom_webhook_urls: str = ""
    schedule_time: str = "18:00"
    silent_start: str = "22:00"
    silent_end: str = "08:00"
    event_push_daily_limit: int = 10

    @field_validator("event_push_daily_limit")
    @classmethod
    def _validate_daily_limit(cls, v: int) -> int:
        if v < 0:
            raise ValueError("事件推送每日限额不能为负数")
        return v


class AppConfig(BaseModel):
    """应用全局配置，聚合所有分区。"""

    runtime_env: RuntimeMode = RuntimeMode.AUTO
    data_dir: str = "data"
    log_level: str = "INFO"
    log_to_stdout: bool = False

    llm: LLMConfig = LLMConfig()
    data: DataConfig = DataConfig()
    db: DatabaseConfig = DatabaseConfig()
    net: NetworkConfig = NetworkConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    cloud: CloudConfig = CloudConfig()
    push: PushConfig = PushConfig()

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"日志级别必须为 {allowed} 之一，收到: {v}")
        return upper

    @field_validator("data_dir")
    @classmethod
    def _validate_data_dir(cls, v: str) -> str:
        if not v:
            raise ValueError("数据目录不能为空")
        return v

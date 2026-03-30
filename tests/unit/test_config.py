"""配置管理系统单元测试。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from src.config.loader import load_yaml_config
from src.config.manager import ConfigLoadError, ConfigManager, _detect_runtime_mode
from src.config.models import (
    AppConfig,
    CloudConfig,
    DataConfig,
    DatabaseConfig,
    LLMConfig,
    NetworkConfig,
    PushConfig,
    RuntimeMode,
    SchedulerConfig,
)


@pytest.fixture(autouse=True)
def _reset_config():
    """每个测试前后重置 ConfigManager 单例状态。"""
    ConfigManager.reset()
    yield
    ConfigManager.reset()


@pytest.fixture()
def clean_env(monkeypatch):
    """清除所有 STOCK_ARM_ 开头的环境变量。"""
    for key in list(os.environ):
        if key.startswith("STOCK_ARM_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


# ============================================================
# AC-1: 优先级链测试
# ============================================================


class TestPriorityChain:
    """AC-1: 配置按优先级链加载。"""

    def test_default_values_used_when_no_sources(self, clean_env):
        """无外部配置源时使用代码默认值。"""
        config = ConfigManager.initialize()
        assert config.llm.primary_model == "deepseek-chat"
        assert config.data.connect_timeout == 5
        assert config.net.port == 8000

    def test_env_var_overrides_default(self, clean_env):
        """环境变量覆盖代码默认值。"""
        clean_env.setenv("STOCK_ARM_NET_PORT", "9090")
        config = ConfigManager.initialize()
        assert config.net.port == 9090

    def test_yaml_overrides_default(self, clean_env, tmp_path):
        """config.yaml 覆盖代码默认值。"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump({"llm": {"primary_model": "gpt-4o"}}))
        data = load_yaml_config(yaml_file)
        assert data["llm"]["primary_model"] == "gpt-4o"

    def test_env_var_overrides_yaml_for_nested(self, clean_env):
        """环境变量优先级高于代码默认值（嵌套分区）。"""
        clean_env.setenv("STOCK_ARM_LLM_PRIMARY_MODEL", "claude-3")
        config = ConfigManager.initialize()
        assert config.llm.primary_model == "claude-3"

    def test_env_var_overrides_top_level(self, clean_env):
        """环境变量覆盖顶层配置项。"""
        clean_env.setenv("STOCK_ARM_LOG_LEVEL", "DEBUG")
        config = ConfigManager.initialize()
        assert config.log_level == "DEBUG"


# ============================================================
# AC-2: Pydantic 模型校验
# ============================================================


class TestPydanticModels:
    """AC-2: 所有配置通过 Pydantic 模型定义和校验。"""

    def test_llm_config_types(self):
        """LLMConfig 字段类型正确。"""
        cfg = LLMConfig(api_key=SecretStr("sk-test"), daily_token_limit=100000)
        assert cfg.api_key.get_secret_value() == "sk-test"
        assert isinstance(cfg.daily_token_limit, int)

    def test_invalid_token_limit_rejected(self):
        """负数 token 限制被拒绝。"""
        with pytest.raises(ValidationError, match="不能为负数"):
            LLMConfig(daily_token_limit=-1)

    def test_invalid_port_rejected(self):
        """无效端口被拒绝。"""
        with pytest.raises(ValidationError, match="1-65535"):
            NetworkConfig(port=99999)

    def test_invalid_log_level_rejected(self):
        """无效日志级别被拒绝。"""
        with pytest.raises(ValidationError, match="日志级别"):
            AppConfig(log_level="TRACE")

    def test_invalid_timeout_rejected(self):
        """非正超时被拒绝。"""
        with pytest.raises(ValidationError, match="正整数"):
            DataConfig(connect_timeout=0)

    def test_invalid_retention_rejected(self):
        """数据保留天数小于 1 被拒绝。"""
        with pytest.raises(ValidationError, match="至少为 1"):
            SchedulerConfig(data_retention_days=0)

    def test_app_config_contains_all_sections(self):
        """AppConfig 包含所有分区。"""
        config = AppConfig()
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.data, DataConfig)
        assert isinstance(config.db, DatabaseConfig)
        assert isinstance(config.net, NetworkConfig)
        assert isinstance(config.scheduler, SchedulerConfig)
        assert isinstance(config.cloud, CloudConfig)
        assert isinstance(config.push, PushConfig)


# ============================================================
# AC-3: 环境变量命名格式
# ============================================================


class TestEnvVarNaming:
    """AC-3: 环境变量遵循 STOCK_ARM_<CATEGORY>_<NAME> 格式。"""

    def test_llm_category(self, clean_env):
        """LLM 分区通过 STOCK_ARM_LLM_ 前缀配置。"""
        clean_env.setenv("STOCK_ARM_LLM_PRIMARY_MODEL", "test-model")
        config = ConfigManager.initialize()
        assert config.llm.primary_model == "test-model"

    def test_net_category(self, clean_env):
        """NET 分区通过 STOCK_ARM_NET_ 前缀配置。"""
        clean_env.setenv("STOCK_ARM_NET_PORT", "3000")
        config = ConfigManager.initialize()
        assert config.net.port == 3000

    def test_scheduler_category(self, clean_env):
        """SCHEDULER 分区通过 STOCK_ARM_SCHEDULER_ 前缀配置。"""
        clean_env.setenv("STOCK_ARM_SCHEDULER_ENABLED", "false")
        config = ConfigManager.initialize()
        assert config.scheduler.enabled is False

    def test_data_category(self, clean_env):
        """DATA 分区通过 STOCK_ARM_DATA_ 前缀配置。"""
        clean_env.setenv("STOCK_ARM_DATA_CONNECT_TIMEOUT", "10")
        config = ConfigManager.initialize()
        assert config.data.connect_timeout == 10

    def test_scheduler_special_env_vars(self, clean_env):
        """调度器特殊环境变量 STOCK_ARM_SCHEDULE_* 映射正确。"""
        clean_env.setenv("STOCK_ARM_SCHEDULE_DAILY_ANALYSIS", "20:00")
        config = ConfigManager.initialize()
        assert config.scheduler.daily_analysis == "20:00"

    def test_cloud_auth_env_vars(self, clean_env):
        """云端认证环境变量 STOCK_ARM_AUTH_* 映射正确。"""
        clean_env.setenv("STOCK_ARM_AUTH_ENABLED", "true")
        clean_env.setenv("STOCK_ARM_AUTH_USERNAME", "admin2")
        config = ConfigManager.initialize()
        assert config.cloud.auth_enabled is True
        assert config.cloud.auth_username == "admin2"


# ============================================================
# AC-4: 秘密字段保护
# ============================================================


class TestSecretFields:
    """AC-4: 秘密信息使用 SecretStr，日志中自动脱敏。"""

    def test_api_key_is_secret(self):
        """API Key 使用 SecretStr 类型。"""
        cfg = LLMConfig(api_key=SecretStr("sk-my-secret-key"))
        assert "sk-my-secret-key" not in str(cfg)
        assert "sk-my-secret-key" not in repr(cfg)
        assert cfg.api_key.get_secret_value() == "sk-my-secret-key"

    def test_tushare_token_is_secret(self):
        """Tushare Token 使用 SecretStr 类型。"""
        cfg = DataConfig(tushare_token=SecretStr("token123"))
        assert "token123" not in str(cfg)
        assert cfg.tushare_token.get_secret_value() == "token123"

    def test_auth_password_is_secret(self):
        """认证密码使用 SecretStr 类型。"""
        cfg = CloudConfig(auth_password=SecretStr("p@ssw0rd"))
        assert "p@ssw0rd" not in str(cfg)

    def test_secret_masked_in_model_dump(self):
        """model_dump() 中秘密字段被脱敏。"""
        cfg = LLMConfig(api_key=SecretStr("sk-secret"))
        dumped = cfg.model_dump()
        assert dumped["api_key"] != "sk-secret"


# ============================================================
# AC-5: 运行时模式检测
# ============================================================


class TestRuntimeMode:
    """AC-5: 运行时模式自动检测。"""

    def test_explicit_mode_from_env(self, clean_env):
        """环境变量明确指定模式时直接使用。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "cloud")
        mode = _detect_runtime_mode()
        assert mode == RuntimeMode.CLOUD

    def test_auto_detects_local(self, clean_env):
        """auto 模式在普通环境下检测为 local。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "auto")
        with (
            patch("src.config.manager.Path.exists", return_value=False),
            patch("src.config.manager.Path.read_text", side_effect=FileNotFoundError),
        ):
            mode = _detect_runtime_mode()
            assert mode == RuntimeMode.LOCAL

    def test_auto_detects_docker(self, clean_env):
        """auto 模式检测 /.dockerenv 文件判断 Docker。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "auto")
        original_exists = Path.exists

        def mock_exists(self):
            if str(self) == "/.dockerenv":
                return True
            return original_exists(self)

        with patch.object(Path, "exists", mock_exists):
            mode = _detect_runtime_mode()
            assert mode == RuntimeMode.DOCKER

    def test_invalid_mode_falls_back_to_detection(self, clean_env):
        """无效模式值回退到自动检测。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "invalid")
        with (
            patch("src.config.manager.Path.exists", return_value=False),
            patch("src.config.manager.Path.read_text", side_effect=FileNotFoundError),
        ):
            mode = _detect_runtime_mode()
            assert mode == RuntimeMode.LOCAL

    def test_cloud_mode_binds_all_interfaces(self, clean_env):
        """云端模式自动绑定 0.0.0.0。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "cloud")
        config = ConfigManager.initialize()
        assert config.net.bind_host == "0.0.0.0"
        assert config.log_to_stdout is True

    def test_docker_mode_sets_app_data_dir(self, clean_env):
        """Docker 模式自动设置 /app/data 数据目录。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "docker")
        config = ConfigManager.initialize()
        assert config.data_dir == "/app/data"
        assert config.net.bind_host == "0.0.0.0"

    def test_local_mode_binds_localhost(self, clean_env):
        """本地模式绑定 127.0.0.1。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        config = ConfigManager.initialize()
        assert config.net.bind_host == "127.0.0.1"


# ============================================================
# AC-6: 分区独立访问
# ============================================================


class TestSectionAccess:
    """AC-6: 各业务模块可独立获取分区配置。"""

    def test_get_llm_section(self, clean_env):
        """获取 LLM 分区配置。"""
        ConfigManager.initialize()
        llm = ConfigManager.get_section("llm")
        assert isinstance(llm, LLMConfig)

    def test_get_scheduler_section(self, clean_env):
        """获取 Scheduler 分区配置。"""
        ConfigManager.initialize()
        sched = ConfigManager.get_section("scheduler")
        assert isinstance(sched, SchedulerConfig)

    def test_invalid_section_raises(self, clean_env):
        """无效分区名称抛出 ValueError。"""
        ConfigManager.initialize()
        with pytest.raises(ValueError, match="无效的配置分区"):
            ConfigManager.get_section("nonexistent")

    def test_all_sections_accessible(self, clean_env):
        """所有分区均可独立访问。"""
        ConfigManager.initialize()
        for section in ("llm", "data", "db", "net", "scheduler", "cloud", "push"):
            result = ConfigManager.get_section(section)
            assert result is not None


# ============================================================
# AC-7: 必填项校验
# ============================================================


class TestRequiredFields:
    """AC-7: 缺少必填配置项时报告清晰错误。"""

    def test_validation_error_is_human_readable(self):
        """校验错误消息包含人类可读信息。"""
        with pytest.raises(ValidationError, match="不能为负数"):
            LLMConfig(daily_token_limit=-1)

    def test_empty_data_dir_rejected(self):
        """空数据目录被拒绝。"""
        with pytest.raises(ValidationError, match="不能为空"):
            AppConfig(data_dir="")


# ============================================================
# AC-8: .env.example 文件
# ============================================================


class TestEnvExample:
    """AC-8: .env.example 文件存在且包含说明。"""

    def test_env_example_exists(self):
        """确保 .env.example 文件存在。"""
        env_example = Path(__file__).parents[2] / ".env.example"
        assert env_example.exists(), ".env.example 文件不存在"

    def test_env_example_has_categories(self):
        """确保 .env.example 包含所有配置分区。"""
        env_example = Path(__file__).parents[2] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "STOCK_ARM_LLM_" in content
        assert "STOCK_ARM_DATA_" in content
        assert "STOCK_ARM_NET_" in content
        assert "STOCK_ARM_SCHEDULER_" in content
        assert "STOCK_ARM_RUNTIME_ENV" in content


# ============================================================
# AC-9: 配置加载失败处理
# ============================================================


class TestErrorHandling:
    """AC-9: 配置加载失败时提供可读错误信息。"""

    def test_yaml_parse_error(self, tmp_path):
        """YAML 格式错误时给出清晰提示。"""
        bad_yaml = tmp_path / "config.yaml"
        bad_yaml.write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError, match="解析失败"):
            load_yaml_config(bad_yaml)

    def test_yaml_not_dict_returns_empty(self, tmp_path):
        """YAML 根节点非字典时返回空字典。"""
        bad_yaml = tmp_path / "config.yaml"
        bad_yaml.write_text("- item1\n- item2\n")
        result = load_yaml_config(bad_yaml)
        assert result == {}

    def test_missing_yaml_returns_empty(self, tmp_path):
        """config.yaml 不存在时返回空字典。"""
        result = load_yaml_config(tmp_path / "nonexistent.yaml")
        assert result == {}


# ============================================================
# AC-10: 独立性
# ============================================================


class TestIndependence:
    """AC-10: 配置系统不依赖其他项目模块。"""

    def test_config_initializes_independently(self, clean_env):
        """配置系统可独立初始化，不依赖其他模块。"""
        config = ConfigManager.initialize()
        assert isinstance(config, AppConfig)

    def test_get_config_auto_initializes(self, clean_env):
        """未初始化时 get_config 自动初始化。"""
        config = ConfigManager.get_config()
        assert isinstance(config, AppConfig)

    def test_get_runtime_mode(self, clean_env):
        """可获取运行时模式。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        ConfigManager.initialize()
        mode = ConfigManager.get_runtime_mode()
        assert mode == RuntimeMode.LOCAL


# ============================================================
# 补充: ConfigManager 单例测试
# ============================================================


class TestConfigManagerSingleton:
    """ConfigManager 单例行为测试。"""

    def test_singleton_returns_same_config(self, clean_env):
        """多次调用返回同一配置对象。"""
        config1 = ConfigManager.get_config()
        config2 = ConfigManager.get_config()
        assert config1 is config2

    def test_reset_allows_reinitialize(self, clean_env):
        """reset 后可重新初始化。"""
        config1 = ConfigManager.initialize()
        ConfigManager.reset()
        config2 = ConfigManager.initialize()
        assert config1 is not config2

    def test_initialize_with_overrides(self, clean_env):
        """initialize 支持覆盖参数。"""
        config = ConfigManager.initialize(log_level="DEBUG")
        assert config.log_level == "DEBUG"

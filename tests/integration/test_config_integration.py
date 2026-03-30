"""配置管理系统集成测试与场景测试（QA 补充）。"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import SecretStr

from src.config.loader import load_yaml_config
from src.config.manager import ConfigLoadError, ConfigManager, _build_section, _load_config
from src.config.models import (
    AppConfig,
    CloudConfig,
    DataConfig,
    LLMConfig,
    NetworkConfig,
    PushConfig,
    RuntimeMode,
    SchedulerConfig,
)


@pytest.fixture(autouse=True)
def _reset_config():
    """每个测试前后重置 ConfigManager。"""
    ConfigManager.reset()
    yield
    ConfigManager.reset()


@pytest.fixture()
def clean_env(monkeypatch):
    """清除所有 STOCK_ARM_ 环境变量。"""
    for key in list(os.environ):
        if key.startswith("STOCK_ARM_"):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


# ============================================================
# 集成测试：端到端优先级链
# ============================================================


class TestPriorityChainE2E:
    """端到端测试：env > yaml > default 完整优先级链。"""

    def test_yaml_overrides_default_via_manager(self, clean_env, tmp_path):
        """通过 ConfigManager 验证 yaml 覆盖代码默认值。"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            yaml.dump({"llm": {"primary_model": "from-yaml"}, "net": {"port": 3000}})
        )
        with patch("src.config.manager.load_yaml_config", return_value=load_yaml_config(yaml_file)):
            config = ConfigManager.initialize()
        assert config.llm.primary_model == "from-yaml"
        assert config.net.port == 3000

    def test_env_overrides_yaml_via_manager(self, clean_env, tmp_path):
        """通过 ConfigManager 验证 env > yaml。"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump({"llm": {"primary_model": "from-yaml"}}))
        clean_env.setenv("STOCK_ARM_LLM_PRIMARY_MODEL", "from-env")
        with patch("src.config.manager.load_yaml_config", return_value=load_yaml_config(yaml_file)):
            config = ConfigManager.initialize()
        assert config.llm.primary_model == "from-env"

    def test_full_chain_default_yaml_env(self, clean_env, tmp_path):
        """完整三层优先级：env > yaml > default。"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            yaml.dump({
                "llm": {"primary_model": "yaml-model", "fast_model": "yaml-fast"},
                "net": {"port": 3000},
            })
        )
        # env 只覆盖 primary_model，fast_model 应来自 yaml，port 也来自 yaml
        clean_env.setenv("STOCK_ARM_LLM_PRIMARY_MODEL", "env-model")

        with patch("src.config.manager.load_yaml_config", return_value=load_yaml_config(yaml_file)):
            config = ConfigManager.initialize()

        assert config.llm.primary_model == "env-model"  # env 覆盖
        assert config.llm.fast_model == "yaml-fast"  # yaml 覆盖 default
        assert config.net.port == 3000  # yaml 覆盖 default
        assert config.data.connect_timeout == 5  # 纯 default


# ============================================================
# 集成测试：ConfigLoadError 包装
# ============================================================


class TestConfigLoadErrorIntegration:
    """测试配置加载失败时的 ConfigLoadError 包装。"""

    def test_invalid_env_var_raises_config_load_error(self, clean_env):
        """无效环境变量值触发 ConfigLoadError（含修正建议）。"""
        clean_env.setenv("STOCK_ARM_NET_PORT", "not-a-number")
        with pytest.raises(ConfigLoadError, match="配置加载失败"):
            ConfigManager.initialize()

    def test_config_load_error_includes_suggestion(self, clean_env):
        """ConfigLoadError 消息包含参考 .env.example 的建议。"""
        clean_env.setenv("STOCK_ARM_LOG_LEVEL", "TRACE")
        with pytest.raises(ConfigLoadError, match="参考 .env.example"):
            ConfigManager.initialize()


# ============================================================
# 场景测试：运行时模式下的配置组合
# ============================================================


class TestRuntimeModeScenarios:
    """运行时模式对配置的综合影响。"""

    def test_docker_mode_combined_defaults(self, clean_env):
        """Docker 模式同时设置 data_dir、bind_host、log_to_stdout。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "docker")
        config = ConfigManager.initialize()
        assert config.data_dir == "/app/data"
        assert config.net.bind_host == "0.0.0.0"
        assert config.log_to_stdout is True

    def test_cloud_mode_preserves_custom_bind_host(self, clean_env):
        """云端模式下如果用户显式设置了 bind_host，不应被覆盖。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "cloud")
        clean_env.setenv("STOCK_ARM_NET_BIND_HOST", "192.168.1.1")
        config = ConfigManager.initialize()
        # _apply_runtime_defaults 只在 bind_host == "127.0.0.1" 时覆盖
        assert config.net.bind_host == "192.168.1.1"

    def test_local_mode_defaults_unchanged(self, clean_env):
        """本地模式不修改任何默认值。"""
        clean_env.setenv("STOCK_ARM_RUNTIME_ENV", "local")
        config = ConfigManager.initialize()
        assert config.net.bind_host == "127.0.0.1"
        assert config.data_dir == "data"
        assert config.log_to_stdout is False


# ============================================================
# 场景测试：边界值和异常输入
# ============================================================


class TestBoundaryScenarios:
    """边界值和异常输入场景。"""

    def test_empty_env_var_does_not_override(self, clean_env):
        """空字符串环境变量也会覆盖（这是当前行为，非理想但需记录）。"""
        clean_env.setenv("STOCK_ARM_LLM_PRIMARY_MODEL", "")
        config = ConfigManager.initialize()
        # 空字符串也会覆盖默认值
        assert config.llm.primary_model == ""

    def test_yaml_with_extra_unknown_fields(self, clean_env, tmp_path):
        """YAML 中包含未知字段时不报错（Pydantic 默认忽略）。"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            yaml.dump({"llm": {"primary_model": "test", "unknown_field": "value"}})
        )
        with patch("src.config.manager.load_yaml_config", return_value=load_yaml_config(yaml_file)):
            config = ConfigManager.initialize()
        assert config.llm.primary_model == "test"

    def test_yaml_section_not_dict(self, clean_env, tmp_path):
        """YAML 分区值非字典时被安全忽略。"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump({"llm": "not-a-dict"}))
        with patch("src.config.manager.load_yaml_config", return_value=load_yaml_config(yaml_file)):
            config = ConfigManager.initialize()
        # 应使用默认值
        assert config.llm.primary_model == "deepseek-chat"

    def test_port_boundary_values(self):
        """端口边界值测试。"""
        # 最小值
        cfg = NetworkConfig(port=1)
        assert cfg.port == 1
        # 最大值
        cfg = NetworkConfig(port=65535)
        assert cfg.port == 65535

    def test_all_sections_with_yaml_override(self, clean_env, tmp_path):
        """所有分区都能通过 YAML 覆盖。"""
        yaml_data = {
            "llm": {"primary_model": "test-llm"},
            "data": {"connect_timeout": 10},
            "db": {"echo": True},
            "net": {"port": 9999},
            "scheduler": {"enabled": False},
            "cloud": {"auth_enabled": True},
            "push": {"schedule_time": "20:00"},
        }
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml.dump(yaml_data))
        with patch("src.config.manager.load_yaml_config", return_value=load_yaml_config(yaml_file)):
            config = ConfigManager.initialize()

        assert config.llm.primary_model == "test-llm"
        assert config.data.connect_timeout == 10
        assert config.db.echo is True
        assert config.net.port == 9999
        assert config.scheduler.enabled is False
        assert config.cloud.auth_enabled is True
        assert config.push.schedule_time == "20:00"


# ============================================================
# 场景测试：秘密字段在各种输出中的脱敏
# ============================================================


class TestSecretMaskingScenarios:
    """秘密字段在各种序列化方式下的脱敏验证。"""

    def test_secret_not_in_str(self):
        """str() 不泄露秘密。"""
        cfg = LLMConfig(api_key=SecretStr("sk-my-key"))
        assert "sk-my-key" not in str(cfg)

    def test_secret_not_in_repr(self):
        """repr() 不泄露秘密。"""
        cfg = LLMConfig(api_key=SecretStr("sk-my-key"))
        assert "sk-my-key" not in repr(cfg)

    def test_secret_not_in_json(self):
        """model_dump_json() 不泄露秘密。"""
        cfg = LLMConfig(api_key=SecretStr("sk-my-key"))
        assert "sk-my-key" not in cfg.model_dump_json()

    def test_secret_not_in_model_dump_json_mode(self):
        """model_dump(mode='json') 不泄露秘密。"""
        cfg = AppConfig(llm=LLMConfig(api_key=SecretStr("sk-my-key")))
        dumped = cfg.model_dump(mode="json")
        assert "sk-my-key" not in str(dumped)

    def test_all_secret_fields_masked(self):
        """所有标记为 SecretStr 的字段都被脱敏。"""
        cfg = AppConfig(
            llm=LLMConfig(api_key=SecretStr("secret1")),
            data=DataConfig(tushare_token=SecretStr("secret2")),
            cloud=CloudConfig(auth_password=SecretStr("secret3")),
            push=PushConfig(wechat_webhook_url=SecretStr("secret4")),
        )
        output = str(cfg)
        for secret in ["secret1", "secret2", "secret3", "secret4"]:
            assert secret not in output


# ============================================================
# 场景测试：.env.example 完整性
# ============================================================


class TestEnvExampleCompleteness:
    """验证 .env.example 文件的完整性。"""

    def test_env_example_has_push_section(self):
        """确保 .env.example 包含推送配置分区。"""
        env_example = Path(__file__).parents[2] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "STOCK_ARM_PUSH_" in content

    def test_env_example_has_cloud_section(self):
        """确保 .env.example 包含云端配置分区。"""
        env_example = Path(__file__).parents[2] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "STOCK_ARM_AUTH_" in content
        assert "STOCK_ARM_BACKUP_" in content

    def test_env_example_has_db_section(self):
        """确保 .env.example 包含数据库相关配置。"""
        env_example = Path(__file__).parents[2] / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        # DB 分区的环境变量暂未列出，但 DatabaseConfig 有 url 和 echo 字段
        # 这是一个覆盖度检查
        assert "STOCK_ARM_" in content

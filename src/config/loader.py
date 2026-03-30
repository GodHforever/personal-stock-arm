"""YAML 配置文件加载器。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 默认 YAML 配置文件路径
DEFAULT_YAML_PATH = Path("config/config.yaml")


def load_yaml_config(yaml_path: Path | None = None) -> dict[str, Any]:
    """加载 YAML 配置文件。

    Args:
        yaml_path: YAML 文件路径，默认为 config/config.yaml

    Returns:
        解析后的配置字典，文件不存在时返回空字典
    """
    path = yaml_path or DEFAULT_YAML_PATH

    if not path.exists():
        logger.debug("配置文件 %s 不存在，使用默认值", path)
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"配置文件 {path} 解析失败: {exc}\n"
            f"请检查 YAML 格式是否正确，可使用在线 YAML 校验工具验证"
        ) from exc

    if not isinstance(raw, dict):
        logger.warning(
            "配置文件 %s 格式无效：根节点应为字典，实际为 %s",
            path,
            type(raw).__name__,
        )
        return {}

    logger.debug("已加载配置文件: %s", path)
    return raw

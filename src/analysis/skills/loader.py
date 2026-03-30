"""YAML 策略加载器：解析 skills/*.yaml 策略定义文件。"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.log import get_logger

logger = get_logger(__name__)


class TriggerDefinition(BaseModel):
    """策略触发条件。"""

    conditions: list[str] = Field(default_factory=list)


class FieldDefinition(BaseModel):
    """输入/输出字段定义。"""

    name: str
    type: str
    required: bool = False


class IODefinition(BaseModel):
    """输入或输出定义。"""

    schema_name: str = Field(default="", alias="schema")
    fields: list[FieldDefinition] = Field(default_factory=list)


class StrategyDefinition(BaseModel):
    """YAML 策略定义的结构化表示。"""

    name: str
    description: str = ""
    version: str = "1.0"
    category: str = ""
    trigger: TriggerDefinition = Field(default_factory=TriggerDefinition)
    input: IODefinition = Field(default_factory=IODefinition)
    output: IODefinition = Field(default_factory=IODefinition)
    implementation: str = ""


def load_strategy(path: Path) -> StrategyDefinition:
    """从 YAML 文件加载策略定义。

    Args:
        path: 策略 YAML 文件路径

    Returns:
        解析后的策略定义对象

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: YAML 格式不合法或缺少必需字段
    """
    if not path.exists():
        raise FileNotFoundError(f"策略文件不存在: {path}")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None or not isinstance(data, dict):
        raise ValueError(f"策略文件格式不合法，应为 YAML 字典: {path}")

    if "name" not in data:
        raise ValueError(f"策略文件缺少必需字段 'name': {path}")

    logger.info("已加载策略: %s (v%s)", data.get("name"), data.get("version", "未知"))
    return StrategyDefinition(**data)

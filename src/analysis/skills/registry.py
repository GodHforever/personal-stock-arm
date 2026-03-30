"""技能注册表：从 skills/registry.yaml 加载和查询已评估的外部技能。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from src.log import get_logger

logger = get_logger(__name__)

# 有效的技能层级和状态值
SkillTier = Literal["direct-use", "reference", "ignore"]
SkillStatus = Literal["planned", "implemented", "deprecated", "reference-only"]


class SkillEntry(BaseModel):
    """注册表中的单条技能记录。"""

    name: str
    source: str
    category: str
    tier: SkillTier
    evaluated: str
    decision: str
    new_deps: list[str] = Field(default_factory=list)
    adapter: str | None = None
    status: SkillStatus = "planned"
    notes: str = ""


class SkillRegistry:
    """技能注册表管理器。

    从 skills/registry.yaml 加载已评估的技能列表，
    支持按分类和名称查询。
    """

    def __init__(self, registry_path: Path | None = None) -> None:
        """初始化注册表。

        Args:
            registry_path: registry.yaml 文件路径，默认为项目根目录下的 skills/registry.yaml
        """
        if registry_path is None:
            registry_path = Path("skills/registry.yaml")
        self._path = registry_path
        self._skills: list[SkillEntry] = []

    @property
    def skills(self) -> list[SkillEntry]:
        """已加载的全部技能列表。"""
        return list(self._skills)

    def load(self) -> None:
        """从 YAML 文件加载技能注册表。

        Raises:
            FileNotFoundError: registry.yaml 文件不存在
            ValueError: YAML 格式不合法
        """
        if not self._path.exists():
            raise FileNotFoundError(f"技能注册表文件不存在: {self._path}")

        with open(self._path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None or not isinstance(data, dict):
            raise ValueError(f"注册表格式不合法，应为 YAML 字典: {self._path}")

        raw_skills = data.get("skills", [])
        if not isinstance(raw_skills, list):
            raise ValueError(f"注册表 skills 字段应为列表: {self._path}")

        self._skills = []
        for item in raw_skills:
            if not isinstance(item, dict):
                logger.warning("跳过非字典类型的技能条目: %s", item)
                continue
            try:
                entry = SkillEntry(**item)
                self._skills.append(entry)
            except Exception as e:
                logger.warning("跳过无法解析的技能条目 %s: %s", item.get("name", "未知"), e)

        logger.info("已加载 %d 个技能条目", len(self._skills))

    def get_skills(self, category: str) -> list[SkillEntry]:
        """按分类获取技能列表。

        Args:
            category: 技能分类名称

        Returns:
            匹配分类的技能列表
        """
        return [s for s in self._skills if s.category == category]

    def get_skill(self, name: str) -> SkillEntry | None:
        """按名称获取单个技能。

        Args:
            name: 技能名称

        Returns:
            匹配的技能条目，未找到返回 None
        """
        for s in self._skills:
            if s.name == name:
                return s
        return None

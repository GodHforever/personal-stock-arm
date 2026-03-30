"""Skills 适配器层：提供外部技能集成框架、技能注册表和策略加载器。"""

from __future__ import annotations

from src.analysis.skills.base import BaseSkillAdapter
from src.analysis.skills.loader import StrategyDefinition, load_strategy
from src.analysis.skills.registry import SkillEntry, SkillRegistry

__all__ = [
    "BaseSkillAdapter",
    "SkillEntry",
    "SkillRegistry",
    "StrategyDefinition",
    "load_strategy",
]

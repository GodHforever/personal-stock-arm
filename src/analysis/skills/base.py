"""技能适配器抽象基类。

所有外部技能集成必须继承 BaseSkillAdapter 并实现全部抽象方法。
适配器代码不得超过 200 行。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class BaseSkillAdapter(ABC):
    """外部技能统一适配接口。

    每个适配器封装一个外部技能/工具的调用逻辑，
    提供类型安全的输入输出和健康检查能力。
    """

    @property
    @abstractmethod
    def skill_name(self) -> str:
        """技能名称。"""

    @property
    @abstractmethod
    def skill_source(self) -> str:
        """技能来源（URL、包名等）。"""

    @abstractmethod
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """执行技能。

        Args:
            input_data: 类型化的输入数据

        Returns:
            类型化的输出结果
        """

    @abstractmethod
    def health_check(self) -> bool:
        """检查技能依赖是否可用。

        Returns:
            True 表示技能可正常使用
        """

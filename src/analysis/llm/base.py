"""LLM 基础抽象：BaseLLMProvider ABC 与 LLMResponse 数据模型。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict


class LLMResponse(BaseModel):
    """LLM 调用响应数据模型。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    content: str = ""
    """原始文本响应。"""

    parsed: BaseModel | None = None
    """解析后的结构化输出（若提供了 response_schema）。"""

    model: str = ""
    """实际使用的模型名（可能因 fallback 与请求不同）。"""

    input_tokens: int = 0
    """输入 token 数。"""

    output_tokens: int = 0
    """输出 token 数。"""

    latency_ms: int = 0
    """调用延迟（毫秒）。"""

    success: bool = False
    """调用是否成功。"""

    error: str | None = None
    """错误信息（失败时）。"""


class BaseLLMProvider(ABC):
    """LLM 提供者抽象基类。所有 LLM 实现必须继承此类。"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """调用 LLM 生成文本。

        Args:
            prompt: 输入提示文本
            model: 指定模型名（None 时使用主力模型）
            response_schema: 期望的结构化输出 Pydantic 模型
            temperature: 生成温度
            max_tokens: 最大输出 token 数

        Returns:
            LLMResponse 对象
        """
        ...

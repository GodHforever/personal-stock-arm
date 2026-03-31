"""LLM 集成子模块：统一大语言模型调用接口。"""

from src.analysis.llm.base import BaseLLMProvider, LLMResponse
from src.analysis.llm.budget import TokenBudgetTracker
from src.analysis.llm.prompt_manager import PromptManager

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "LiteLLMRouter",
    "PromptManager",
    "TokenBudgetTracker",
]


def __getattr__(name: str) -> object:
    """延迟导入 LiteLLMRouter（避免 litellm 在测试收集阶段引发导入错误）。"""
    if name == "LiteLLMRouter":
        from src.analysis.llm.router import LiteLLMRouter

        return LiteLLMRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


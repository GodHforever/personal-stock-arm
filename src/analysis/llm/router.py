"""LiteLLM Router：基于 litellm 的 LLM 调用实现。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import litellm  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from src.analysis.llm.base import BaseLLMProvider, LLMResponse
from src.analysis.llm.budget import TokenBudgetTracker
from src.config.manager import ConfigManager

logger = logging.getLogger(__name__)

# 结构化输出 retry 时附加的格式提示
_JSON_FORMAT_HINT = (
    "\n\n请严格按照以下 JSON 格式返回，不要包含任何其他文本：\n{schema}"
)


class LiteLLMRouter(BaseLLMProvider):
    """基于 LiteLLM 的 LLM 调用路由器。

    功能：
    - 从 ConfigManager 读取模型配置（主力、快速、兜底链）
    - 主模型失败后自动尝试 fallback chain
    - 支持结构化输出解析（Pydantic schema）
    - 每次调用记录日志和 token 用量
    - 无 API Key 时可初始化但调用返回错误
    """

    def __init__(
        self,
        budget_tracker: TokenBudgetTracker | None = None,
    ) -> None:
        config = ConfigManager.get_section("llm")
        self._primary_model: str = config.primary_model
        self._fast_model: str = config.fast_model
        self._fallback_chain: list[str] = list(config.fallback_chain)
        self._api_key: str = config.api_key.get_secret_value()
        self._budget = budget_tracker or TokenBudgetTracker(
            daily_limit=config.daily_token_limit,
        )

    @property
    def budget_tracker(self) -> TokenBudgetTracker:
        """获取 token 预算追踪器。"""
        return self._budget

    async def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """调用 LLM 生成文本，支持 fallback 和结构化输出。"""
        # 检查 API Key
        if not self._api_key:
            return LLMResponse(
                success=False,
                error="未配置 LLM API Key，请设置 STOCK_ARM_LLM_API_KEY 环境变量",
            )

        # 检查预算
        if not self._budget.check_budget(max_tokens):
            return LLMResponse(
                success=False,
                error="每日 Token 预算已耗尽，请等待次日重置或调整预算配置",
            )

        target_model = model or self._primary_model
        models_to_try = [target_model] + [
            m for m in self._fallback_chain if m != target_model
        ]

        last_error: str = ""
        for current_model in models_to_try:
            response = await self._call_model(
                prompt=prompt,
                model=current_model,
                response_schema=response_schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response.success:
                return response
            last_error = response.error or "未知错误"
            logger.warning(
                "模型 %s 调用失败: %s，尝试下一个模型",
                current_model,
                last_error,
            )

        return LLMResponse(
            success=False,
            error=f"所有模型调用均失败，最后一个错误: {last_error}",
        )

    async def _call_model(
        self,
        *,
        prompt: str,
        model: str,
        response_schema: type[BaseModel] | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """调用单个模型。"""
        start_ms = _now_ms()
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            latency = _now_ms() - start_ms
            logger.error("LLM 调用异常: 模型=%s, 耗时=%dms, 错误=%s", model, latency, exc)
            return LLMResponse(
                model=model,
                latency_ms=latency,
                success=False,
                error=str(exc),
            )

        # 提取响应数据
        content = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        latency = _now_ms() - start_ms

        # 记录 token 用量
        self._budget.record_usage(model, input_tokens, output_tokens)

        # 记录调用日志
        logger.info(
            "LLM 调用完成: 模型=%s, 输入=%d tokens, 输出=%d tokens, 耗时=%dms",
            model,
            input_tokens,
            output_tokens,
            latency,
        )

        # 结构化输出解析
        parsed = None
        if response_schema is not None:
            parsed = self._try_parse(content, response_schema)
            if parsed is None:
                # Retry 一次，附加格式提示
                logger.info("结构化输出解析失败，附加格式提示重试: 模型=%s", model)
                retry_response = await self._retry_with_format_hint(
                    prompt=prompt,
                    model=model,
                    response_schema=response_schema,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if retry_response is not None:
                    return retry_response

        return LLMResponse(
            content=content,
            parsed=parsed,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            success=True,
        )

    async def _retry_with_format_hint(
        self,
        *,
        prompt: str,
        model: str,
        response_schema: type[BaseModel],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse | None:
        """附加 JSON 格式提示后重试一次。成功返回 LLMResponse，失败返回 None。"""
        schema_json = json.dumps(
            response_schema.model_json_schema(), ensure_ascii=False, indent=2
        )
        enhanced_prompt = prompt + _JSON_FORMAT_HINT.format(schema=schema_json)

        start_ms = _now_ms()
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": enhanced_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.warning("结构化输出重试调用失败: %s", exc)
            return None

        content = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        latency = _now_ms() - start_ms

        self._budget.record_usage(model, input_tokens, output_tokens)

        parsed = self._try_parse(content, response_schema)
        if parsed is None:
            logger.warning("结构化输出重试解析仍然失败，返回原始文本: 模型=%s", model)

        return LLMResponse(
            content=content,
            parsed=parsed,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            success=True,
        )

    @staticmethod
    def _try_parse(content: str, schema: type[BaseModel]) -> BaseModel | None:
        """尝试将 LLM 输出解析为指定的 Pydantic 模型。"""
        # 尝试提取 JSON（可能包裹在 markdown code block 中）
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉首尾的 ``` 行
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                if line.strip() == "```" and in_block:
                    break
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)

        try:
            data: Any = json.loads(text)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.debug("结构化输出解析失败: %s", exc)
            return None


def _now_ms() -> int:
    """获取当前时间的毫秒时间戳。"""
    return int(time.monotonic() * 1000)

"""LLM 集成模块单元测试。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.analysis.llm.base import BaseLLMProvider, LLMResponse
from src.analysis.llm.budget import TokenBudgetTracker
from src.analysis.llm.prompt_manager import PromptManager
from src.analysis.llm.router import LiteLLMRouter


# ======================== LLMResponse 测试 ========================


class TestLLMResponse:
    """LLMResponse 数据模型测试。"""

    def test_默认值(self) -> None:
        resp = LLMResponse()
        assert resp.content == ""
        assert resp.parsed is None
        assert resp.model == ""
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.latency_ms == 0
        assert resp.success is False
        assert resp.error is None

    def test_完整构造(self) -> None:
        resp = LLMResponse(
            content="分析结果",
            model="deepseek-chat",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1200,
            success=True,
        )
        assert resp.content == "分析结果"
        assert resp.model == "deepseek-chat"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.latency_ms == 1200
        assert resp.success is True

    def test_parsed_字段接受_pydantic_model(self) -> None:
        class StockResult(BaseModel):
            summary: str

        result = StockResult(summary="看好")
        resp = LLMResponse(content="ok", parsed=result, success=True)
        assert resp.parsed is not None
        assert isinstance(resp.parsed, StockResult)
        assert resp.parsed.summary == "看好"  # type: ignore[attr-defined]


# ======================== BaseLLMProvider 测试 ========================


class TestBaseLLMProvider:
    """BaseLLMProvider ABC 测试。"""

    def test_不可直接实例化(self) -> None:
        with pytest.raises(TypeError):
            BaseLLMProvider()  # type: ignore[abstract]

    def test_子类必须实现_complete(self) -> None:
        class IncompleteProvider(BaseLLMProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_正确子类可实例化(self) -> None:
        class MockProvider(BaseLLMProvider):
            async def complete(
                self,
                prompt: str,
                *,
                model: str | None = None,
                response_schema: type[BaseModel] | None = None,
                temperature: float = 0.3,
                max_tokens: int = 4096,
            ) -> LLMResponse:
                return LLMResponse(content="ok", success=True)

        provider = MockProvider()
        assert isinstance(provider, BaseLLMProvider)


# ======================== TokenBudgetTracker 测试 ========================


class TestTokenBudgetTracker:
    """TokenBudgetTracker 测试。"""

    def test_初始状态(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=100_000)
        assert tracker.used_tokens == 0
        assert tracker.daily_limit == 100_000
        assert tracker.remaining == 100_000

    def test_预算检查_充足(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=100_000)
        assert tracker.check_budget(1000) is True

    def test_预算检查_不足(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=1000)
        tracker.record_usage("test-model", 500, 400)
        assert tracker.check_budget(200) is False

    def test_记录用量(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=100_000)
        tracker.record_usage("deepseek-chat", 100, 50)
        assert tracker.used_tokens == 150
        assert tracker.remaining == 100_000 - 150

    def test_多次记录累计(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=100_000)
        tracker.record_usage("model-a", 100, 50)
        tracker.record_usage("model-b", 200, 100)
        assert tracker.used_tokens == 450

    def test_80_百分比警告(self, caplog: pytest.LogCaptureFixture) -> None:
        tracker = TokenBudgetTracker(daily_limit=1000)
        import logging

        with caplog.at_level(logging.WARNING):
            tracker.record_usage("test", 400, 400)  # 800 = 80%
        assert "80%" in caplog.text

    def test_日期切换重置(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=100_000)
        tracker.record_usage("test", 500, 500)
        assert tracker.used_tokens == 1000
        # 模拟日期切换
        tracker._today = date(2020, 1, 1)
        assert tracker.used_tokens == 0

    def test_零预算_不限制(self) -> None:
        tracker = TokenBudgetTracker(daily_limit=0)
        assert tracker.check_budget(999_999) is True


# ======================== PromptManager 测试 ========================


class TestPromptManager:
    """PromptManager 测试。"""

    def test_加载_jinja2_模板(self, tmp_path: Path) -> None:
        template = tmp_path / "test.j2"
        template.write_text("你好 {{ name }}", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        raw = pm.load_template("test.j2")
        assert "{{ name }}" in raw

    def test_渲染_jinja2_模板(self, tmp_path: Path) -> None:
        template = tmp_path / "test.j2"
        template.write_text("分析 {{ stock_code }} 的走势", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test.j2", stock_code="000001")
        assert result == "分析 000001 的走势"

    def test_渲染_简单_txt_模板(self, tmp_path: Path) -> None:
        template = tmp_path / "test.txt"
        template.write_text("分析 {stock_code} 的走势", encoding="utf-8")
        pm = PromptManager(prompts_dir=tmp_path)
        result = pm.render("test.txt", stock_code="600036")
        assert result == "分析 600036 的走势"

    def test_模板不存在_抛出异常(self, tmp_path: Path) -> None:
        pm = PromptManager(prompts_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            pm.load_template("nonexistent.j2")

    def test_jinja2_模板不存在_抛出异常(self, tmp_path: Path) -> None:
        pm = PromptManager(prompts_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            pm.render("nonexistent.j2")

    def test_jinja2_条件渲染(self, tmp_path: Path) -> None:
        template = tmp_path / "cond.j2"
        template.write_text(
            "{% if show %}显示{% else %}隐藏{% endif %}", encoding="utf-8"
        )
        pm = PromptManager(prompts_dir=tmp_path)
        assert pm.render("cond.j2", show=True) == "显示"
        assert pm.render("cond.j2", show=False) == "隐藏"

    def test_默认_prompts_目录(self) -> None:
        pm = PromptManager()
        # 应能加载项目中的示例模板
        raw = pm.load_template("stock_analysis.j2")
        assert "股票" in raw

    def test_渲染示例模板(self) -> None:
        pm = PromptManager()
        result = pm.render(
            "stock_analysis.j2",
            stock_code="000001",
            stock_name="平安银行",
            industry="银行",
            additional_context="",
        )
        assert "000001" in result
        assert "平安银行" in result


# ======================== LiteLLMRouter 测试 ========================


def _make_llm_config(**overrides: Any) -> MagicMock:
    """创建模拟的 LLMConfig。"""
    defaults = {
        "primary_model": "deepseek-chat",
        "fast_model": "glm-4-flash",
        "fallback_chain": ["qwen-plus", "gpt-4o-mini"],
        "api_key": MagicMock(get_secret_value=MagicMock(return_value="test-key")),
        "daily_token_limit": 500_000,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _make_litellm_response(
    content: str = "分析结果",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> SimpleNamespace:
    """创建模拟的 litellm 响应。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


class TestLiteLLMRouter:
    """LiteLLMRouter 测试。"""

    @patch("src.analysis.llm.router.ConfigManager")
    def test_初始化_读取配置(self, mock_cm: MagicMock) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        router = LiteLLMRouter()
        mock_cm.get_section.assert_called_once_with("llm")
        assert router._primary_model == "deepseek-chat"

    @patch("src.analysis.llm.router.ConfigManager")
    async def test_无_api_key_返回错误(self, mock_cm: MagicMock) -> None:
        mock_cm.get_section.return_value = _make_llm_config(
            api_key=MagicMock(get_secret_value=MagicMock(return_value="")),
        )
        router = LiteLLMRouter()
        resp = await router.complete("测试")
        assert resp.success is False
        assert "API Key" in (resp.error or "")

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_正常调用(self, mock_cm: MagicMock, mock_litellm: MagicMock) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(return_value=_make_litellm_response())
        router = LiteLLMRouter()
        resp = await router.complete("分析平安银行")
        assert resp.success is True
        assert resp.content == "分析结果"
        assert resp.model == "deepseek-chat"
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_指定模型(self, mock_cm: MagicMock, mock_litellm: MagicMock) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(return_value=_make_litellm_response())
        router = LiteLLMRouter()
        resp = await router.complete("测试", model="gpt-4o")
        assert resp.success is True
        mock_litellm.acompletion.assert_called_once()
        call_kwargs = mock_litellm.acompletion.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_fallback_机制(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        # 第一次调用失败，第二次成功
        mock_litellm.acompletion = AsyncMock(
            side_effect=[
                Exception("主模型不可用"),
                _make_litellm_response(content="备用模型结果"),
            ]
        )
        router = LiteLLMRouter()
        resp = await router.complete("测试")
        assert resp.success is True
        assert resp.content == "备用模型结果"
        assert resp.model == "qwen-plus"  # fallback_chain 第一个

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_全部模型失败(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("全部不可用"))
        router = LiteLLMRouter()
        resp = await router.complete("测试")
        assert resp.success is False
        assert "所有模型调用均失败" in (resp.error or "")

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_结构化输出_解析成功(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        class StockResult(BaseModel):
            summary: str
            recommendation: str

        json_content = json.dumps(
            {"summary": "看好", "recommendation": "买入"}, ensure_ascii=False
        )
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_litellm_response(content=json_content)
        )
        router = LiteLLMRouter()
        resp = await router.complete("分析", response_schema=StockResult)
        assert resp.success is True
        assert resp.parsed is not None
        assert isinstance(resp.parsed, StockResult)
        assert resp.parsed.summary == "看好"  # type: ignore[attr-defined]

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_结构化输出_markdown_code_block(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        class Result(BaseModel):
            value: int

        json_content = '```json\n{"value": 42}\n```'
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_litellm_response(content=json_content)
        )
        router = LiteLLMRouter()
        resp = await router.complete("测试", response_schema=Result)
        assert resp.success is True
        assert resp.parsed is not None
        assert resp.parsed.value == 42  # type: ignore[attr-defined]

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_结构化输出_解析失败_重试(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        class StockResult(BaseModel):
            summary: str

        # 第一次返回非 JSON，第二次（retry）返回正确 JSON
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(
            side_effect=[
                _make_litellm_response(content="这不是JSON"),
                _make_litellm_response(
                    content=json.dumps({"summary": "重试成功"}, ensure_ascii=False)
                ),
            ]
        )
        router = LiteLLMRouter()
        resp = await router.complete("分析", response_schema=StockResult)
        assert resp.success is True
        assert resp.parsed is not None
        assert resp.parsed.summary == "重试成功"  # type: ignore[attr-defined]

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_结构化输出_重试也失败(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        class StockResult(BaseModel):
            summary: str

        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_litellm_response(content="不是JSON")
        )
        router = LiteLLMRouter()
        resp = await router.complete("分析", response_schema=StockResult)
        assert resp.success is True
        assert resp.parsed is None  # 解析失败但调用本身成功

    @patch("src.analysis.llm.router.ConfigManager")
    async def test_预算耗尽_拒绝调用(self, mock_cm: MagicMock) -> None:
        mock_cm.get_section.return_value = _make_llm_config(daily_token_limit=100)
        router = LiteLLMRouter()
        # 消耗预算
        router.budget_tracker.record_usage("test", 50, 60)
        resp = await router.complete("测试")
        assert resp.success is False
        assert "预算" in (resp.error or "")

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_调用记录_token_用量(
        self, mock_cm: MagicMock, mock_litellm: MagicMock
    ) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_litellm_response(prompt_tokens=200, completion_tokens=100)
        )
        router = LiteLLMRouter()
        await router.complete("测试")
        assert router.budget_tracker.used_tokens == 300

    @patch("src.analysis.llm.router.litellm")
    @patch("src.analysis.llm.router.ConfigManager")
    async def test_调用日志_记录(
        self, mock_cm: MagicMock, mock_litellm: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        mock_cm.get_section.return_value = _make_llm_config()
        mock_litellm.acompletion = AsyncMock(return_value=_make_litellm_response())
        router = LiteLLMRouter()
        with caplog.at_level(logging.INFO):
            await router.complete("测试")
        assert "LLM 调用完成" in caplog.text
        assert "deepseek-chat" in caplog.text

    @patch("src.analysis.llm.router.ConfigManager")
    def test_自定义_budget_tracker(self, mock_cm: MagicMock) -> None:
        mock_cm.get_section.return_value = _make_llm_config()
        custom_budget = TokenBudgetTracker(daily_limit=999)
        router = LiteLLMRouter(budget_tracker=custom_budget)
        assert router.budget_tracker is custom_budget
        assert router.budget_tracker.daily_limit == 999

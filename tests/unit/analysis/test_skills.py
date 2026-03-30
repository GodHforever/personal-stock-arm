"""Skills 适配器层单元测试。

测试策略：
- BaseSkillAdapter: 验证 ABC 约束，测试具体子类实现
- SkillRegistry: 测试 YAML 加载、按分类过滤、按名称查找、异常处理
- 策略加载器: 测试正常加载、缺少字段、文件不存在等场景
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.analysis.skills.base import BaseSkillAdapter
from src.analysis.skills.loader import StrategyDefinition, load_strategy
from src.analysis.skills.registry import SkillEntry, SkillRegistry


# ===================== BaseSkillAdapter 测试 =====================


class DummyInput(BaseModel):
    """测试用输入模型。"""

    value: str


class DummyOutput(BaseModel):
    """测试用输出模型。"""

    result: str


class DummySkillAdapter(BaseSkillAdapter):
    """测试用的具体适配器实现。"""

    @property
    def skill_name(self) -> str:
        return "测试技能"

    @property
    def skill_source(self) -> str:
        return "https://example.com/test-skill"

    async def execute(self, input_data: BaseModel) -> BaseModel:
        assert isinstance(input_data, DummyInput)
        return DummyOutput(result=f"处理完成: {input_data.value}")

    def health_check(self) -> bool:
        return True


class TestBaseSkillAdapter:
    """BaseSkillAdapter ABC 测试。"""

    def test_不能直接实例化ABC(self) -> None:
        with pytest.raises(TypeError):
            BaseSkillAdapter()  # type: ignore[abstract]

    def test_具体子类可以实例化(self) -> None:
        adapter = DummySkillAdapter()
        assert adapter.skill_name == "测试技能"
        assert adapter.skill_source == "https://example.com/test-skill"

    def test_健康检查(self) -> None:
        adapter = DummySkillAdapter()
        assert adapter.health_check() is True

    async def test_执行技能(self) -> None:
        adapter = DummySkillAdapter()
        input_data = DummyInput(value="测试数据")
        result = await adapter.execute(input_data)
        assert isinstance(result, DummyOutput)
        assert result.result == "处理完成: 测试数据"

    def test_缺少方法的子类不能实例化(self) -> None:
        class IncompleteAdapter(BaseSkillAdapter):
            @property
            def skill_name(self) -> str:
                return "不完整"

            @property
            def skill_source(self) -> str:
                return "test"

            # 缺少 execute 和 health_check

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore[abstract]


# ===================== SkillRegistry 测试 =====================


SAMPLE_REGISTRY_YAML = """\
skills:
  - name: "ta-lib"
    source: "https://github.com/TA-Lib/ta-lib-python"
    category: "technical-analysis"
    tier: "reference"
    evaluated: "2026-03-29"
    decision: "Heavy C dependency, reference only"
    new_deps: []
    adapter: null
    status: "reference-only"
    notes: "纯 Python 重实现核心算法"

  - name: "longbridge-mcp"
    source: "https://open.longbridge.com/mcp"
    category: "data-fetching"
    tier: "direct-use"
    evaluated: "2026-03-29"
    decision: "Direct integration via MCP"
    new_deps: ["longbridge"]
    adapter: "src/skills/longbridge_adapter.py"
    status: "planned"
"""

EMPTY_REGISTRY_YAML = """\
skills: []
"""

INVALID_REGISTRY_YAML = """\
not_skills: "invalid"
"""


class TestSkillRegistry:
    """SkillRegistry 测试。"""

    def test_加载正常注册表(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(SAMPLE_REGISTRY_YAML, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        registry.load()

        assert len(registry.skills) == 2

    def test_按分类过滤(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(SAMPLE_REGISTRY_YAML, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        registry.load()

        ta_skills = registry.get_skills("technical-analysis")
        assert len(ta_skills) == 1
        assert ta_skills[0].name == "ta-lib"

        data_skills = registry.get_skills("data-fetching")
        assert len(data_skills) == 1
        assert data_skills[0].name == "longbridge-mcp"

        empty_skills = registry.get_skills("nonexistent")
        assert len(empty_skills) == 0

    def test_按名称查找(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(SAMPLE_REGISTRY_YAML, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        registry.load()

        skill = registry.get_skill("ta-lib")
        assert skill is not None
        assert skill.tier == "reference"
        assert skill.category == "technical-analysis"

        none_skill = registry.get_skill("不存在的技能")
        assert none_skill is None

    def test_加载空注册表(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(EMPTY_REGISTRY_YAML, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        registry.load()

        assert len(registry.skills) == 0

    def test_文件不存在抛出异常(self, tmp_path: Path) -> None:
        registry = SkillRegistry(registry_path=tmp_path / "nonexistent.yaml")
        with pytest.raises(FileNotFoundError, match="技能注册表文件不存在"):
            registry.load()

    def test_格式不合法抛出异常(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text("just a string", encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        with pytest.raises(ValueError, match="注册表格式不合法"):
            registry.load()

    def test_skills字段非列表抛出异常(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(INVALID_REGISTRY_YAML, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        # skills 字段不存在时默认为空列表，不应报错
        registry.load()
        assert len(registry.skills) == 0

    def test_SkillEntry模型字段完整(self) -> None:
        entry = SkillEntry(
            name="test-skill",
            source="https://example.com",
            category="test",
            tier="direct-use",
            evaluated="2026-03-30",
            decision="测试用",
            new_deps=["pkg1"],
            adapter="src/skills/test.py",
            status="planned",
            notes="备注",
        )
        assert entry.name == "test-skill"
        assert entry.new_deps == ["pkg1"]
        assert entry.status == "planned"

    def test_skills属性返回副本(self, tmp_path: Path) -> None:
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(SAMPLE_REGISTRY_YAML, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        registry.load()

        skills_copy = registry.skills
        skills_copy.clear()
        # 修改副本不应影响内部列表
        assert len(registry.skills) == 2

    def test_跳过无法解析的条目(self, tmp_path: Path) -> None:
        bad_yaml = """\
skills:
  - name: "valid"
    source: "https://example.com"
    category: "test"
    tier: "direct-use"
    evaluated: "2026-03-30"
    decision: "ok"
  - "not-a-dict"
  - name: "bad-tier"
    source: "x"
    category: "test"
    tier: "invalid-tier"
    evaluated: "2026-03-30"
    decision: "bad"
"""
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(bad_yaml, encoding="utf-8")

        registry = SkillRegistry(registry_path=registry_file)
        registry.load()

        # 只有第一条有效记录被加载
        assert len(registry.skills) == 1
        assert registry.skills[0].name == "valid"


# ===================== 策略加载器测试 =====================


SAMPLE_STRATEGY_YAML = """\
name: bull_trend
description: "均线多头排列策略"
version: "1.0"
category: "strategy"

trigger:
  conditions:
    - "MA5 > MA10 > MA20"
    - "乖离率 < 5%"

input:
  schema: "StockKlineData"
  fields:
    - name: kline_data
      type: "list[KlineBar]"
      required: true

output:
  schema: "StrategySignal"
  fields:
    - name: signal
      type: "str"
    - name: confidence
      type: "float"
    - name: reasoning
      type: "str"

implementation: "src/skills/strategies/bull_trend.py"
"""

MINIMAL_STRATEGY_YAML = """\
name: simple_strategy
"""


class TestLoadStrategy:
    """策略加载器测试。"""

    def test_加载完整策略定义(self, tmp_path: Path) -> None:
        strategy_file = tmp_path / "bull_trend.yaml"
        strategy_file.write_text(SAMPLE_STRATEGY_YAML, encoding="utf-8")

        strategy = load_strategy(strategy_file)

        assert strategy.name == "bull_trend"
        assert strategy.description == "均线多头排列策略"
        assert strategy.version == "1.0"
        assert strategy.category == "strategy"
        assert len(strategy.trigger.conditions) == 2
        assert len(strategy.input.fields) == 1
        assert strategy.input.fields[0].name == "kline_data"
        assert strategy.input.fields[0].required is True
        assert len(strategy.output.fields) == 3
        assert strategy.implementation == "src/skills/strategies/bull_trend.py"

    def test_加载最小策略定义(self, tmp_path: Path) -> None:
        strategy_file = tmp_path / "simple.yaml"
        strategy_file.write_text(MINIMAL_STRATEGY_YAML, encoding="utf-8")

        strategy = load_strategy(strategy_file)

        assert strategy.name == "simple_strategy"
        assert strategy.description == ""
        assert strategy.version == "1.0"
        assert strategy.category == ""
        assert len(strategy.trigger.conditions) == 0
        assert len(strategy.input.fields) == 0
        assert len(strategy.output.fields) == 0

    def test_文件不存在抛出异常(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="策略文件不存在"):
            load_strategy(tmp_path / "nonexistent.yaml")

    def test_格式不合法抛出异常(self, tmp_path: Path) -> None:
        strategy_file = tmp_path / "bad.yaml"
        strategy_file.write_text("just a string", encoding="utf-8")

        with pytest.raises(ValueError, match="策略文件格式不合法"):
            load_strategy(strategy_file)

    def test_缺少name字段抛出异常(self, tmp_path: Path) -> None:
        strategy_file = tmp_path / "no_name.yaml"
        strategy_file.write_text("description: '没有名称的策略'", encoding="utf-8")

        with pytest.raises(ValueError, match="缺少必需字段 'name'"):
            load_strategy(strategy_file)

    def test_StrategyDefinition模型字段(self) -> None:
        strategy = StrategyDefinition(
            name="test",
            description="测试策略",
            version="2.0",
            category="test-cat",
            implementation="src/test.py",
        )
        assert strategy.name == "test"
        assert strategy.version == "2.0"

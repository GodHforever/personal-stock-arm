"""Prompt 模板管理器：加载和渲染 LLM 提示模板。"""

from __future__ import annotations

import logging
import string
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class PromptManager:
    """管理 prompts/ 目录下的提示模板。

    支持两种模板格式：
    - Jinja2 模板 (.j2)：使用 {{ variable }} 语法
    - 简单占位符 (.txt)：使用 {variable} 语法（Python str.format_map）
    """

    def __init__(self, prompts_dir: str | Path | None = None) -> None:
        if prompts_dir is None:
            # 默认使用项目根目录下的 prompts/
            prompts_dir = Path(__file__).resolve().parents[3] / "prompts"
        self._prompts_dir = Path(prompts_dir)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self._prompts_dir)),
            autoescape=False,
        )
        logger.debug("PromptManager 初始化，模板目录: %s", self._prompts_dir)

    def load_template(self, name: str) -> str:
        """加载模板原始内容。

        Args:
            name: 模板文件名（如 "stock_analysis.j2"）

        Returns:
            模板原始文本

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        path = self._prompts_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Prompt 模板不存在: {path}")
        content = path.read_text(encoding="utf-8")
        logger.debug("加载模板: %s (%d 字符)", name, len(content))
        return content

    def render(self, template_name: str, **kwargs: object) -> str:
        """渲染模板并填充变量。

        根据文件后缀选择渲染方式：
        - .j2: Jinja2 渲染
        - .txt 或其他: Python str.format_map 渲染

        Args:
            template_name: 模板文件名
            **kwargs: 模板变量

        Returns:
            渲染后的文本

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        if template_name.endswith(".j2"):
            return self._render_jinja2(template_name, **kwargs)
        return self._render_simple(template_name, **kwargs)

    def _render_jinja2(self, template_name: str, **kwargs: object) -> str:
        """使用 Jinja2 渲染模板。"""
        try:
            template = self._jinja_env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(
                f"Prompt 模板不存在: {self._prompts_dir / template_name}"
            ) from exc
        result = template.render(**kwargs)
        logger.debug("Jinja2 渲染完成: %s (%d 字符)", template_name, len(result))
        return result

    def _render_simple(self, template_name: str, **kwargs: object) -> str:
        """使用 Python format_map 渲染简单占位符模板。"""
        raw = self.load_template(template_name)
        formatter = string.Formatter()
        result = formatter.format(raw, **kwargs)
        logger.debug("简单模板渲染完成: %s (%d 字符)", template_name, len(result))
        return result

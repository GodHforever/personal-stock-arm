"""数据源异常：结构化的网络请求错误，包含定位和建议信息。"""

from __future__ import annotations


class DataSourceError(Exception):
    """数据源请求异常。

    提供结构化的错误信息，便于上层模块定位问题和向用户展示可读的错误提示。

    Attributes:
        step: 出错步骤（如 "请求发送"、"响应解析"）
        source: 数据源名称（如 "tushare"、"akshare"）
        url: 请求的 URL
        error_type: 错误类型（如 "超时"、"连接失败"、"HTTP错误"）
        error_msg: 原始错误消息
        suggestion: 建议的处理方式
    """

    def __init__(
        self,
        *,
        step: str,
        source: str,
        url: str,
        error_type: str,
        error_msg: str,
        suggestion: str,
    ) -> None:
        self.step = step
        self.source = source
        self.url = url
        self.error_type = error_type
        self.error_msg = error_msg
        self.suggestion = suggestion
        super().__init__(str(self))

    def to_dict(self) -> dict[str, str]:
        """将异常信息序列化为字典。"""
        return {
            "step": self.step,
            "source": self.source,
            "url": self.url,
            "error_type": self.error_type,
            "error_msg": self.error_msg,
            "suggestion": self.suggestion,
        }

    def __str__(self) -> str:
        """返回中文可读的错误描述。"""
        return (
            f"[{self.source}] {self.step}失败 — "
            f"{self.error_type}: {self.error_msg} | "
            f"URL: {self.url} | "
            f"建议: {self.suggestion}"
        )

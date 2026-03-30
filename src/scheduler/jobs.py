"""调度任务 stub 函数：定义所有预注册的定时任务。

实际业务逻辑将在 Layer 4 实现，此处仅记录日志作为占位。
"""

from __future__ import annotations

from src.log import get_logger

logger = get_logger(__name__)


async def daily_analysis() -> None:
    """每日个股分析任务（默认 18:00）。"""
    logger.info("执行每日个股分析任务")


async def daily_macro() -> None:
    """每日宏观数据任务（默认 18:30）。"""
    logger.info("执行每日宏观数据任务")


async def daily_briefing() -> None:
    """每日简报任务（默认 19:00）。"""
    logger.info("执行每日简报任务")


async def earnings_scan() -> None:
    """财报扫描任务（默认 20:00，财报季）。"""
    logger.info("执行财报扫描任务")


async def monthly_report() -> None:
    """月度报告任务（每月1号 09:00）。"""
    logger.info("执行月度报告生成任务")


async def data_cleanup() -> None:
    """数据清理任务（每月1号 03:00）。"""
    logger.info("执行数据清理任务")

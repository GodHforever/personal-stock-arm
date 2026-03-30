"""宏观数据模型：Pydantic 数据模型和 SQLAlchemy ORM 模型。"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin


class MacroIndicator(BaseModel):
    """宏观指标数据模型（Pydantic）。

    用于模块间传递指标数据，不直接持久化。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    """指标名称，如 "CPI"。"""

    category: str
    """指标类别，如 "价格"、"货币"、"利率"。"""

    value: float | None = None
    """当前值。"""

    prev_value: float | None = None
    """前值。"""

    unit: str = ""
    """单位，如 "%"、"亿元"。"""

    updated_at: datetime.datetime | None = None
    """数据更新时间。"""

    source: str = ""
    """数据来源，如 "akshare"。"""

    change: float | None = None
    """变化量 = value - prev_value。"""

    change_pct: float | None = None
    """变化率(%) = (value - prev_value) / |prev_value| * 100。"""

    no_update: bool = False
    """当日是否无更新。"""

    last_available_date: str = ""
    """最近可用数据的日期（当日无更新时使用）。"""

    error: str | None = None
    """拉取失败时的错误信息。"""


class MacroRecord(TimestampMixin, Base):
    """宏观指标数据库记录。

    只存储最新值和前值，不保留完整历史。
    """

    __tablename__ = "macro_record"

    indicator_name: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="指标名称"
    )
    current_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="最新值"
    )
    previous_value: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="前值"
    )
    change: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="变化量"
    )
    change_pct: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="变化率(%)"
    )
    unit: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="单位"
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", comment="数据来源"
    )
    data_updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, comment="数据更新时间（非记录更新时间）"
    )

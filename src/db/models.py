"""数据模型：定义所有 ORM 数据表模型。"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin


class SchedulerState(TimestampMixin, Base):
    """调度器状态表：记录各定时任务的运行状态。"""

    __tablename__ = "scheduler_state"

    job_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, comment="任务名称")
    last_run_time: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最近运行时间"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", comment="运行状态")

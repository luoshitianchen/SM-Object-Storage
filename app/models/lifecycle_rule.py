"""生命周期规则模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class LifecycleRule(Base):
    """生命周期规则：按前缀对桶内对象执行转储与过期清理。"""

    __tablename__ = "lifecycle_rules"
    __table_args__ = (
        UniqueConstraint("bucket_id", "prefix", name="uq_rule_bucket_prefix"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bucket_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    prefix: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(16), default="enabled", index=True)
    expiration_days: Mapped[int] = mapped_column(Integer, default=30)
    transitions: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

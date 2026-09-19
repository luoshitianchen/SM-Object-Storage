"""存储桶模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class StorageBucket(Base):
    """对象存储桶：顶层命名空间，承载对象与生命周期规则。"""

    __tablename__ = "storage_buckets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True, index=True)
    region: Mapped[str] = mapped_column(String(64), default="cn-east-1")
    storage_class: Mapped[str] = mapped_column(String(16), default="standard")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    versioning_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

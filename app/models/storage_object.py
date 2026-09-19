"""存储对象元数据模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class StorageObject(Base):
    """存储对象元数据：记录桶内对象的 key、大小、ETag 与存储类别。"""

    __tablename__ = "storage_objects"
    __table_args__ = (
        UniqueConstraint("bucket_id", "object_key", name="uq_object_bucket_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bucket_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    etag: Mapped[str] = mapped_column(String(64), default="")
    storage_class: Mapped[str] = mapped_column(String(16), default="standard")
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

"""存储对象 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ObjectRegister(BaseModel):
    """登记一个新上传对象的元数据（实际字节流由数据面承载）。"""

    bucket_id: str = Field(min_length=1, max_length=64)
    object_key: str = Field(min_length=1, max_length=1024)
    size_bytes: int = Field(default=0, ge=0)
    content_type: str = Field(default="application/octet-stream", max_length=128)
    etag: str = Field(default="", max_length=64)
    storage_class: Literal["standard", "infrequent", "archive"] = "standard"


class ObjectUpdate(BaseModel):
    size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = Field(default=None, max_length=128)
    etag: str | None = Field(default=None, max_length=64)
    storage_class: Literal["standard", "infrequent", "archive"] | None = None


class ObjectStatusUpdate(BaseModel):
    status: Literal["active", "archived", "deleted"]


class ObjectResponse(BaseModel):
    id: str
    bucket_id: str
    object_key: str
    size_bytes: int
    content_type: str
    etag: str
    storage_class: str
    status: str
    created_at: datetime | str
    updated_at: datetime | str


class ObjectListResponse(BaseModel):
    total: int
    items: list[ObjectResponse]

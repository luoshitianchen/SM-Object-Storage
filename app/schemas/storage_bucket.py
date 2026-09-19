"""存储桶 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BucketCreate(BaseModel):
    name: str = Field(min_length=3, max_length=63, pattern=r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
    region: str = Field(default="cn-east-1", min_length=1, max_length=64)
    storage_class: Literal["standard", "infrequent", "archive"] = "standard"
    versioning_enabled: bool = False


class BucketUpdate(BaseModel):
    region: str | None = Field(default=None, min_length=1, max_length=64)
    storage_class: Literal["standard", "infrequent", "archive"] | None = None
    versioning_enabled: bool | None = None


class BucketStatusUpdate(BaseModel):
    status: Literal["active", "locked", "deleted"]


class BucketResponse(BaseModel):
    id: str
    name: str
    region: str
    storage_class: str
    status: str
    versioning_enabled: bool
    created_at: datetime | str
    updated_at: datetime | str


class BucketListResponse(BaseModel):
    total: int
    items: list[BucketResponse]

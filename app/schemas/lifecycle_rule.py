"""生命周期规则 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LifecycleRuleCreate(BaseModel):
    bucket_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    prefix: str = Field(default="", max_length=1024)
    expiration_days: int = Field(default=30, ge=0, le=3650)
    transitions: list[str] = Field(default_factory=list)


class LifecycleRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    expiration_days: int | None = Field(default=None, ge=0, le=3650)
    transitions: list[str] | None = None


class LifecycleRuleStatusUpdate(BaseModel):
    status: Literal["enabled", "disabled"]


class LifecycleRuleResponse(BaseModel):
    id: str
    bucket_id: str
    name: str
    prefix: str
    status: str
    expiration_days: int
    transitions: list[str]
    created_at: datetime | str
    updated_at: datetime | str


class LifecycleRuleListResponse(BaseModel):
    total: int
    items: list[LifecycleRuleResponse]

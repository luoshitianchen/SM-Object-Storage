"""生命周期规则管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.lifecycle_rule import (
    LifecycleRuleCreate,
    LifecycleRuleStatusUpdate,
    LifecycleRuleUpdate,
)
from app.services.lifecycle_rule import LifecycleRuleService

router = APIRouter(prefix="/api/storage/lifecycle-rules", tags=["lifecycle-rules"])


@router.get("")
async def list_rules(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    bucket_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LifecycleRuleService.list_rules(
        session, limit=limit, offset=offset, bucket_id=bucket_id,
        status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: LifecycleRuleCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LifecycleRuleService.create_rule(session, payload, request)


@router.get("/{rule_id}")
async def get_rule(
    rule_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LifecycleRuleService.get_rule(session, rule_id)


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: str, payload: LifecycleRuleUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LifecycleRuleService.update_rule(session, rule_id, payload, request)


@router.patch("/{rule_id}/status")
async def update_rule_status(
    rule_id: str, payload: LifecycleRuleStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LifecycleRuleService.update_status(session, rule_id, payload.status, request)


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LifecycleRuleService.delete_rule(session, rule_id, request)

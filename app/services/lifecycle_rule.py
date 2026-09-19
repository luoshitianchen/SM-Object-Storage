"""生命周期规则服务层：规则配置与启停。"""
from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.lifecycle_rule import LifecycleRule
from app.repositories import lifecycle_rule as repo
from app.repositories import storage_bucket as bucket_repo
from app.schemas.lifecycle_rule import LifecycleRuleCreate, LifecycleRuleUpdate
from app.services.audit import record_audit

# 合法的存储类别转储目标
_VALID_TRANSITIONS = {"infrequent", "archive"}


def _rule_to_dict(r: LifecycleRule) -> dict:
    return {
        "id": r.id, "bucket_id": r.bucket_id, "name": r.name, "prefix": r.prefix or "",
        "status": r.status, "expiration_days": r.expiration_days,
        "transitions": json.loads(r.transitions or "[]"),
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


def _validate_transitions(transitions: list[str]) -> None:
    invalid = [t for t in transitions if t not in _VALID_TRANSITIONS]
    if invalid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"非法转储目标：{','.join(invalid)}")


class LifecycleRuleService:
    @staticmethod
    async def list_rules(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        bucket_id: str | None = None, status_filter: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        items = await repo.list_rules(
            session, limit=limit, offset=offset, bucket_id=bucket_id,
            status=status_filter, keyword=keyword,
        )
        total = await repo.count_rules(
            session, bucket_id=bucket_id, status=status_filter, keyword=keyword
        )
        return {"total": total, "items": [_rule_to_dict(r) for r in items]}

    @staticmethod
    async def get_rule(session: AsyncSession, rule_id: str) -> dict:
        rule = await repo.get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "生命周期规则不存在")
        return _rule_to_dict(rule)

    @staticmethod
    async def create_rule(
        session: AsyncSession, payload: LifecycleRuleCreate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        bucket = await bucket_repo.get_bucket(session, payload.bucket_id)
        if not bucket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "存储桶不存在")
        _validate_transitions(payload.transitions)
        if await repo.get_rule_by_prefix(session, payload.bucket_id, payload.prefix):
            raise HTTPException(status.HTTP_409_CONFLICT, "该桶下同前缀规则已存在")
        rule = LifecycleRule(
            id=str(uuid.uuid4()), bucket_id=payload.bucket_id, name=payload.name,
            prefix=payload.prefix, expiration_days=payload.expiration_days,
            transitions=json.dumps(payload.transitions, ensure_ascii=False),
            status="enabled",
        )
        rule = await repo.create_rule(session, rule)
        await record_audit(session, "lifecycle.created", "internal",
                           f"rule={payload.name}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def update_rule(
        session: AsyncSession, rule_id: str, payload: LifecycleRuleUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "生命周期规则不存在")
        if rule.status == "disabled":
            raise HTTPException(status.HTTP_409_CONFLICT, "已停用规则不可变更，请先启用")
        if payload.name is not None:
            rule.name = payload.name
        if payload.expiration_days is not None:
            rule.expiration_days = payload.expiration_days
        if payload.transitions is not None:
            _validate_transitions(payload.transitions)
            rule.transitions = json.dumps(payload.transitions, ensure_ascii=False)
        rule = await repo.update_rule(session, rule)
        await record_audit(session, "lifecycle.updated", "internal",
                           f"rule_id={rule_id}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def update_status(
        session: AsyncSession, rule_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "生命周期规则不存在")
        if new_status not in ("enabled", "disabled"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法状态值")
        rule.status = new_status
        rule = await repo.update_rule(session, rule)
        await record_audit(session, "lifecycle.status_changed", "internal",
                           f"rule_id={rule_id} status={new_status}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def delete_rule(session: AsyncSession, rule_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "生命周期规则不存在")
        name = rule.name
        await repo.delete_rule(session, rule)
        await record_audit(session, "lifecycle.deleted", "internal",
                           f"rule_id={rule_id} name={name}", request)
        return {"deleted": True, "id": rule_id}

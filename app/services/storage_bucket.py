"""存储桶服务层：桶全生命周期管理。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.storage_bucket import StorageBucket
from app.repositories import storage_bucket as repo
from app.repositories import storage_object as obj_repo
from app.schemas.storage_bucket import BucketCreate, BucketUpdate
from app.services.audit import record_audit

# 桶状态机：允许的合法迁移
_BUCKET_TRANSITIONS: dict[str, set[str]] = {
    "active": {"locked", "deleted"},
    "locked": {"active", "deleted"},
    "deleted": set(),
}


def _bucket_to_dict(b: StorageBucket) -> dict:
    return {
        "id": b.id, "name": b.name, "region": b.region,
        "storage_class": b.storage_class, "status": b.status,
        "versioning_enabled": bool(b.versioning_enabled),
        "created_at": b.created_at.isoformat() if b.created_at else "",
        "updated_at": b.updated_at.isoformat() if b.updated_at else "",
    }


class BucketService:
    @staticmethod
    async def list_buckets(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        status_filter: str | None = None, keyword: str | None = None,
    ) -> dict:
        items = await repo.list_buckets(
            session, limit=limit, offset=offset, status=status_filter, keyword=keyword
        )
        total = await repo.count_buckets(session, status=status_filter, keyword=keyword)
        return {"total": total, "items": [_bucket_to_dict(b) for b in items]}

    @staticmethod
    async def get_bucket(session: AsyncSession, bucket_id: str) -> dict:
        bucket = await repo.get_bucket(session, bucket_id)
        if not bucket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "存储桶不存在")
        return _bucket_to_dict(bucket)

    @staticmethod
    async def create_bucket(session: AsyncSession, payload: BucketCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_bucket_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "桶名已存在")
        bucket = StorageBucket(
            id=str(uuid.uuid4()), name=payload.name, region=payload.region,
            storage_class=payload.storage_class,
            versioning_enabled=payload.versioning_enabled, status="active",
        )
        bucket = await repo.create_bucket(session, bucket)
        await record_audit(session, "bucket.created", "internal",
                           f"bucket={payload.name}", request)
        return _bucket_to_dict(bucket)

    @staticmethod
    async def update_bucket(
        session: AsyncSession, bucket_id: str, payload: BucketUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        bucket = await repo.get_bucket(session, bucket_id)
        if not bucket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "存储桶不存在")
        if bucket.status == "deleted":
            raise HTTPException(status.HTTP_409_CONFLICT, "已删除桶不可变更")
        if payload.region is not None:
            bucket.region = payload.region
        if payload.storage_class is not None:
            bucket.storage_class = payload.storage_class
        if payload.versioning_enabled is not None:
            bucket.versioning_enabled = payload.versioning_enabled
        bucket = await repo.update_bucket(session, bucket)
        await record_audit(session, "bucket.updated", "internal",
                           f"bucket_id={bucket_id}", request)
        return _bucket_to_dict(bucket)

    @staticmethod
    async def update_status(
        session: AsyncSession, bucket_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        bucket = await repo.get_bucket(session, bucket_id)
        if not bucket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "存储桶不存在")
        allowed = _BUCKET_TRANSITIONS.get(bucket.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"非法状态迁移：{bucket.status} -> {new_status}",
            )
        # 仅当桶内无对象时才允许删除
        if new_status == "deleted":
            count = await obj_repo.count_objects_by_bucket(session, bucket_id)
            if count > 0:
                raise HTTPException(status.HTTP_409_CONFLICT, "桶内仍有对象，禁止删除")
        bucket.status = new_status
        bucket = await repo.update_bucket(session, bucket)
        await record_audit(session, "bucket.status_changed", "internal",
                           f"bucket_id={bucket_id} status={new_status}", request)
        return _bucket_to_dict(bucket)

    @staticmethod
    async def delete_bucket(session: AsyncSession, bucket_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        bucket = await repo.get_bucket(session, bucket_id)
        if not bucket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "存储桶不存在")
        count = await obj_repo.count_objects_by_bucket(session, bucket_id)
        if count > 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "桶内仍有对象，禁止删除")
        name = bucket.name
        await repo.delete_bucket(session, bucket)
        await record_audit(session, "bucket.deleted", "internal",
                           f"bucket_id={bucket_id} name={name}", request)
        return {"deleted": True, "id": bucket_id}

"""存储对象服务层：对象元数据登记与生命周期。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.storage_object import StorageObject
from app.repositories import storage_bucket as bucket_repo
from app.repositories import storage_object as repo
from app.schemas.storage_object import ObjectRegister, ObjectUpdate
from app.services.audit import record_audit

# 对象状态机：允许的合法迁移
_OBJECT_TRANSITIONS: dict[str, set[str]] = {
    "active": {"archived", "deleted"},
    "archived": {"active", "deleted"},
    "deleted": set(),
}


def _object_to_dict(o: StorageObject) -> dict:
    return {
        "id": o.id, "bucket_id": o.bucket_id, "object_key": o.object_key,
        "size_bytes": o.size_bytes, "content_type": o.content_type,
        "etag": o.etag or "", "storage_class": o.storage_class, "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else "",
        "updated_at": o.updated_at.isoformat() if o.updated_at else "",
    }


class StorageObjectService:
    @staticmethod
    async def list_objects(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        bucket_id: str | None = None, status_filter: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        items = await repo.list_objects(
            session, limit=limit, offset=offset, bucket_id=bucket_id,
            status=status_filter, keyword=keyword,
        )
        total = await repo.count_objects(
            session, bucket_id=bucket_id, status=status_filter, keyword=keyword
        )
        return {"total": total, "items": [_object_to_dict(o) for o in items]}

    @staticmethod
    async def get_object(session: AsyncSession, object_id: str) -> dict:
        obj = await repo.get_object(session, object_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
        return _object_to_dict(obj)

    @staticmethod
    async def register_object(
        session: AsyncSession, payload: ObjectRegister, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        bucket = await bucket_repo.get_bucket(session, payload.bucket_id)
        if not bucket:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "存储桶不存在")
        if bucket.status != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "仅 active 桶可写入对象")
        if await repo.get_object_by_key(session, payload.bucket_id, payload.object_key):
            raise HTTPException(status.HTTP_409_CONFLICT, "同 key 对象已存在")
        obj = StorageObject(
            id=str(uuid.uuid4()), bucket_id=payload.bucket_id,
            object_key=payload.object_key, size_bytes=payload.size_bytes,
            content_type=payload.content_type, etag=payload.etag,
            storage_class=payload.storage_class, status="active",
        )
        obj = await repo.create_object(session, obj)
        await record_audit(session, "object.registered", "internal",
                           f"object_key={payload.object_key}", request)
        return _object_to_dict(obj)

    @staticmethod
    async def update_object(
        session: AsyncSession, object_id: str, payload: ObjectUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        obj = await repo.get_object(session, object_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
        if obj.status == "deleted":
            raise HTTPException(status.HTTP_409_CONFLICT, "已删除对象不可变更")
        if payload.size_bytes is not None:
            obj.size_bytes = payload.size_bytes
        if payload.content_type is not None:
            obj.content_type = payload.content_type
        if payload.etag is not None:
            obj.etag = payload.etag
        if payload.storage_class is not None:
            obj.storage_class = payload.storage_class
        obj = await repo.update_object(session, obj)
        await record_audit(session, "object.updated", "internal",
                           f"object_id={object_id}", request)
        return _object_to_dict(obj)

    @staticmethod
    async def update_status(
        session: AsyncSession, object_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        obj = await repo.get_object(session, object_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
        allowed = _OBJECT_TRANSITIONS.get(obj.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"非法状态迁移：{obj.status} -> {new_status}",
            )
        obj.status = new_status
        obj = await repo.update_object(session, obj)
        await record_audit(session, "object.status_changed", "internal",
                           f"object_id={object_id} status={new_status}", request)
        return _object_to_dict(obj)

    @staticmethod
    async def delete_object(session: AsyncSession, object_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        obj = await repo.get_object(session, object_id)
        if not obj:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
        object_key = obj.object_key
        await repo.delete_object(session, obj)
        await record_audit(session, "object.deleted", "internal",
                           f"object_id={object_id} key={object_key}", request)
        return {"deleted": True, "id": object_id}

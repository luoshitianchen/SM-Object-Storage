"""存储对象仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_object import StorageObject


async def get_object(session: AsyncSession, object_id: str) -> StorageObject | None:
    result = await session.execute(select(StorageObject).where(StorageObject.id == object_id))
    return result.scalar_one_or_none()


async def get_object_by_key(
    session: AsyncSession, bucket_id: str, object_key: str
) -> StorageObject | None:
    stmt = select(StorageObject).where(
        StorageObject.bucket_id == bucket_id, StorageObject.object_key == object_key
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_objects(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    bucket_id: str | None = None, status: str | None = None, keyword: str | None = None,
) -> list[StorageObject]:
    stmt = select(StorageObject).order_by(StorageObject.created_at.desc()).limit(limit).offset(offset)
    if bucket_id:
        stmt = stmt.where(StorageObject.bucket_id == bucket_id)
    if status:
        stmt = stmt.where(StorageObject.status == status)
    if keyword:
        stmt = stmt.where(StorageObject.object_key.like(f"%{keyword}%"))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_objects(
    session: AsyncSession, bucket_id: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(StorageObject.id))
    if bucket_id:
        stmt = stmt.where(StorageObject.bucket_id == bucket_id)
    if status:
        stmt = stmt.where(StorageObject.status == status)
    if keyword:
        stmt = stmt.where(StorageObject.object_key.like(f"%{keyword}%"))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_objects_by_bucket(session: AsyncSession, bucket_id: str) -> int:
    stmt = select(func.count(StorageObject.id)).where(
        StorageObject.bucket_id == bucket_id, StorageObject.status != "deleted"
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_object(session: AsyncSession, obj: StorageObject) -> StorageObject:
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update_object(session: AsyncSession, obj: StorageObject) -> StorageObject:
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_object(session: AsyncSession, obj: StorageObject) -> None:
    await session.delete(obj)
    await session.commit()

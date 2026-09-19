"""存储桶仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_bucket import StorageBucket


async def get_bucket(session: AsyncSession, bucket_id: str) -> StorageBucket | None:
    result = await session.execute(select(StorageBucket).where(StorageBucket.id == bucket_id))
    return result.scalar_one_or_none()


async def get_bucket_by_name(session: AsyncSession, name: str) -> StorageBucket | None:
    result = await session.execute(select(StorageBucket).where(StorageBucket.name == name))
    return result.scalar_one_or_none()


async def list_buckets(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, keyword: str | None = None,
) -> list[StorageBucket]:
    stmt = select(StorageBucket).order_by(StorageBucket.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(StorageBucket.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(StorageBucket.name.like(pattern), StorageBucket.region.like(pattern)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_buckets(
    session: AsyncSession, status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(StorageBucket.id))
    if status:
        stmt = stmt.where(StorageBucket.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(or_(StorageBucket.name.like(pattern), StorageBucket.region.like(pattern)))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_bucket(session: AsyncSession, bucket: StorageBucket) -> StorageBucket:
    session.add(bucket)
    await session.commit()
    await session.refresh(bucket)
    return bucket


async def update_bucket(session: AsyncSession, bucket: StorageBucket) -> StorageBucket:
    await session.commit()
    await session.refresh(bucket)
    return bucket


async def delete_bucket(session: AsyncSession, bucket: StorageBucket) -> None:
    await session.delete(bucket)
    await session.commit()

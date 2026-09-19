"""生命周期规则仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lifecycle_rule import LifecycleRule


async def get_rule(session: AsyncSession, rule_id: str) -> LifecycleRule | None:
    result = await session.execute(select(LifecycleRule).where(LifecycleRule.id == rule_id))
    return result.scalar_one_or_none()


async def get_rule_by_prefix(
    session: AsyncSession, bucket_id: str, prefix: str
) -> LifecycleRule | None:
    stmt = select(LifecycleRule).where(
        LifecycleRule.bucket_id == bucket_id, LifecycleRule.prefix == prefix
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_rules(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    bucket_id: str | None = None, status: str | None = None, keyword: str | None = None,
) -> list[LifecycleRule]:
    stmt = select(LifecycleRule).order_by(LifecycleRule.created_at.desc()).limit(limit).offset(offset)
    if bucket_id:
        stmt = stmt.where(LifecycleRule.bucket_id == bucket_id)
    if status:
        stmt = stmt.where(LifecycleRule.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(LifecycleRule.name.like(pattern), LifecycleRule.prefix.like(pattern))
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_rules(
    session: AsyncSession, bucket_id: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(LifecycleRule.id))
    if bucket_id:
        stmt = stmt.where(LifecycleRule.bucket_id == bucket_id)
    if status:
        stmt = stmt.where(LifecycleRule.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(LifecycleRule.name.like(pattern), LifecycleRule.prefix.like(pattern))
        )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_rule(session: AsyncSession, rule: LifecycleRule) -> LifecycleRule:
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_rule(session: AsyncSession, rule: LifecycleRule) -> LifecycleRule:
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_rule(session: AsyncSession, rule: LifecycleRule) -> None:
    await session.delete(rule)
    await session.commit()

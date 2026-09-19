"""存储桶管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.storage_bucket import BucketCreate, BucketStatusUpdate, BucketUpdate
from app.services.storage_bucket import BucketService

router = APIRouter(prefix="/api/storage/buckets", tags=["storage-buckets"])


@router.get("")
async def list_buckets(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BucketService.list_buckets(
        session, limit=limit, offset=offset,
        status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bucket(
    payload: BucketCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BucketService.create_bucket(session, payload, request)


@router.get("/{bucket_id}")
async def get_bucket(
    bucket_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BucketService.get_bucket(session, bucket_id)


@router.patch("/{bucket_id}")
async def update_bucket(
    bucket_id: str, payload: BucketUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BucketService.update_bucket(session, bucket_id, payload, request)


@router.patch("/{bucket_id}/status")
async def update_bucket_status(
    bucket_id: str, payload: BucketStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BucketService.update_status(session, bucket_id, payload.status, request)


@router.delete("/{bucket_id}", status_code=status.HTTP_200_OK)
async def delete_bucket(
    bucket_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BucketService.delete_bucket(session, bucket_id, request)

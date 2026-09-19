"""存储对象管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.storage_object import ObjectRegister, ObjectStatusUpdate, ObjectUpdate
from app.services.storage_object import StorageObjectService

router = APIRouter(prefix="/api/storage/objects", tags=["storage-objects"])


@router.get("")
async def list_objects(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    bucket_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StorageObjectService.list_objects(
        session, limit=limit, offset=offset, bucket_id=bucket_id,
        status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_object(
    payload: ObjectRegister, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StorageObjectService.register_object(session, payload, request)


@router.get("/{object_id}")
async def get_object(
    object_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StorageObjectService.get_object(session, object_id)


@router.patch("/{object_id}")
async def update_object(
    object_id: str, payload: ObjectUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StorageObjectService.update_object(session, object_id, payload, request)


@router.patch("/{object_id}/status")
async def update_object_status(
    object_id: str, payload: ObjectStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StorageObjectService.update_status(session, object_id, payload.status, request)


@router.delete("/{object_id}", status_code=status.HTTP_200_OK)
async def delete_object(
    object_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await StorageObjectService.delete_object(session, object_id, request)

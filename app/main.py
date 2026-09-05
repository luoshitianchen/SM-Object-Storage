"""SM Object Storage —— 企业对象存储：桶、对象存取、元数据与 SM3 完整性校验。"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-object-storage"
VERSION = "3.0.0"
NAME = "SM Object Storage"
DESCRIPTION = "企业对象存储：桶、对象存取、元数据与 SM3 完整性校验"
PORT = 8420


def _now() -> str:
    return datetime.now(UTC).isoformat()


def storage_dir() -> Path:
    return Path(os.getenv("SM_STORAGE_DIR", "data/objects"))


def _safe_object_path(bucket: str, object_key: str) -> Path:
    """对象键经规范化后必须位于存储根/桶目录内，杜绝路径遍历（任意文件读写删）。"""
    if not object_key or "\x00" in object_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法的对象键")
    if any(seg in ("", ".", "..") for seg in object_key.replace("\\", "/").split("/")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法的对象键")
    base_dir = (storage_dir() / bucket).resolve()
    target = (base_dir / object_key).resolve()
    if target != base_dir and base_dir not in target.parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法的对象键")
    return target


def _init() -> None:
    storage_dir().mkdir(parents=True, exist_ok=True)
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS buckets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, owner TEXT NOT NULL,
                policy TEXT NOT NULL DEFAULT 'private', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS objects (
                id TEXT PRIMARY KEY, bucket TEXT NOT NULL, key TEXT NOT NULL,
                size INTEGER NOT NULL, sm3 TEXT NOT NULL, content_type TEXT DEFAULT 'application/octet-stream',
                created_at TEXT NOT NULL, UNIQUE(bucket, key)
            );
            CREATE INDEX IF NOT EXISTS idx_objects_bucket ON objects(bucket, key);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-audit-log-center"],
    events=["bucket.created", "object.put", "object.deleted"],
    overview_fn=lambda _r: {
        "summary": {
            "buckets": base.get_db().execute("SELECT COUNT(*) FROM buckets").fetchone()[0],
            "objects": base.get_db().execute("SELECT COUNT(*) FROM objects").fetchone()[0],
        }
    },
)
_init()


class BucketIn(BaseModel):
    name: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9.-]{1,78}[a-z0-9]$")
    owner: str = Field(default="平台工程部", min_length=1, max_length=80)
    policy: str = Field(default="private", pattern=r"^(private|public-read)$")


@app.get("/api/storage/buckets")
def list_buckets() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM buckets ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/storage/buckets", status_code=status.HTTP_201_CREATED)
def create_bucket(payload: BucketIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    bucket_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO buckets VALUES (?,?,?,?,?)", (bucket_id, payload.name, payload.owner, payload.policy, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "桶已存在") from exc
        base.record_audit("bucket.created", "internal", f"bucket={payload.name}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    (storage_dir() / payload.name).mkdir(parents=True, exist_ok=True)
    return {"id": bucket_id, "name": payload.name}


@app.put("/api/storage/buckets/{bucket}/objects/{object_key:path}")
async def put_object(bucket: str, object_key: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    body = await request.body()
    if len(body) > 64 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "对象超过 64MiB 上限")
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM buckets WHERE name=?", (bucket,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "桶不存在")
        obj_id = str(uuid.uuid4())
        digest = base.sm3_hex(body)
        content_type = request.headers.get("content-type", "application/octet-stream")
        conn.execute(
            "INSERT INTO objects (id, bucket, key, size, sm3, content_type, created_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(bucket, key) DO UPDATE SET size=excluded.size, sm3=excluded.sm3, content_type=excluded.content_type, created_at=excluded.created_at",
            (obj_id, bucket, object_key, len(body), digest, content_type, _now()),
        )
        base.record_audit("object.put", "internal", f"bucket={bucket} key={object_key} bytes={len(body)}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    target = _safe_object_path(bucket, object_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {"bucket": bucket, "key": object_key, "size": len(body), "sm3": digest, "etag": digest[:16]}


@app.get("/api/storage/buckets/{bucket}/objects/{object_key:path}")
def get_object(bucket: str, object_key: str) -> Response:
    target = _safe_object_path(bucket, object_key)
    if not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM objects WHERE bucket=? AND key=?", (bucket, object_key)).fetchone()
    content_type = row["content_type"] if row else "application/octet-stream"
    return Response(content=target.read_bytes(), media_type=content_type, headers={"ETag": f"\"{row['sm3'][:16] if row else ''}\"", "X-Object-SM3": row["sm3"] if row else ""})


@app.head("/api/storage/buckets/{bucket}/objects/{object_key:path}")
def head_object(bucket: str, object_key: str) -> Response:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM objects WHERE bucket=? AND key=?", (bucket, object_key)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
    return Response(status_code=200, headers={"X-Object-Size": str(row["size"]), "X-Object-SM3": row["sm3"], "Content-Type": row["content_type"]})


@app.delete("/api/storage/buckets/{bucket}/objects/{object_key:path}")
def delete_object(bucket: str, object_key: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if conn.execute("DELETE FROM objects WHERE bucket=? AND key=?", (bucket, object_key)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "对象不存在")
        base.record_audit("object.deleted", "internal", f"bucket={bucket} key={object_key}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    target = _safe_object_path(bucket, object_key)
    if target.is_file():
        target.unlink()
    return {"deleted": True, "bucket": bucket, "key": object_key}


@app.get("/api/storage/buckets/{bucket}/objects")
def list_objects(bucket: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM buckets WHERE name=?", (bucket,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "桶不存在")
        rows = conn.execute("SELECT * FROM objects WHERE bucket=? ORDER BY created_at DESC", (bucket,)).fetchall()
    return {"bucket": bucket, "items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/storage/status")
def storage_status() -> dict[str, Any]:
    with base.db_ctx() as conn:
        total_bytes = conn.execute("SELECT COALESCE(SUM(size),0) FROM objects").fetchone()[0]
        total_objects = conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
        total_buckets = conn.execute("SELECT COUNT(*) FROM buckets").fetchone()[0]
    return {"buckets": total_buckets, "objects": total_objects, "total_bytes": int(total_bytes), "storage_dir": str(storage_dir())}
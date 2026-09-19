"""对象存储业务深化测试：桶/对象/生命周期规则全生命周期。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _mk_bucket(client, name="docs-bucket", **extra):
    payload = {"name": name, **extra}
    return await client.post("/api/storage/buckets", json=payload, headers=H)


# ═══════════════════════════════════════════════════════════
# 存储桶
# ═══════════════════════════════════════════════════════════

class TestBucketManagement:
    async def test_create_bucket_success(self, client):
        resp = await _mk_bucket(client, "order-bucket")
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "order-bucket"
        assert data["status"] == "active"
        assert data["storage_class"] == "standard"
        assert "id" in data

    async def test_create_bucket_requires_token(self, client):
        resp = await client.post("/api/storage/buckets", json={"name": "noauth-bucket"})
        assert resp.status_code in (401, 403)

    async def test_create_bucket_duplicate_name(self, client):
        await _mk_bucket(client, "dup-bucket")
        resp = await _mk_bucket(client, "dup-bucket")
        assert resp.status_code == 409

    async def test_create_bucket_invalid_name_rejected(self, client):
        resp = await _mk_bucket(client, "Bad_Name")
        assert resp.status_code == 422

    async def test_list_buckets(self, client):
        await _mk_bucket(client, "list-bucket")
        resp = await client.get("/api/storage/buckets", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_buckets_keyword_filter(self, client):
        await _mk_bucket(client, "kw-unique-bucket")
        resp = await client.get("/api/storage/buckets?keyword=kw-unique", headers=H)
        assert resp.status_code == 200
        names = [b["name"] for b in resp.json()["items"]]
        assert "kw-unique-bucket" in names

    async def test_get_bucket(self, client):
        create = await _mk_bucket(client, "get-bucket")
        bid = create.json()["id"]
        resp = await client.get(f"/api/storage/buckets/{bid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["id"] == bid

    async def test_get_bucket_not_found(self, client):
        resp = await client.get("/api/storage/buckets/nope", headers=H)
        assert resp.status_code == 404

    async def test_update_bucket(self, client):
        create = await _mk_bucket(client, "upd-bucket")
        bid = create.json()["id"]
        resp = await client.patch(f"/api/storage/buckets/{bid}", json={
            "storage_class": "archive", "versioning_enabled": True,
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["storage_class"] == "archive"
        assert resp.json()["versioning_enabled"] is True

    async def test_bucket_state_transition_valid(self, client):
        create = await _mk_bucket(client, "state-bucket")
        bid = create.json()["id"]
        resp = await client.patch(f"/api/storage/buckets/{bid}/status",
                                  json={"status": "locked"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "locked"

    async def test_bucket_state_transition_invalid(self, client):
        create = await _mk_bucket(client, "badstate-bucket")
        bid = create.json()["id"]
        # active -> deleted 需空桶，先直接尝试非法跳过：active->locked->active 合法；
        # 这里验证 deleted 为终态不可迁出
        await client.patch(f"/api/storage/buckets/{bid}/status",
                           json={"status": "locked"}, headers=H)
        await client.patch(f"/api/storage/buckets/{bid}/status",
                           json={"status": "active"}, headers=H)
        resp = await client.patch(f"/api/storage/buckets/{bid}/status",
                                  json={"status": "deleted"}, headers=H)
        assert resp.status_code == 200
        # 已删除桶不可再迁移
        resp2 = await client.patch(f"/api/storage/buckets/{bid}/status",
                                   json={"status": "active"}, headers=H)
        assert resp2.status_code == 409


# ═══════════════════════════════════════════════════════════
# 存储对象
# ═══════════════════════════════════════════════════════════

class TestObjectManagement:
    async def _bucket_id(self, client, name="obj-bucket"):
        r = await _mk_bucket(client, name)
        return r.json()["id"]

    async def test_register_object_success(self, client):
        bid = await self._bucket_id(client, "reg-obj-bucket")
        resp = await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "a/b/c.txt", "size_bytes": 1024,
            "etag": "abc123",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["object_key"] == "a/b/c.txt"
        assert data["status"] == "active"

    async def test_register_object_requires_token(self, client):
        bid = await self._bucket_id(client, "notoken-obj-bucket")
        resp = await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "x.txt",
        })
        assert resp.status_code in (401, 403)

    async def test_register_object_nonexistent_bucket(self, client):
        resp = await client.post("/api/storage/objects", json={
            "bucket_id": "missing", "object_key": "x.txt",
        }, headers=H)
        assert resp.status_code == 404

    async def test_register_object_duplicate_key(self, client):
        bid = await self._bucket_id(client, "dup-obj-bucket")
        body = {"bucket_id": bid, "object_key": "same/key.txt"}
        await client.post("/api/storage/objects", json=body, headers=H)
        resp = await client.post("/api/storage/objects", json=body, headers=H)
        assert resp.status_code == 409

    async def test_list_objects_filter_by_bucket(self, client):
        bid = await self._bucket_id(client, "filter-obj-bucket")
        await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "filtered/1.log",
        }, headers=H)
        resp = await client.get(f"/api/storage/objects?bucket_id={bid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1
        assert all(o["bucket_id"] == bid for o in resp.json()["items"])

    async def test_list_objects_keyword_search(self, client):
        bid = await self._bucket_id(client, "search-obj-bucket")
        await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "searchable/special.txt",
        }, headers=H)
        resp = await client.get("/api/storage/objects?keyword=searchable", headers=H)
        assert resp.status_code == 200
        keys = [o["object_key"] for o in resp.json()["items"]]
        assert any("searchable" in k for k in keys)

    async def test_get_object_not_found(self, client):
        resp = await client.get("/api/storage/objects/nope", headers=H)
        assert resp.status_code == 404

    async def test_update_object(self, client):
        bid = await self._bucket_id(client, "upd-obj-bucket")
        create = await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "upd.txt", "size_bytes": 10,
        }, headers=H)
        oid = create.json()["id"]
        resp = await client.patch(f"/api/storage/objects/{oid}", json={
            "size_bytes": 2048, "storage_class": "infrequent",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["size_bytes"] == 2048
        assert resp.json()["storage_class"] == "infrequent"

    async def test_object_state_transition(self, client):
        bid = await self._bucket_id(client, "state-obj-bucket")
        create = await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "arch.txt",
        }, headers=H)
        oid = create.json()["id"]
        resp = await client.patch(f"/api/storage/objects/{oid}/status",
                                  json={"status": "archived"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    async def test_object_delete(self, client):
        bid = await self._bucket_id(client, "del-obj-bucket")
        create = await client.post("/api/storage/objects", json={
            "bucket_id": bid, "object_key": "trash.txt",
        }, headers=H)
        oid = create.json()["id"]
        resp = await client.delete(f"/api/storage/objects/{oid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


# ═══════════════════════════════════════════════════════════
# 生命周期规则
# ═══════════════════════════════════════════════════════════

class TestLifecycleManagement:
    async def _bucket_id(self, client, name="lc-bucket"):
        r = await _mk_bucket(client, name)
        return r.json()["id"]

    async def test_create_rule_success(self, client):
        bid = await self._bucket_id(client, "lc-ok-bucket")
        resp = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "旧日志清理", "prefix": "logs/",
            "expiration_days": 30, "transitions": ["archive"],
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "旧日志清理"
        assert data["status"] == "enabled"
        assert "archive" in data["transitions"]

    async def test_create_rule_requires_token(self, client):
        bid = await self._bucket_id(client, "lc-notoken-bucket")
        resp = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "x",
        })
        assert resp.status_code in (401, 403)

    async def test_create_rule_nonexistent_bucket(self, client):
        resp = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": "missing", "name": "x",
        }, headers=H)
        assert resp.status_code == 404

    async def test_create_rule_invalid_transition(self, client):
        bid = await self._bucket_id(client, "lc-badtrans-bucket")
        resp = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "bad", "transitions": ["glacier"],
        }, headers=H)
        assert resp.status_code == 400

    async def test_create_rule_duplicate_prefix(self, client):
        bid = await self._bucket_id(client, "lc-dup-bucket")
        body = {"bucket_id": bid, "name": "r1", "prefix": "dup/"}
        await client.post("/api/storage/lifecycle-rules", json=body, headers=H)
        resp = await client.post("/api/storage/lifecycle-rules", json=body, headers=H)
        assert resp.status_code == 409

    async def test_list_rules_filter_status(self, client):
        bid = await self._bucket_id(client, "lc-list-bucket")
        await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "en-rule", "prefix": "en/",
        }, headers=H)
        resp = await client.get("/api/storage/lifecycle-rules?status=enabled", headers=H)
        assert resp.status_code == 200
        assert all(r["status"] == "enabled" for r in resp.json()["items"])

    async def test_toggle_rule_status(self, client):
        bid = await self._bucket_id(client, "lc-toggle-bucket")
        create = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "tog", "prefix": "tog/",
        }, headers=H)
        rid = create.json()["id"]
        resp = await client.patch(f"/api/storage/lifecycle-rules/{rid}/status",
                                  json={"status": "disabled"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    async def test_update_rule(self, client):
        bid = await self._bucket_id(client, "lc-upd-bucket")
        create = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "upd", "prefix": "upd/", "expiration_days": 10,
        }, headers=H)
        rid = create.json()["id"]
        resp = await client.patch(f"/api/storage/lifecycle-rules/{rid}",
                                  json={"expiration_days": 90}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["expiration_days"] == 90

    async def test_delete_rule(self, client):
        bid = await self._bucket_id(client, "lc-del-bucket")
        create = await client.post("/api/storage/lifecycle-rules", json={
            "bucket_id": bid, "name": "del", "prefix": "del/",
        }, headers=H)
        rid = create.json()["id"]
        resp = await client.delete(f"/api/storage/lifecycle-rules/{rid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

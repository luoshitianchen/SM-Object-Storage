"""SM Object Storage 领域测试：桶、对象存取、元数据、SM3 完整性与删除。"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    tmp = tempfile.mkdtemp(prefix="sm-store-")
    import app.main as m
    monkeypatch.setattr(m, "storage_dir", lambda: Path(tmp))
    base.reset_state()
    m._init()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_bucket_lifecycle(client):
    assert client.post("/api/storage/buckets", json={"name": "assets", "owner": "平台部"}).status_code == 201
    assert client.post("/api/storage/buckets", json={"name": "assets"}).status_code == 409
    assert client.get("/api/storage/buckets").json()["total"] == 1


def test_object_put_get_head_delete(client):
    client.post("/api/storage/buckets", json={"name": "docs"})
    put = client.put("/api/storage/buckets/docs/objects/reports/q1.txt", content=b"hello-object", headers={"Content-Type": "text/plain"})
    assert put.status_code == 200
    assert put.json()["size"] == 12
    assert len(put.json()["sm3"]) == 64
    got = client.get("/api/storage/buckets/docs/objects/reports/q1.txt")
    assert got.content == b"hello-object"
    assert got.headers["X-Object-SM3"] == put.json()["sm3"]
    head = client.head("/api/storage/buckets/docs/objects/reports/q1.txt")
    assert head.headers["X-Object-Size"] == "12"
    assert client.get("/api/storage/buckets/docs/objects").json()["total"] == 1
    assert client.delete("/api/storage/buckets/docs/objects/reports/q1.txt").json()["deleted"] is True
    assert client.get("/api/storage/buckets/docs/objects").json()["total"] == 0


def test_object_404(client):
    client.post("/api/storage/buckets", json={"name": "docs"})
    assert client.get("/api/storage/buckets/docs/objects/missing.txt").status_code == 404
    assert client.get("/api/storage/buckets/nonexist/objects/x.txt").status_code == 404


def test_object_key_traversal_rejected(client):
    """路径遍历（.. / 编码 .. / 反斜杠 / 绝对路径）必须被拒绝，杜绝任意文件读写删。"""
    client.post("/api/storage/buckets", json={"name": "docs"})
    # 客户端规范化后仍能到达处理器、必须返回 400 的形态
    for key in ("..%2f..%2foutside.txt", "%2e%2e%2f%2e%2e%2foutside.txt", "..\\..\\win.txt", "a%2f..%2f..%2fx"):
        r = client.put(f"/api/storage/buckets/docs/objects/{key}", content=b"x")
        assert r.status_code == 400, f"PUT 应拒绝 {key!r}, got {r.status_code}"
        g = client.get(f"/api/storage/buckets/docs/objects/{key}")
        assert g.status_code in (400, 404), f"GET 应拒绝/未命中 {key!r}, got {g.status_code}"
    # 字面 .. 会被 HTTP 客户端规范化导致路由不命中（404）——同样不可利用；绝对路径同理
    for key in ("../outside.txt", "a/../../outside.txt", "/etc/passwd", "a/../../../tmp/x"):
        assert client.put(f"/api/storage/buckets/docs/objects/{key}", content=b"x").status_code in (400, 404), key


def test_status(client):
    client.post("/api/storage/buckets", json={"name": "docs"})
    client.put("/api/storage/buckets/docs/objects/a.txt", content=b"abc")
    status = client.get("/api/storage/status").json()
    assert status["objects"] == 1
    assert status["total_bytes"] == 3


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.put("/api/storage/buckets/docs/objects/a.txt", content=b"x").status_code == 401

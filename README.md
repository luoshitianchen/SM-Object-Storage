# SM Object Storage

企业对象存储中心：文件、附件、归档和备份对象管理。

```powershell
git clone https://github.com/luoshitianchen/SM-Object-Storage.git
cd SM-Object-Storage
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8420
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。

内置 TrustedHost、安全响应头、CSP、国密状态接口和容器加固。

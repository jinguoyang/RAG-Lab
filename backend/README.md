# RAG-Lab 后端工程

## 工程定位

`backend/` 是 RAG-Lab 的 FastAPI 后端工程入口。

当前阶段已搭建最小应用骨架，并开始接入 PostgreSQL 迁移基础；文档上传链路已预留 MinIO 原始文件存储 Provider，Redis、Milvus、OpenSearch、Neo4j 或模型服务仍按后续 Sprint 逐步接入。

## 本地运行

启动条件：

- 本机已安装 Conda。
- 已创建项目专属环境 `rag-lab`。
- 在 `backend/` 目录执行后端命令。

### 1. 创建 Conda 环境

本项目后端使用专属 Conda 环境 `rag-lab`。

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda env create -f environment.yml
```

如果环境已经存在，更新依赖：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda env update -f environment.yml --prune
```

### 2. 启动后端

推荐使用启动脚本：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
.\scripts\start-dev.ps1
```

也可以手动启动：

```powershell
conda activate rag-lab
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
python -m uvicorn app.main:app --reload
```

启动后可访问：

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

### 3. 执行数据库迁移

迁移使用 Alembic，数据库连接从 `RAG_LAB_DATABASE_URL` 或 `DATABASE_URL` 读取。初始化本地 `.env` 后，按实际 PostgreSQL 地址调整连接串：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
.\scripts\migrate.ps1
```

也可以手动执行：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m alembic upgrade head
```

当前 E1 迁移会创建 `users`、`user_groups`、`user_group_members`、`knowledge_bases` 基础表，并写入开发期默认用户和默认知识库。
当前 E2 迁移会创建 `stored_files`、`documents`、`document_versions`、`ingest_jobs`，用于文档中心最小上传与作业追踪链路。

更完整的 E1 初始化与联调说明见：[E1 本地验证说明](../docs/04-迭代与交付/E1-本地验证说明.md)。
更完整的 E2 文档中心验证说明见：[E2 本地验证说明](../docs/04-迭代与交付/E2-本地验证说明.md)。

## 最小验证

提交前至少运行：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python -m alembic current
conda run -n rag-lab python -c "from fastapi.testclient import TestClient; from app.main import app; r=TestClient(app).get('/api/v1/health'); print(r.status_code); print(r.json())"
conda run -n rag-lab python -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); print(c.get('/api/v1/auth/me').status_code); print(c.get('/api/v1/knowledge-bases').status_code)"
conda run -n rag-lab python -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); kb=c.get('/api/v1/knowledge-bases').json()['items'][0]['kbId']; print(c.get(f'/api/v1/knowledge-bases/{kb}/documents').status_code); print(c.get(f'/api/v1/knowledge-bases/{kb}/ingest-jobs').status_code)"
```

验证通过标准：

- Python 编译无错误。
- Alembic 能读取迁移配置并连接数据库。
- `/api/v1/health` 返回 `200`。
- `/api/v1/auth/me` 和 `/api/v1/knowledge-bases` 返回 `200`。
- `/api/v1/knowledge-bases/{kbId}/documents` 和 `/api/v1/knowledge-bases/{kbId}/ingest-jobs` 返回 `200`。
- 响应包含 `status`、`app_name`、`version`、`environment`。

## 目录结构

```text
backend/
├── app/
│   ├── api/          # API 路由聚合
│   ├── core/         # 配置、日志、安全等基础能力
│   ├── schemas/      # 请求/响应 Schema
│   ├── services/     # 业务服务层
│   └── main.py       # FastAPI 应用入口
├── scripts/
│   └── start-dev.ps1 # 本地开发启动脚本
├── .env.example      # 本地配置示例
├── environment.yml   # Conda 环境定义
└── requirements.txt  # pip 依赖清单，由 environment.yml 引用
```

## 配置说明

后端配置由 `app/core/config.py` 统一读取，优先使用环境变量，也支持读取 `backend/.env`。

初始化本地配置：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
Copy-Item .env.example .env
```

当前支持的配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `RAG_LAB_APP_NAME` | `RAG-Lab API` | OpenAPI 文档展示的应用名称 |
| `RAG_LAB_APP_VERSION` | `0.1.0` | 应用版本 |
| `RAG_LAB_ENVIRONMENT` | `local` | 运行环境标识 |
| `RAG_LAB_API_V1_PREFIX` | `/api/v1` | v1 API 前缀 |
| `RAG_LAB_BACKEND_CORS_ORIGINS` | `[]` | 前端允许来源，JSON 数组格式 |
| `RAG_LAB_DATABASE_URL` | 空 | PostgreSQL 连接串，供 Alembic 和后续数据库访问使用 |
| `RAG_LAB_DEV_AUTH_ENABLED` | `true` | 是否启用开发期认证占位 |
| `RAG_LAB_DEV_DEFAULT_USERNAME` | `admin` | 默认开发用户 |
| `RAG_LAB_DEV_DEFAULT_SECURITY_LEVEL` | `public` | 默认开发密级，保持开放以便联调 |
| `RAG_LAB_STORAGE_BACKEND` | `metadata` | 对象存储后端，`metadata` 仅记录引用，`minio` 写入 MinIO |
| `RAG_LAB_STORAGE_BUCKET` | `rag-lab-source` | 原始文件对象存储 bucket |
| `RAG_LAB_STORAGE_OBJECT_PREFIX` | `dev` | 原始文件对象 key 前缀 |
| `RAG_LAB_MINIO_ENDPOINT` | 空 | MinIO 服务地址，例如 `127.0.0.1:9000` |
| `RAG_LAB_MINIO_ACCESS_KEY` | 空 | MinIO Access Key |
| `RAG_LAB_MINIO_SECRET_KEY` | 空 | MinIO Secret Key |
| `RAG_LAB_MINIO_SECURE` | `false` | 是否使用 HTTPS 连接 MinIO |

## 开发期认证

当前只实现开发期认证占位，内置两个用户：

| 用户名 | 角色 | 说明 |
| --- | --- | --- |
| `admin` | `platform_admin` | 默认用户，具备开发期管理能力 |
| `user` | `platform_user` | 普通开发用户，用于验证非管理员视角 |

当前用户接口：

```text
GET /api/v1/auth/me
```

默认返回 `admin`。如需临时切换用户，可在请求头中传入：

```text
X-Dev-User: user
```

## 开发约定

- API 层只负责请求解析、鉴权入口和响应组装。
- Service 层负责业务流程和事务边界。
- 后续接入外部组件时优先通过 Provider / Adapter 隔离实现差异。
- `/api/v1/health` 只做服务进程级探活，不探测数据库或外部依赖。

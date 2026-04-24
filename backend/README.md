# RAG-Lab 后端工程

## 工程定位

`backend/` 是 RAG-Lab 的 FastAPI 后端工程入口。

当前阶段只搭建最小应用骨架，不接入 PostgreSQL、Redis、MinIO、Milvus、OpenSearch、Neo4j 或模型服务。后续功能应按 Sprint 计划逐步接入。

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

## 最小验证

提交前至少运行：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python -c "from fastapi.testclient import TestClient; from app.main import app; r=TestClient(app).get('/api/v1/health'); print(r.status_code); print(r.json())"
```

验证通过标准：

- Python 编译无错误。
- `/api/v1/health` 返回 `200`。
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

## 开发约定

- API 层只负责请求解析、鉴权入口和响应组装。
- Service 层负责业务流程和事务边界。
- 后续接入外部组件时优先通过 Provider / Adapter 隔离实现差异。
- `/api/v1/health` 只做服务进程级探活，不探测数据库或外部依赖。

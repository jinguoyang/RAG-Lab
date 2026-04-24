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

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

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
├── environment.yml   # Conda 环境定义
└── requirements.txt  # pip 依赖清单，由 environment.yml 引用
```

## 开发约定

- API 层只负责请求解析、鉴权入口和响应组装。
- Service 层负责业务流程和事务边界。
- 后续接入外部组件时优先通过 Provider / Adapter 隔离实现差异。
- 当前骨架不包含 `/health`，该接口由 S1-004 单独实现。

# RAG-Lab

## 项目说明

本仓库用于承载 RAG 调试平台的需求、原型、设计与后续开发交付物。

当前阶段以“瀑布里程碑 + 敏捷迭代”混合模式推进：

- 瀑布负责阶段关口与评审产物
- 敏捷负责阶段内部的 Sprint 开发与交付

## 项目结构

```text
rag-lab/
├── AGENTS.md                  # Codex / Agent 协作约定
├── DESIGN.md                  # 页面设计与视觉风格要求
├── README.md                  # 项目开发说明入口
├── frontend/                  # 当前正式前端入口，基于 React + Vite
├── backend/                   # FastAPI 后端工程入口
├── docs/                      # 项目文档区
│   ├── 00-项目导航.md
│   ├── 01-项目管理/
│   ├── 02-需求与原型/
│   ├── 03-系统设计/
│   ├── 04-迭代与交付/
│   ├── 05-测试与验收/
│   └── 06-发布与运维/
└── screanshot/
    ├── P01-登录页.png 等       # 设计稿截图
    └── prototype/             # 设计原型归档，保留原型工程
```

说明：

- 当前仓库已落地的是文档、设计原型和正式前端工程入口。
- `frontend/` 从 `screanshot/prototype/` 复制而来，作为正式前端开发入口。
- `screanshot/prototype/` 作为设计原型归档保留，不直接承载正式开发。
- 后端服务、数据库迁移、Worker、部署脚本等目录尚未创建，后续应按系统设计和编码规范小步补齐。

## 文档入口

- [项目导航](./docs/00-项目导航.md)
- [需求规格说明书](./docs/02-需求与原型/需求规格说明书.md)
- [原型设计文档](./docs/02-需求与原型/原型设计文档.md)
- [Figma视觉原型说明](./docs/02-需求与原型/Figma视觉原型说明.md)
- [总体设计说明书](./docs/03-系统设计/总体设计说明书.md)
- [详细设计说明书](./docs/03-系统设计/详细设计说明书.md)
- [接口设计说明](./docs/03-系统设计/接口设计说明.md)
- [数据模型设计](./docs/03-系统设计/数据模型设计.md)
- [数据库设计](./docs/03-系统设计/数据库设计.md)
- [编码规范](./docs/04-迭代与交付/编码规范.md)

## 本地运行方式

### 运行前端

正式前端工程位于 `frontend/`。

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm install
npm run dev
```

启动后按终端输出访问本地 Vite 地址，通常为 `http://localhost:5173`。

### 构建前端

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

当前前端 `package.json` 只定义了 `dev` 和 `build` 脚本，尚未定义 lint 或 test 命令。

### 创建后端 Conda 环境

后端使用项目专属 Conda 环境 `rag-lab`。

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda env create -f environment.yml
```

如果环境已经存在，使用：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda env update -f environment.yml --prune
```

### 启动后端

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
.\scripts\start-dev.ps1
```

启动后访问 `http://127.0.0.1:8000/docs`。

## 依赖说明

### 当前已落地依赖

原型工程使用：

- React 18
- Vite 6
- TypeScript / TSX
- Tailwind CSS 4
- Radix UI 组件族
- MUI icons
- lucide-react
- recharts
- motion
- react-router

正式前端依赖版本以 `frontend/package.json` 和 `package-lock.json` 为准；原型依赖保留在 `screanshot/prototype/`。

后端当前已落地依赖：

- Python 3.12
- FastAPI
- Uvicorn

后端依赖版本以 `backend/environment.yml` 和 `backend/requirements.txt` 为准。

### 设计确定但尚未落代码的依赖

系统设计建议后续实现采用：

- 后端：Python FastAPI
- 任务框架：Celery + Redis
- 主数据库：PostgreSQL
- 对象存储：MinIO
- Dense 检索：Milvus，必要时可评估 pgvector
- Sparse 检索：OpenSearch
- 图数据库：Neo4j
- 模型服务：统一封装 LLM / Embedding / Rerank Provider

这些依赖当前还没有对应工程目录、配置或迁移脚本。实现时应先参考 `docs/03-系统设计/` 下的设计文档，再新增最小必要代码。

## 推荐开发前阅读顺序

1. [项目导航](./docs/00-项目导航.md)
2. [需求规格说明书](./docs/02-需求与原型/需求规格说明书.md)
3. [原型设计文档](./docs/02-需求与原型/原型设计文档.md)
4. [总体设计说明书](./docs/03-系统设计/总体设计说明书.md)
5. [详细设计说明书](./docs/03-系统设计/详细设计说明书.md)
6. [接口设计说明](./docs/03-系统设计/接口设计说明.md)
7. [数据模型设计](./docs/03-系统设计/数据模型设计.md)
8. [数据库设计](./docs/03-系统设计/数据库设计.md)
9. [编码规范](./docs/04-迭代与交付/编码规范.md)

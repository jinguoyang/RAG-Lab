# 外部培训应用（External Training App）

接入 RAG-Lab 平台员工培训 Agent 的轻量演示应用。无 LLM、Embedding 或 RAG 能力，所有智能功能通过平台 API 调用。

## 功能概览

| 功能 | 说明 |
|------|------|
| 平台绑定 | 配置平台地址和 App API Key |
| 学习计划审核 | 展示平台生成的学习计划草稿，支持通过/驳回操作 |
| 题库审核 | 展示平台生成的题目草稿，支持审核 |
| 员工课堂 | 多轮对话、课堂状态流转、A/B/C/D 结构化答题 |

## 项目结构

```text
external-training-app/
├── backend/                    # FastAPI + PostgreSQL 后端
│   ├── app/
│   │   ├── api/routes/         # API 路由（bindings, reviews, classroom, health）
│   │   ├── core/               # 配置与数据库连接
│   │   ├── schemas/            # Pydantic 数据模型
│   │   ├── services/           # 业务逻辑与平台 API 客户端
│   │   ├── tables/             # SQLAlchemy 表定义（6 张表）
│   │   └── main.py             # FastAPI 入口
│   ├── migrations/             # Alembic 数据库迁移
│   │   ├── env.py
│   │   └── versions/           # 迁移版本文件
│   ├── scripts/                # PowerShell 启动脚本
│   ├── alembic.ini
│   ├── .env.example
│   └── requirements.txt
├── frontend/                   # Vite + React + TypeScript 前端
│   ├── src/
│   │   ├── pages/              # 页面组件（BindingPage, ReviewPage, ClassroomPage）
│   │   ├── components/         # UI 组件（ChoiceQuestion）
│   │   ├── services/           # API 调用封装
│   │   ├── types/              # TypeScript 类型定义
│   │   ├── routes.tsx          # 路由配置
│   │   └── App.tsx             # 应用入口
│   └── package.json
└── README.md
```

## 数据库表

| 表名 | 说明 |
|------|------|
| `external_users` | 外部用户 |
| `platform_app_bindings` | 平台 App 绑定配置 |
| `training_review_tasks` | 审核任务记录 |
| `training_class_sessions` | 课堂会话映射 |
| `training_class_messages` | 课堂消息展示记录 |
| `training_answer_records` | 答题提交记录 |

## 本地运行

### 环境前提

- Python 3.12+
- Node.js 18+ 与 npm
- PostgreSQL 可用

### 启动后端

```powershell
cd external-training-app/backend
pip install -r requirements.txt
Copy-Item .env.example .env
# 编辑 .env 配置数据库连接和平台凭据

# 执行数据库迁移
.\scripts\migrate.ps1

# 启动服务
.\scripts\start-dev.ps1
```

linux版本：
```
conda activate rag-lab
cd /data/rag/external-training-app/backend
mkdir -p logs
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > logs/backend.out.log 2> logs/backend.err.log &
```

启动后访问：

- 健康检查：`http://localhost:8001/health`
- API 文档：`http://localhost:8001/docs`

### 启动前端

```powershell
cd external-training-app/frontend
npm install
npm run dev
```

linux版本后台启动
```
cd external-training-app/frontend
npm install
setsid npm run dev -- --host 0.0.0.0 --port 5183 > logs/frontend.out.log 2> logs/frontend.err.log < /dev/null &
```

启动后访问 `http://localhost:5173`。前端通过 Vite proxy 将 `/api` 请求转发到后端 `localhost:8001`。

### 环境变量

后端支持以下环境变量（前缀 `EXT_TRAINING_`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EXT_TRAINING_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/external_training` | PostgreSQL 连接串 |
| `EXT_TRAINING_PLATFORM_BASE_URL` | `http://localhost:8000/api/v1` | 平台 API 地址 |
| `EXT_TRAINING_PLATFORM_API_KEY` | 空 | 平台 App API Key；平台根据 Key 反查所属 App |

### 验证

```powershell
# 后端编译
cd external-training-app/backend
python -c "from app.main import app; print('OK')"

# 前端构建
cd external-training-app/frontend
npm run build
```

## 关键边界

本应用**不**具备以下能力：

- 不调用 LLM、Embedding 或 RAG Provider
- 不访问向量库、图数据库或 OpenSearch
- 不保存文档正文、Chunk 正文或 RAG Trace
- 不自行决定课堂业务状态流转
- 不实现完整 LMS、证书或组织学习档案

所有智能功能通过平台 `/api/v1/training/` 接口调用。外部应用只在服务端保存 App API Key，请求体不携带 `appId`。

## 页面路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | 学习计划审核 | 生成草稿、查看、审核 |
| `/bindings` | 平台绑定 | 配置平台连接信息 |
| `/reviews` | 学习计划审核 | 同 `/` |
| `/classroom` | 员工课堂 | 多轮对话、状态流转、答题 |

## 关联文档

- [外部培训应用设计规范](../docs/04-迭代与交付/specs/2026-05-26-external-training-app-design.md)
- [平台侧设计规范](../docs/04-迭代与交付/specs/2026-05-26-employee-training-agent-platform-design.md)
- [实施计划](../docs/04-迭代与交付/plans/2026-05-26-employee-training-agent-and-external-app.md)

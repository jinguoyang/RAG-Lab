# 迭代计划 Sprint 01

## 1. Sprint 基本信息

- Sprint 名称：Sprint 01
- Sprint 主题：工程启动与最小运行链路
- 时间范围：待定
- 目标：建立可本地启动、可健康检查、可继续扩展的前后端工程骨架。

## 2. 本 Sprint 目标

- 明确正式前端工程入口，在保留 `screanshot/prototype` 原型归档的前提下建立 `frontend/`。
- 搭建 FastAPI 后端工程骨架，形成清晰的应用入口、配置加载和路由结构。
- 提供 `.env.example`，记录本地开发必需配置。
- 实现后端 `/health` 健康检查接口。
- 更新本地启动说明，保证新人可以按 README 启动最小工程。

## 3. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S1-001 | B-001 | 建立正式前端工程入口或明确 prototype 演进路径 | P0 | 0.5d |  | Done |
| S1-002 | B-002 | 搭建 FastAPI 后端工程骨架 | P0 | 1d |  | Done |
| S1-003 | B-003 | 增加后端配置加载与 `.env.example` | P0 | 0.5d |  | Done |
| S1-004 | B-004 | 实现 `/health` 健康检查接口 | P0 | 0.5d |  | Todo |
| S1-005 | B-005 | 补充前后端本地启动说明和最小验证命令 | P0 | 0.5d |  | Todo |

## 4. 验收标准

- 前端运行方式明确，README 中有可执行命令。
- 后端应用可以本地启动。
- `/health` 返回服务状态、版本或运行环境等基础信息。
- 本地配置使用 `.env.example` 说明，不提交真实密钥。
- 本 Sprint 不接入真实 PostgreSQL、MinIO、Milvus、OpenSearch、Neo4j 或 LLM 服务，除非它们成为健康检查的最小必要依赖。
- `git diff` 不包含无关文档重排、依赖升级或设计范围外改动。

## 5. 风险与阻塞

- 如果正式前端目录与现有 prototype 的关系不明确，可能导致后续重复搬迁页面。
- 如果过早接入多存储组件，Sprint 01 容易从工程启动变成环境排障。
- 后端技术栈虽然已建议为 FastAPI，但具体包管理工具和目录模板需要在实现时选择最小方案。

## 6. Sprint 输出物

- 前端工程入口决策记录。
- 后端 FastAPI 最小工程。
- `.env.example`。
- `/health` 接口。
- 更新后的 README 本地开发说明。

## 7. 后续衔接

Sprint 01 完成后，从 [产品待办清单](./产品待办清单.md) 中优先选择 E1 用户与知识库基础相关条目进入下一轮 Sprint。

## 8. 决策记录

### S1-001 前端工程入口

- 决策：新增 `frontend/` 作为正式前端入口，保留 `screanshot/prototype/` 作为设计原型归档。
- 原因：复制现有 prototype 可以复用 Vite、React、TypeScript、路由、样式和页面资产，同时避免正式开发污染原型目录。
- 已完成：复制 prototype 到 `frontend/`，排除 `node_modules` 和 `dist`；将正式前端包名设为 `@rag-lab/frontend`；补充 `frontend/README.md`；在根 README 中明确前端入口。
- 后续：正式前端开发只改 `frontend/`；除非同步设计原型，不直接修改 `screanshot/prototype/`。

### S1-002 后端工程骨架

- 决策：新增 `backend/` 作为 FastAPI 后端工程入口。
- 范围：本任务只建立应用入口、路由聚合、基础分层目录和依赖声明，不接入数据库、中间件或外部 Provider。
- 已完成：新增 `backend/app/main.py`、`api/`、`core/`、`schemas/`、`services/`、`requirements.txt`、`environment.yml` 和本地启动脚本。
- 环境：后端使用项目专属 Conda 环境 `rag-lab`，不使用 base 或共享环境。
- 后续：S1-003 补充配置加载与 `.env.example`，S1-004 单独实现 `/health`。

### S1-003 后端配置加载

- 决策：使用 `pydantic-settings` 管理后端配置，配置来源为默认值、环境变量和 `backend/.env`。
- 范围：只加入应用名、版本、运行环境、API 前缀和 CORS 来源占位，不提前加入数据库或外部 Provider 配置。
- 已完成：新增 `backend/app/core/config.py` 和 `backend/.env.example`，并让 FastAPI 应用从配置读取标题、版本和 API 前缀。
- 后续：S1-004 的 `/health` 可读取配置中的应用版本和运行环境。

# 迭代计划 Sprint 36

## 1. Sprint 基本信息

- Sprint 名称：Sprint 36
- Sprint 主题：文档库功能 - Phase 1 基础框架 + Phase 2 文档解析
- 涉及 Epic：E28 文档库功能
- 建议版本：文档库 V1.0
- 时间范围：待定
- 目标：建立个人文档库核心功能，实现文档上传、存储、文本提取和在线预览，为后续知识库关联奠定基础。

## 2. 关键假设

- PostgreSQL、MinIO 对象存储和 Celery 异步任务已部署就绪。
- 前端工程已建立，支持新增页面和依赖安装。
- 文档格式预览采用开源组件方案（PDF Viewer、Markdown 解析等），不涉及后端转 PDF。
- 本 Sprint 只实现 owner 级最小访问控制；完整权限码收口、大文件断点续传和性能优化作为 Sprint 38 后续任务。
- 新旧流程并行，本 Sprint 只定义兼容迁移策略，不执行历史知识库文档数据的一次性迁移。

## 3. 本 Sprint 目标

- 完成数据库设计，实现 documents 表解耦 kb_id 和新建 document_kb_bindings、library_parse_jobs 表。
- 实现文档上传、列表、详情 API，支持用户私有文档存储。
- 完成文档库首页和详情页基础前端页面。
- 实现文本提取异步服务和预览数据生成。
- 接入 PDF 和 Markdown 在线预览组件。
- 建立 Sprint 36 最小验收脚本，覆盖上传、列表、详情、文本提取和 owner 访问边界。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S36-001 | B-162 | 设计并创建数据库迁移脚本 | P0 | 1d | Codex | Todo |
| S36-002 | B-163 | 实现文档库上传 API | P0 | 1.5d | Codex | Todo |
| S36-003 | B-164 | 实现文档库列表/详情 API | P0 | 1d | Codex | Todo |
| S36-004 | B-165 | 对象存储路径适配 | P0 | 0.5d | Codex | Todo |
| S36-005 | B-166 | 文档库首页前端页面（P15） | P0 | 2d | Codex | Todo |
| S36-006 | B-167 | 文档详情页基础版（P16） | P0 | 1d | Codex | Todo |
| S36-007 | B-168 | 文档解析服务重构 | P0 | 2d | Codex | Todo |
| S36-008 | B-169 | Celery 任务：文档库解析 | P0 | 1d | Codex | Todo |
| S36-009 | B-170 | PDF 在线预览组件 | P0 | 1d | Codex | Todo |
| S36-010 | B-171 | Markdown 在线预览组件 | P0 | 0.5d | Codex | Todo |
| S36-011 | B-186 | Sprint 36 最小验收脚本 | P1 | 0.5d | Codex | Todo |

## 5. 验收标准

- 数据库迁移脚本可以引入 `owner_id`、`document_kb_bindings` 和 `library_parse_jobs`，并明确历史 `kb_id` 数据的兼容策略。
- 文档上传 API 返回 document_id，文件存储在 `users/{user_id}/library/{doc_id}/` 路径下。
- 文档列表分页只返回当前用户自己的文档，详情接口拒绝访问非 owner 文档。
- P15 可以展示文档列表、支持上传新文件和基本搜索。
- P16 可以展示文档详情、元数据和预览数据占位。
- 文本提取异步任务至少可以处理 PDF 和 Markdown 示例文档，生成纯文本结果和预览状态。
- PDF 和 Markdown 预览组件可在 P16 正确渲染示例文档。

## 6. 范围边界

- 不完成完整权限码与角色映射收口（Sprint 38），但本 Sprint 必须实现 owner 级最小访问控制。
- 不支持文件夹/标签分类（后续扩展）。
- 不涉及大文件断点续传和上传进度详细反馈（Phase 4 优化）。
- 不支持文档版本管理（扩展功能）。
- 不覆盖 Excel 预览（P2 优先级，留给后续任务）。
- 不涉及文档与知识库绑定流程（Phase 3 任务）。

## 7. 验证命令

- 后端数据库迁移：在 `backend` 目录运行 `conda run -n rag-lab alembic upgrade head`
- 后端编译检查：在 `backend` 目录运行 `conda run -n rag-lab python -m compileall app`
- 文档上传验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_upload.py`（随本 Sprint 新增）
- 文档列表/详情验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_crud.py`（随本 Sprint 新增）
- 文本提取验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_parsing.py`（随本 Sprint 新增）
- 前端构建：在 `frontend` 目录运行 `npm run build`
- 前端预览测试：在浏览器中打开 `http://localhost:3000/library` 和 `/library/:docId`
- OpenAPI 导出：在 `backend` 目录运行 `conda run -n rag-lab python scripts/export_openapi.py`
- 文档空白检查：`git diff --check`

## 8. 执行记录

待执行。

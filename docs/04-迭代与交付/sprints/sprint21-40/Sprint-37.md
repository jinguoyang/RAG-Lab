# 迭代计划 Sprint 37

## 1. Sprint 基本信息

- Sprint 名称：Sprint 37
- Sprint 主题：文档库功能 - Phase 2 预览完善 + Phase 3 知识库绑定
- 涉及 Epic：E28 文档库功能
- 建议版本：文档库 V1.0
- 时间范围：待定
- 目标：完善在线预览能力（Word、TXT），实现文档与知识库的多对多关联，支持从文档库添加文档到知识库。

## 2. 关键假设

- Sprint 36 的数据模型和基础 API 已完成。
- 文本提取和 Markdown/PDF 预览在 Sprint 36 已通过验收。
- Word 和 TXT 预览采用开源方案（mammoth.js、原生 `<pre>` 等），不涉及复杂格式处理。
- Chunk 生成逻辑复用现有 ingest worker，仅触发时机由"上传时"改为"绑定时"。
- 权限细节在 Sprint 38 收口；本 Sprint 仍必须校验文档 owner 和目标知识库权限。

## 3. 本 Sprint 目标

- 完成 Word（DOCX）和 TXT 在线预览。
- 基于 Sprint 36 的 document_kb_bindings 表实现多对多关联 API 和状态流转。
- 改造知识库文档中心（P06），支持从文档库添加文档。
- 实现绑定后分块向量化流程，复用现有 ingest pipeline。
- 完成文档使用情况查询和展示。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S37-001 | B-172 | TXT 在线预览组件 | P1 | 0.5d | Codex | Todo |
| S37-002 | B-173 | Word 在线预览（mammoth.js） | P1 | 1d | Codex | Todo |
| S37-003 | B-176 | 绑定服务、状态流转和绑定/解绑 API | P0 | 1.5d | Codex | Todo |
| S37-004 | B-177 | 知识库文档中心改造（从文档库添加） | P0 | 1.5d | Codex | Todo |
| S37-005 | B-178 | 绑定后分块向量化流程 | P0 | 2d | Codex | Todo |
| S37-006 | B-179 | 文档使用情况查询 API | P1 | 0.5d | Codex | Todo |
| S37-007 | B-180 | 文档使用情况展示（P16） | P1 | 0.5d | Codex | Todo |
| S37-008 | B-186 | Sprint 37 绑定链路验收脚本 | P1 | 0.5d | Codex | Todo |

## 5. 验收标准

- TXT 预览可在 P16 正确显示纯文本和等宽字体。
- Word（DOCX）预览可通过 mammoth.js 转换为 HTML 并展示段落、列表、表格等基础格式。
- document_kb_bindings 表包含 document_id、kb_id、chunk_size、chunk_overlap 和状态字段。
- 绑定 API 可以在校验文档 owner 和目标知识库权限后建立关联，触发 Chunk 生成任务。
- 解绑 API 可以移除关联，并清理相关索引。
- P06 文档中心新增"从文档库添加"按钮，可打开文档选择器选择多个文档。
- 绑定时可配置 chunk_size 和 chunk_overlap，触发分块任务并写入 PostgreSQL 和检索副本。
- 文档使用情况 API 返回文档关联的所有知识库及其绑定状态。
- P16 展示该文档被哪些知识库使用及其处理状态。

## 6. 范围边界

- 不支持 Excel 预览（P2，推迟到后续 Sprint）。
- 不支持文档版本管理（扩展功能）。
- 不涉及知识库中现有文档迁移（新旧流程并行）。
- 不支持复杂的 Chunk 去重或合并策略（保持简单分块）。
- 不完成完整权限码与角色映射收口（Sprint 38），但不能绕过文档 owner 和知识库权限校验。

## 7. 验证命令

- 数据库迁移：在 `backend` 目录运行 `conda run -n rag-lab alembic upgrade head`
- 绑定 API 验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_binding.py`（随本 Sprint 新增）
- Chunk 生成验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_chunking_after_binding.py`（随本 Sprint 新增）
- 文档使用情况查询脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_document_usage_query.py`（随本 Sprint 新增）
- 前端 P06 改造验证：浏览器打开 `http://localhost:3000/knowledge-bases/:kbId/documents` 验证"从文档库添加"入口
- 前端 P16 使用情况展示：浏览器打开 `http://localhost:3000/library/:docId` 验证使用情况列表
- 前端构建：在 `frontend` 目录运行 `npm run build`
- OpenAPI 导出：在 `backend` 目录运行 `conda run -n rag-lab python scripts/export_openapi.py`
- 文档空白检查：`git diff --check`

## 8. 执行记录

待执行。

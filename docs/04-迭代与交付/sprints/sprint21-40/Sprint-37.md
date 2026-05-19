# 迭代计划 Sprint 37

## 1. Sprint 基本信息

- Sprint 名称：Sprint 37
- Sprint 主题：文档库功能 - Phase 2 预览完善 + Phase 3 知识库绑定
- 涉及 Epic：E28 文档库功能
- 建议版本：文档库 V1.0
- 时间范围：待定
- 目标：完善在线预览能力（Word、TXT），实现文档与知识库的多对多关联，支持从文档库添加文档到知识库，实现删除级联和重试机制。
- 设计文档：`docs/04-迭代与交付/plans/2026-05-19-sprint37-binding-preview.md`

## 2. 关键假设

- Sprint 36 的数据模型和基础 API 已完成。
- 文本提取和 Markdown/PDF 预览在 Sprint 36 已通过验收。
- Word 预览采用前端 mammoth.js 方案（~120KB），保留段落、列表、表格等格式。
- 库侧解析存储完整 parsed_chunks[]，KB ingest 复用已解析结果，跳过重复 parse_document() 调用。
- 分块参数使用目标 KB 的默认 chunk_size/chunk_overlap，不暴露配置。
- 权限细节在 Sprint 38 收口；本 Sprint 仍必须校验文档 owner 和目标知识库权限。

## 3. 本 Sprint 目标

- 新增文本预览 API，支持 preview/full/chunks 三种模式。
- 完成 Word（DOCX）和 TXT 在线预览。
- 改造库侧解析存储，保存完整 parsed_chunks[] 供 KB ingest 复用。
- 基于 document_kb_bindings 表实现绑定/解绑 API 和状态流转。
- 改造 KB ingest pipeline 复用库侧解析结果。
- 改造 P06 支持从文档库添加文档。
- 实现文档删除级联清理（软删除 + 自动解绑 + 异步索引清理）。
- 实现解析重试和绑定重试机制。
- 完成文档使用情况查询和展示。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S37-000 | B-187 | 文本预览 API（preview/full/chunks） | P0 | 0.5d | Codex | Todo |
| S37-001 | B-172 | TXT 在线预览组件 | P1 | 0.5d | Codex | Todo |
| S37-002 | B-173 | Word 在线预览（mammoth.js） | P1 | 1d | Codex | Todo |
| S37-003 | B-188 | 解析结果存储改造（parsed_chunks[]） | P0 | 1d | Codex | Todo |
| S37-004 | B-176 | 绑定服务、绑定/解绑 API | P0 | 1.5d | Codex | Todo |
| S37-005 | B-189 | KB ingest 解析复用 | P0 | 1d | Codex | Todo |
| S37-006 | B-177 | P06 知识库文档中心改造（从文档库添加） | P0 | 1.5d | Codex | Todo |
| S37-007 | B-190 | 文档删除 API（级联清理） | P0 | 1d | Codex | Todo |
| S37-008 | B-191 | 重试机制（解析重试 + 绑定重试） | P0 | 1d | Codex | Todo |
| S37-009 | B-179 | 文档使用情况 API + P16 展示 | P1 | 0.5d | Codex | Todo |
| S37-010 | B-186 | 绑定链路验收脚本 | P1 | 0.5d | Codex | Todo |

**总预估：10d**

## 5. 验收标准

- 文本预览 API 支持 preview（2000 字符）、full（完整文本）和 chunks（结构化 JSON）三种模式。
- TXT 预览可在 P16 正确显示纯文本，基于文本预览 API。
- Word（DOCX）预览可通过 mammoth.js 转换为 HTML 并展示段落、列表、表格等基础格式。
- 库侧 document_versions.metadata 存储完整 parsed_chunks[] 数组。
- KB ingest pipeline 绑定时读取库侧 parsed_chunks，跳过 parse_document() 调用。
- 绑定 API 可以在校验文档 owner 和目标知识库权限后建立关联，触发 ingest 任务。
- 解绑 API 可以移除关联，并清理相关 chunks 和索引。
- P06 文档中心新增"从文档库添加"按钮，可打开文档选择器选择多个文档。
- 文档删除 API 执行软删除并级联解绑所有活跃绑定，异步清理索引。
- 解析失败时 P16 显示"重试解析"按钮，绑定失败时显示"重试绑定"按钮。
- P06 中绑定失败的文档显示"重试"按钮，仅重试 ingest。
- P16 展示该文档被哪些知识库使用及其处理状态。

## 6. 范围边界

- 不支持 Excel 预览（P2，推迟到后续 Sprint）。
- 不支持文档版本管理（扩展功能）。
- 不涉及知识库中现有文档迁移（新旧流程并行）。
- 不支持复杂的 Chunk 去重或合并策略（保持简单分块）。
- 不完成完整权限码与角色映射收口（Sprint 38），但不能绕过文档 owner 和知识库权限校验。
- 不支持批量删除（Sprint 38）。
- 不支持 parse job 分页查询（Sprint 38）。
- 不支持上传文件大小限制（Sprint 38）。
- 不支持审计日志记录（Sprint 38）。

## 7. 验证命令

- 数据库迁移：在 `backend` 目录运行 `conda run -n rag-lab alembic upgrade head`
- 后端编译检查：在 `backend` 目录运行 `conda run -n rag-lab python -m compileall app`
- 文本预览 API 验证：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_text_preview_api.py`（随本 Sprint 新增）
- 绑定链路验收脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_binding.py`（随本 Sprint 新增）
- 解析复用验收脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_parse_reuse.py`（随本 Sprint 新增）
- 删除级联验收脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_delete.py`（随本 Sprint 新增）
- 前端构建：在 `frontend` 目录运行 `npm run build`
- 前端 P06 改造验证：浏览器打开 `http://localhost:3000/knowledge-bases/:kbId/documents` 验证"从文档库添加"入口
- 前端 P16 预览验证：浏览器打开 `http://localhost:3000/library/:docId` 验证文本预览、DOCX 预览和使用情况展示
- OpenAPI 导出：在 `backend` 目录运行 `conda run -n rag-lab python scripts/export_openapi.py`
- 文档空白检查：`git diff --check`

## 8. 执行记录

待执行。

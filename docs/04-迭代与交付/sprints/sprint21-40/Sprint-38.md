# 迭代计划 Sprint 38

## 1. Sprint 基本信息

- Sprint 名称：Sprint 38
- Sprint 主题：文档库功能 - Phase 4 增强功能与优化
- 涉及 Epic：E28 文档库功能
- 建议版本：文档库 V1.0
- 时间范围：待定
- 目标：完善体验和边界情况处理，包括权限适配、批量操作、大文件优化、错误处理和测试覆盖。

## 2. 关键假设

- Sprint 36 和 Sprint 37 的核心功能已完成并通过验收。
- 权限框架已在系统中建立（如 `kb.*` 权限模式可复用）。
- 大文件处理基于现有 MinIO 能力，不涉及复杂的分布式存储架构。
- 测试使用现有的单元测试和集成测试框架（pytest、Jest 等）。

## 3. 本 Sprint 目标

- 适配权限体系，新增 `library.document.*` 权限码。
- 支持批量删除、批量重新解析、批量停用文档。
- 添加文档库统计卡片到平台首页（P02）。
- 优化大文件处理，改善上传和解析体验。
- 完善错误处理与重试机制。
- 建立全面的单元测试与集成测试。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S38-001 | B-181 | 权限体系适配 | P1 | 1d | Codex | Todo |
| S38-002 | B-182 | 批量操作支持 | P1 | 1d | Codex | Todo |
| S38-003 | B-183 | 文档库统计卡片（P02） | P2 | 0.5d | Codex | Todo |
| S38-004 | B-184 | 大文件处理优化 | P2 | 1d | Codex | Todo |
| S38-005 | B-185 | 错误处理与重试机制 | P1 | 0.5d | Codex | Todo |
| S38-006 | B-186 | 单元测试与集成测试 | P1 | 1d | Codex | Todo |

## 5. 验收标准

- 权限码 `library.document.read`、`library.document.create`、`library.document.delete` 等已定义并集成。
- 用户只能访问自己的文档，且权限检查在 API 层执行。
- 批量操作接口 `POST /api/v1/library/documents/batch-actions` 支持批量停用、批量重新解析和批量删除标记。
- P02 平台首页显示"我的文档库"统计卡片，包含总文档数、今日上传数、待解析数。
- 大文件（>100MB）上传显示进度条，支持断点续传（基础版可使用 HTTP Range header）。
- 解析失败自动重试（最多 3 次），每次重试间隔递增。
- 异常诊断信息清晰，包含错误类型、对应文件和建议。
- 单元测试覆盖 API 逻辑、权限检查、批量操作和错误处理。
- 集成测试验证端到端流程（上传→解析→预览→绑定→使用）。
- 若当前仓库尚未建立 pytest 测试目录，本 Sprint 先建立最小测试目录和运行命令。

## 6. 范围边界

- 不支持高级文件夹管理、标签分类或自定义元数据字段（后续扩展）。
- 不涉及文档版本管理、VCS 级别的变更追踪（扩展功能）。
- 不支持秒传、去重或内容寻址存储（后续性能优化）。
- 不涉及云存储集成（Google Drive、OneDrive）（后续扩展）。
- 权限细节采用最小化设计，不涉及复杂的基于内容的访问控制。

## 7. 验证命令

- 权限验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_permissions.py`（随本 Sprint 新增）
- 批量操作验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_library_batch_operations.py`（随本 Sprint 新增）
- 大文件上传验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_large_file_upload.py`（随本 Sprint 新增）
- 重试机制验证脚本：在 `backend` 目录运行 `conda run -n rag-lab python scripts/verify_parsing_retry.py`（随本 Sprint 新增）
- 后端单元测试：在 `backend` 目录运行 `conda run -n rag-lab pytest app/tests/unit -v`（若目录由本 Sprint 新建）
- 后端集成测试：在 `backend` 目录运行 `conda run -n rag-lab pytest app/tests/integration -v`（若目录由本 Sprint 新建）
- 前端单元测试：在 `frontend` 目录运行 `npm run test -- --run`
- 前端构建：在 `frontend` 目录运行 `npm run build`
- 前端 lint：在 `frontend` 目录运行 `npm run lint`
- OpenAPI 导出：在 `backend` 目录运行 `conda run -n rag-lab python scripts/export_openapi.py`
- 文档空白检查：`git diff --check`

## 8. 执行记录

待执行。

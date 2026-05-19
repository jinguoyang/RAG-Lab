# 系统字典数据表与字典化读取开发计划

本文档是系统运营字典一期的开发计划与执行记录。当前目标是把可运营维护的选项纳入系统字典表，稳定业务状态、权限码和 Pipeline 契约枚举继续由后端约束控制。

## 范围

纳入一期系统字典并支持平台管理页维护：

- `security_level`：用户密级、知识库默认密级、文档上传密级。
- `document_source_type`：文档来源类型，默认 `upload`、`sync`、`import`。
- `file_role`：存储文件角色，默认 `source`、`parsed_artifact`、`attachment`。
- `platform_role`：平台角色展示名、排序和启停；code 仍固定。
- `kb_role`：知识库角色展示名、排序和启停；code 仍固定。
- `feedback_status`：QA 与 App Runtime 反馈状态。

不纳入一期页面可变更范围：

- 业务状态机字段，例如文档、QA Run、RAG App、调用记录状态。
- 权限契约字段，例如权限码、授权 effect。
- Pipeline DSL、Runtime 模式、图检索模式等执行契约。

## 实现步骤

1. 后端新增 `system_dict_types`、`system_dict_items` 表和 Alembic 迁移，写入六类默认种子。
2. 后端新增字典 schema、service、route，提供字典类型查询、字典项查询、创建、更新和禁用能力。
3. 后端写入链路增加 active 字典项校验，覆盖用户密级、知识库默认密级、上传文档密级、KB 角色和反馈状态。
4. 前端新增 `dictionaryService.ts` 和 `types/dictionary.ts`，统一读取字典并保留本地默认兜底。
5. 前端新增平台侧“字典管理”页，并接入 P02、P03、P06、P10、P12、P13 的运营字典选项。

## 验证

- 后端：运行 Python 编译检查和 `backend/scripts/verify_system_dictionaries.py`。
- 前端：运行 `frontend/scripts/verify_system_dictionary_ui.mjs` 和 `npm run build`。
- 数据库：具备本地数据库连接时执行 Alembic upgrade，确认表、索引、CHECK 与种子数据。

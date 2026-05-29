# ParsedDocumentV2 与证据定位 Provenance 设计规范

> 用途：本文件是 B-319 / Sprint 64 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

建立统一 ParsedDocumentV2 数据契约，保存页、块、段落、表格、图片/流程图和定位 provenance，为精准引用、表格检索、流程图理解和答案校验提供底层依据。

## 范围

- 新增 ParsedDocumentV2 schema 与持久化结构。
- 记录 `parseVersion`、`providerName`、`providerVersion`、`contentHash`。
- 块级 provenance 包含 `pageNo`、`blockId`、`blockType`、`text`、`charStart`、`charEnd`、`bbox`、`confidence`。
- 表格保留行列、单元格文本、合并单元格和单元格 bbox。
- 图片和流程图保留对象位置、caption、OCR 文本和结构化识别结果入口。

## 不做

- 不要求所有 provider 都能填满所有字段。
- 不在本任务完成表格问答和流程图推理。
- 不把 ParsedDocumentV2 作为业务真值替代原始文件。

## 设计要点

- ParsedDocumentV2 是下游分块、索引和引用的统一输入。
- 缺失字段必须显式为空或标记不支持，不能伪造页码或 bbox。
- 历史 chunk 的 `page_no`、`charStart`、`charEnd` 应能映射到新 provenance。

## 开发注意项点

- 数据表设计要考虑大文档，正文和结构化块可分表存储。
- 保存 bbox 时明确坐标系、页面宽高和单位。
- LLM 不允许生成定位信息，只能基于解析结果补充摘要或标签。

## 验收标准

- 解析一个 PDF 后能查询页、块和块级定位。
- 解析一个 DOCX 后能保留标题、段落和表格基础结构。
- chunk 能关联到 ParsedDocumentV2 的 block 或 block range。
- 引用响应可返回页码与块级 provenance。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_parsed_document_v2_schema.py -q
python -m pytest backend/app/tests/integration/test_parsed_document_provenance.py -q
python -m py_compile backend/migrations/versions/*parsed_document*.py
python -m compileall backend/app
git diff --check
```

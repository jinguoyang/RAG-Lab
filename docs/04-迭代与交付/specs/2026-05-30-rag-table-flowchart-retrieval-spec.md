# 表格与流程图结构化检索设计规范

> 用途：本文件是 B-324 / Sprint 67 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

让平台能够识别、索引并检索表格和流程图等结构化证据，支持表格问答、流程步骤查询和带定位引用的结构化回答。

## 范围

- 表格解析结果保存为 table、row、column、cell 结构。
- 表格索引同时包含整表摘要、行摘要、列名和关键单元格文本。
- 流程图解析结果保存为 node、edge、label、bbox 和原图引用。
- 检索结果可返回结构化证据片段，并回落到原始页码和 bbox。

## 不做

- 不承诺所有复杂图都能自动完美理解。
- 不在本任务实现完整电子表格计算引擎。
- 不允许 LLM 凭空补全表格单元格。

## 设计要点

- 表格问答应优先使用结构化表格证据，必要时附带周边段落。
- 流程图可先支持 OCR 文本和简单连线关系，复杂图标记低置信度。
- 结构化证据必须能映射回 ParsedDocumentV2 的页面与对象位置。

## 开发注意项点

- 表格单元格合并、跨页表和空单元格需要保留原始结构。
- 流程图 node/edge 识别要记录置信度，低置信度不应用于强结论。
- 所有结构化检索都要通过权限过滤。

## 验收标准

- 表格文档可以按列名、行关键词和单元格内容检索。
- 流程图文档可以检索到关键节点和相邻步骤。
- 答案引用能定位到表格或流程图所在页和 bbox。
- 低置信度结构化结果会在 trace 中显示。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_table_evidence_index.py -q
python -m pytest backend/app/tests/unit/test_flowchart_evidence_index.py -q
python -m pytest backend/app/tests/integration/test_structured_evidence_retrieval.py -q
python -m compileall backend/app
git diff --check
```

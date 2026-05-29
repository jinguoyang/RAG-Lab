# 高质量文档解析 Provider 路由设计规范

> 用途：本文件是 B-318 / Sprint 64 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

为文档解析建立 Provider 路由层，使平台可以按文件类型、质量要求、租户配置和成本策略选择基础解析、版面解析、OCR、视觉模型或外部解析服务，并统一返回 ParsedDocumentV2。

## 当前问题

- PDF 主要依赖文本抽取，表格、版面、页码块和扫描件能力不足。
- DOCX 读取文本节点，表格结构、列表层级和标题层级保真不足。
- 图片解析有方向，但未与文档解析质量等级统一管理。
- 下游分块和引用缺少稳定的解析质量信号。

## 范围

- 新增解析 Provider 能力描述，例如支持文件类型、是否支持 bbox、表格、OCR、图片、置信度。
- 新增解析路由策略：默认、低成本、高质量、强 OCR、表格优先。
- 解析任务记录 provider、版本、耗时、质量标记和失败原因。
- 保持现有文本解析作为 fallback。

## 不做

- 不在本任务绑定唯一外部商业服务。
- 不要求一次性完成所有文件类型的高保真解析。
- 不改造所有历史文档，历史文档通过重新解析任务升级。

## 设计要点

- Provider 路由应是后端能力，前端只选择质量策略或使用知识库默认策略。
- 高质量解析失败时应回退到基础解析，并在质量标记中说明。
- 解析输出必须归一化到 ParsedDocumentV2，而不是让下游适配多个 provider 私有格式。

## 开发注意项点

- 不要把 provider 原始响应直接暴露给分块服务。
- 解析 Provider 的成本和耗时需要进入任务记录，为后续治理提供依据。
- 对扫描 PDF 要给出“需要 OCR”或“已 OCR”的明确标记。

## 验收标准

- 同一文件可以按策略选择不同解析 Provider 或 fallback。
- 解析记录能说明 provider、策略、版本、质量状态和错误。
- 基础解析不被破坏，现有上传和入库流程仍可运行。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_document_parser_routing.py -q
python -m pytest backend/app/tests/integration/test_document_parse_fallback.py -q
python -m compileall backend/app
git diff --check
```

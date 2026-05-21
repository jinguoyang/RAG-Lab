# 图片多模态 RAG 第一阶段实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 RAG 主链路的前提下，让图片文件通过视觉文本抽取进入 ParseRevision、Chunk、检索和 Citation 闭环。

**Architecture:** 第一阶段采用“图片 -> 视觉文本 Markdown -> 文本 Chunk -> 现有 Dense/Sparse/Graph/QA”的融合方式。对象存储保存图片原件，PostgreSQL 保存解析文本和 Chunk 真值，检索副本仍可重建。

**Tech Stack:** FastAPI、SQLAlchemy Core、PostgreSQL、MinIO、Celery、OpenAI-compatible Xiaomi LLM endpoint、React/Vite、Vitest、Pytest。

---

## 1. 关键假设

- 使用 `backend/.env` 已配置的 Xiaomi API Key 进行测试开发，不新增密钥文件，不在文档中写真实 key。
- `RAG_LAB_LLM_ENDPOINT`、`RAG_LAB_LLM_API_KEY`、`RAG_LAB_LLM_MODEL=mimo-v2.5-pro` 可作为视觉文本抽取 Provider 的默认继承配置。
- 如果真实 Xiaomi endpoint 不支持图片消息，开发阶段以 mock Provider 和单元测试完成主链路，真实复测记录为阻塞项。
- 第一阶段只支持独立图片文件：`png`、`jpg`、`jpeg`、`webp`。
- 第二阶段不开发，只在产品待办中预留。

## 2. 文件结构

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `backend/app/core/config.py` | 修改 | 增加视觉文本 Provider 配置，默认继承现有 LLM 配置 |
| `backend/app/services/vision_text_provider.py` | 新增 | 封装图片视觉文本抽取 Provider、HTTP 实现和本地 mock |
| `backend/app/services/document_parsing.py` | 修改 | 识别图片文件并生成 ParsedChunk |
| `backend/app/services/document_service.py` | 修改 | 写入图片 metadata、ParseRevision parse_options 和 Citation 所需来源信息 |
| `backend/app/services/qa_run_service.py` | 修改 | Citation locationSnapshot 补充图片来源字段 |
| `backend/app/schemas/document.py` | 修改 | 文档和 Chunk DTO 暴露 `sourceModality`、图片元数据 |
| `backend/app/tests/unit/test_image_document_parsing.py` | 新增 | 验证图片解析和视觉文本结果 |
| `backend/app/tests/unit/test_image_rag_citation.py` | 新增 | 验证图片 Chunk 的 Evidence/Citation 元数据 |
| `frontend/src` 下文档详情、Chunk/Evidence 相关文件 | 修改 | 对图片证据展示标签和打开原图入口做最小适配 |
| `docs/03-系统设计/*.md` | 修改 | 同步接口、数据模型和详细设计中的图片第一阶段说明 |

## 3. 任务拆分

### Task 1: 配置和 Provider 抽象

**Backlog:** B-218  
**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/vision_text_provider.py`
- Test: `backend/app/tests/unit/test_image_document_parsing.py`

- [ ] Step 1: 增加失败测试，验证默认视觉配置继承 LLM 配置。

运行：

```powershell
cd backend
conda run -n rag-lab pytest app/tests/unit/test_image_document_parsing.py::test_vision_settings_inherit_llm_config -v
```

期望：测试失败，提示视觉配置字段不存在。

- [ ] Step 2: 在 `Settings` 中新增配置。

新增字段：

```python
vision_text_provider: str = Field(default="http", alias="RAG_LAB_VISION_TEXT_PROVIDER")
vision_text_endpoint: str | None = Field(default=None, alias="RAG_LAB_VISION_TEXT_ENDPOINT")
vision_text_api_key: str | None = Field(default=None, alias="RAG_LAB_VISION_TEXT_API_KEY")
vision_text_model: str | None = Field(default=None, alias="RAG_LAB_VISION_TEXT_MODEL")
vision_text_max_image_side: int = Field(default=1600, alias="RAG_LAB_VISION_TEXT_MAX_IMAGE_SIDE")
```

- [ ] Step 3: 新增 `VisionTextProvider`、`LocalVisionTextProvider`、`HttpVisionTextProvider`。

实现要求：

- `LocalVisionTextProvider` 用于单元测试，返回稳定 caption、ocr_text 和 structured_summary。
- `HttpVisionTextProvider` 读取 endpoint/key/model；为空时继承 `llm_endpoint`、`llm_api_key`、`llm_model`。
- HTTP 请求只传图片 base64 给模型，不写入日志。

- [ ] Step 4: 跑 Provider 测试。

运行：

```powershell
cd backend
conda run -n rag-lab pytest app/tests/unit/test_image_document_parsing.py::test_vision_settings_inherit_llm_config -v
```

期望：PASS。

### Task 2: 图片解析接入 document_parsing

**Backlog:** B-219  
**Files:**
- Modify: `backend/app/services/document_parsing.py`
- Test: `backend/app/tests/unit/test_image_document_parsing.py`

- [ ] Step 1: 增加失败测试，上传 `.png` 应返回 `ParsedDocument`。

测试断言：

- `parser_name == "vision_text"`
- `chunks[0].metadata["sourceModality"] == "image"`
- `chunks[0].content` 包含图片描述和 OCR 文本章节。

- [ ] Step 2: 在 `parse_document()` 中增加图片扩展名分支。

规则：

- `.png`、`.jpg`、`.jpeg`、`.webp` 进入 `_parse_image()`。
- 非白名单图片仍返回 `UNSUPPORTED_FILE_TYPE`。
- `_parse_image()` 调用 `get_vision_text_provider()`，把结果渲染成 Markdown。

- [ ] Step 3: 生成图片 Chunk metadata。

metadata 至少包含：

```json
{
  "sourceModality": "image",
  "parserName": "vision_text",
  "region": "full",
  "visionConfidence": "medium"
}
```

- [ ] Step 4: 跑解析测试。

运行：

```powershell
cd backend
conda run -n rag-lab pytest app/tests/unit/test_image_document_parsing.py -v
```

期望：PASS。

### Task 3: 文档与 ParseRevision 元数据落库

**Backlog:** B-220  
**Files:**
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/app/schemas/document.py`
- Test: `backend/app/tests/unit/test_image_document_parsing.py`

- [ ] Step 1: 增加失败测试，图片入库后 version metadata 和 ParseRevision parse_options 包含视觉信息。

断言字段：

- `document_versions.metadata.sourceModality == "image"`
- `document_versions.metadata.visionTextProvider` 存在
- `parse_revisions.parse_options.sourceModality == "image"`

- [ ] Step 2: 在创建 DocumentVersion 和 ParseRevision 时写入图片元数据。

实现规则：

- 从 `ParsedChunk.metadata.sourceModality` 判断是否图片。
- 图片 ParseRevision 使用 `content_format="markdown"`。
- `parse_options` 记录 provider、model、maxImageSide，不记录 API Key。

- [ ] Step 3: DTO 返回图片基础信息。

仅返回安全字段：

```json
{
  "sourceModality": "image",
  "image": {
    "region": "full",
    "visionConfidence": "medium"
  }
}
```

- [ ] Step 4: 跑文档服务相关测试。

运行：

```powershell
cd backend
conda run -n rag-lab pytest app/tests/unit/test_image_document_parsing.py app/tests/unit/test_library_service.py -v
```

期望：PASS。

### Task 4: 图片 Chunk 入库和索引同步验证

**Backlog:** B-221  
**Files:**
- Modify: `backend/app/services/document_service.py`
- Test: `backend/app/tests/unit/test_image_document_parsing.py`

- [ ] Step 1: 增加失败测试，图片绑定知识库后能生成 active Chunk。

断言：

- `chunks.content` 不为空。
- `chunks.metadata.sourceModality == "image"`。
- `chunks.metadata.sourceFileName` 为原始图片名。
- Dense payload 中包含该 Chunk 文本和过滤字段。

- [ ] Step 2: 确保图片 Chunk 复用现有 embedding 和索引同步逻辑。

实现规则：

- 不新增 Visual Index。
- 不改 `DenseRetrievalProvider.upsert_chunks()` 入参。
- OpenSearch 文档中保留 metadata.sourceModality。

- [ ] Step 3: 跑入库相关测试。

运行：

```powershell
cd backend
conda run -n rag-lab pytest app/tests/unit/test_document_lifecycle.py app/tests/unit/test_image_document_parsing.py -v
```

期望：PASS。

### Task 5: QA Evidence 和 Citation 图片来源

**Backlog:** B-222  
**Files:**
- Modify: `backend/app/services/qa_run_service.py`
- Test: `backend/app/tests/unit/test_image_rag_citation.py`

- [ ] Step 1: 增加失败测试，图片候选进入 Evidence 后 Citation 带图片定位。

断言：

- `qa_run_evidence.source_snapshot.sourceModality == "image"`
- `qa_run_citations.location_snapshot.sourceModality == "image"`
- `location_snapshot.region == "full"`
- 不包含 base64 或原始图片二进制。

- [ ] Step 2: 扩展 Citation snapshot 构造。

实现规则：

- 从 candidate metadata 透传 `sourceModality`、`sourceFileId`、`region`、`imageWidth`、`imageHeight`。
- 保持已有 documentId、versionId、chunkId 字段不变。

- [ ] Step 3: 跑 QA 测试。

运行：

```powershell
cd backend
conda run -n rag-lab pytest app/tests/unit/test_image_rag_citation.py app/tests/unit/test_qa_evidence_status.py -v
```

期望：PASS。

### Task 6: 前端最小展示适配

**Backlog:** B-222  
**Files:**
- Modify: `frontend/src` 下文档详情、Chunk 详情、QA Evidence/Citation 展示相关文件
- Test: 对应 Vitest 或构建验证

- [ ] Step 1: 定位当前 Evidence/Citation 和 Chunk 展示组件。

运行：

```powershell
cd frontend
rg -n "Evidence|Citation|Chunk|sourceSnapshot|locationSnapshot|download" src
```

期望：找到 P07/P09/P10 相关展示入口。

- [ ] Step 2: 图片证据展示最小信息。

展示规则：

- `sourceModality=image` 时显示“图片证据”标签。
- 展示原文件名、Chunk 摘要、解析置信度。
- 使用已有文档下载接口打开原图，不新增公开对象存储 URL。

- [ ] Step 3: 跑前端验证。

运行：

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

期望：全部通过。

### Task 7: 小米 API Key 真实开发复测

**Backlog:** B-223  
**Files:**
- Modify: `docs/06-发布与运维/` 下新增或更新复测记录

- [ ] Step 1: 确认 `.env` 中启用 HTTP LLM Provider，密钥不输出。

运行：

```powershell
cd backend
Get-Content .env | ForEach-Object { if ($_ -match 'API_KEY|TOKEN|PASSWORD|SECRET') { ($_ -replace '=.*$', '=***') } else { $_ } }
```

期望：能看到 `RAG_LAB_LLM_PROVIDER=http`、Xiaomi 模型名和脱敏 API Key。

- [ ] Step 2: 使用一张小尺寸测试图片执行图片解析。

运行方式按实现后的测试脚本或 API smoke 命令执行。复测记录必须区分：

- `success`：Xiaomi endpoint 支持图片消息，生成视觉文本。
- `unsupported`：endpoint 或模型不支持图片消息，mock 测试通过但真实复测阻塞。
- `runtime_failed`：网络、凭据或限流失败。

- [ ] Step 3: 记录复测结果。

记录要求：

- 不记录密钥。
- 不粘贴图片 base64。
- 写明模型名、endpoint 类型、状态、失败分类和下一步建议。

### Task 8: 系统设计、OpenAPI 和最终验证

**Backlog:** B-223  
**Files:**
- Modify: `docs/03-系统设计/详细设计说明书.md`
- Modify: `docs/03-系统设计/数据模型设计.md`
- Modify: `docs/03-系统设计/接口设计说明.md`
- Modify: `backend/.env.example`

- [ ] Step 1: 同步系统设计。

补充内容：

- 图片第一阶段属于文档解析能力增强。
- 图片原件在对象存储，视觉文本在 ParseRevision/Chunk。
- Citation 可以回到原图，但不暴露图片 base64。

- [ ] Step 2: 更新 `.env.example`。

新增视觉配置示例，但不写真实值：

```text
RAG_LAB_VISION_TEXT_PROVIDER=http
RAG_LAB_VISION_TEXT_ENDPOINT=
RAG_LAB_VISION_TEXT_API_KEY=
RAG_LAB_VISION_TEXT_MODEL=
RAG_LAB_VISION_TEXT_MAX_IMAGE_SIDE=1600
```

- [ ] Step 3: 执行最终验证。

运行：

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

```powershell
git diff --check
```

期望：全部通过；若 Xiaomi 真实图片复测失败，需在复测记录中明确失败分类。

## 4. 第二阶段预留

第二阶段作为 B-224 保留，不在 Sprint 44 开发。范围包括：

- 多模态 embedding。
- Visual Retrieval Provider。
- 图片作为 query。
- PDF/DOCX 内嵌图片抽取。
- bbox 级 Citation 高亮。
- 跨模态评估集和视觉 rerank。

## 5. 总体验收口径

- 图片文件可上传、解析、绑定知识库、生成 Chunk 并参与文本 QA。
- 图片证据可被 Citation 回溯，不泄露 base64 或密钥。
- 现有文本文档解析、索引和 QA 流程不回退。
- 真实 Xiaomi Provider 复测有明确记录；若环境不支持图片消息，不把 mock 结果冒充真实 Provider 通过。

# 图片多模态 RAG 第一阶段设计

本文档为设计规范，用于指导“图片转视觉文本 Chunk”的第一阶段开发。本文是活文档，聚焦当前可落地的最小闭环；真正跨模态向量检索、以图搜图和多模态 query 不在本阶段实现。

## 1. 背景与目标

当前系统已经具备文档库、知识库绑定、ParseRevision、Chunk、Dense/Sparse/Graph 索引、QA Evidence、Citation 和 RAG App Runtime 链路。图片能力应复用这条链路，而不是另建一套独立图片知识库。

第一阶段目标是让用户上传图片文件后，系统通过视觉文本抽取生成可检索、可引用、可回溯的 Chunk：

- 支持上传常见图片文件，并进入现有文档库和知识库绑定流程。
- 通过视觉模型生成 OCR 文本、图片描述和结构化摘要。
- 将视觉文本写入 ParseRevision 和 Chunk，继续复用现有 Dense、Sparse、Graph、QA、Evidence、Citation 链路。
- Citation 能回溯到原始图片，并展示图片文件、图片区域或整图定位信息。

## 2. 关键假设

- 测试开发阶段使用 `backend/.env` 中已配置的 Xiaomi API Key 和 OpenAI-compatible LLM endpoint，不在代码中新增或提交密钥。
- 新增视觉能力通过独立 Provider 封装，默认可继承现有 `RAG_LAB_LLM_ENDPOINT`、`RAG_LAB_LLM_API_KEY` 和 `RAG_LAB_LLM_MODEL`。
- 如果当前 Xiaomi 模型不支持图片消息，开发阶段允许用单元测试 mock `VisionTextProvider`，真实图片复测记录为环境阻塞，不影响文本 RAG 主链路。
- PostgreSQL 仍是业务真值中心；对象存储保存图片原件，Milvus/OpenSearch/Neo4j 只保存可重建副本。
- 第一阶段只处理独立图片文件；PDF/DOCX 内嵌图片抽取、图片区域级视觉向量和以图搜图放入后续待办。

## 3. 范围

### 3.1 本阶段包含

- 图片 MIME 和扩展名白名单：`png`、`jpg`、`jpeg`、`webp`。
- 新增 `VisionTextProvider` 抽象和 HTTP 实现。
- 图片解析结果结构：OCR 文本、图片描述、关键对象、图表/流程摘要、置信度、定位信息。
- 图片 ParseRevision：以 Markdown 文本保存视觉抽取结果，并在 `parse_options` 或 `metadata` 中标记 `sourceModality=image`。
- 图片 Chunk：继续写入现有 `chunks.content`，metadata 标记视觉来源、原图文件、页码为空、整图区域。
- QA Evidence/Citation：保持引用 Chunk 的安全边界，补充图片来源定位字段，前端可打开原图或下载原文件。
- 测试与验证：覆盖图片解析、知识库绑定、QA 召回、Citation 回溯和无视觉模型时的失败诊断。

### 3.2 本阶段不包含

- 不新增真正多模态向量库 schema。
- 不实现以图搜图。
- 不支持用户上传图片作为 QA query。
- 不解析 PDF/DOCX 内嵌图片。
- 不做图片区域级切块和 bbox 高亮。
- 不更改现有 Dense/Sparse/Graph 至少一路启用的 Pipeline 校验规则。
- 不把图片原件或 base64 写入 QA Trace、Evidence 正文或日志。

## 4. 业务流程

### 4.1 图片上传

图片文件继续走文档库上传入口。`stored_files.mime_type` 保存原始 MIME，`documents.metadata` 或 `document_versions.metadata` 标记：

```json
{
  "sourceModality": "image",
  "image": {
    "width": 1280,
    "height": 720,
    "format": "png"
  }
}
```

上传阶段不调用视觉模型，只保存原件并创建解析任务，避免前台请求阻塞。

### 4.2 图片解析

解析 Worker 根据扩展名或 MIME 调用 `parse_image_document()`：

1. 从对象存储读取图片二进制。
2. 读取图片基础元数据，包括宽、高、格式和文件大小。
3. 调用 `VisionTextProvider.extract_image_text()`，传入图片字节、文件名、MIME 和抽取策略。
4. 将返回结果渲染为 Markdown：
   - `## 图片描述`
   - `## OCR 文本`
   - `## 结构化摘要`
   - `## 关键对象`
   - `## 抽取说明`
5. 创建 ParseRevision，`content_format=markdown`，`parser_name=vision_text`。
6. 基于 Markdown 生成一个或少量 Chunk。

### 4.3 知识库入库

图片入库复用现有知识库绑定后流程：

- Chunk 内容仍是文本，可直接调用现有 `EmbeddingProvider.embed_query()`。
- Dense、Sparse、Graph 副本仍基于文本 Chunk 写入。
- Graph 抽取可复用当前 LLM 图抽取，但 metadata 需要保留 `sourceModality=image`，便于诊断。
- 如果视觉抽取失败，`DocumentVersion.parse_status=failed`，不生成 Chunk，不污染索引副本。

### 4.4 QA 检索与回答

用户以文本提问时，系统仍走当前 QA Pipeline：

```text
query -> rewrite -> embedding -> dense/sparse/graph -> fusion -> permissionFilter -> contextPacking -> generation -> citation
```

图片 Chunk 作为普通文本候选参与召回。答案中如果引用图片 Chunk，Citation 的 `locationSnapshot` 额外包含：

```json
{
  "sourceModality": "image",
  "sourceFileId": "uuid",
  "imageWidth": 1280,
  "imageHeight": 720,
  "region": "full"
}
```

前端展示时优先显示“图片证据”标签，并提供打开原图或下载源文件的入口。

## 5. Provider 设计

新增 Provider：

```python
class VisionTextProvider:
    """图片视觉文本抽取 Provider，负责把图片转换为可检索文本。"""

    def extract_image_text(self, request: VisionTextRequest) -> VisionTextResult:
        raise NotImplementedError
```

推荐 DTO：

```python
class VisionTextRequest(BaseModel):
    file_name: str
    mime_type: str
    image_bytes: bytes
    max_image_side: int = 1600

class VisionTextResult(BaseModel):
    caption: str
    ocr_text: str
    structured_summary: str
    objects: list[str]
    confidence: Literal["high", "medium", "low", "unknown"]
    warnings: list[str] = []
```

HTTP 实现使用 OpenAI-compatible chat completions。配置建议：

```text
RAG_LAB_VISION_TEXT_PROVIDER=http
RAG_LAB_VISION_TEXT_ENDPOINT=        # 为空时继承 RAG_LAB_LLM_ENDPOINT
RAG_LAB_VISION_TEXT_API_KEY=         # 为空时继承 RAG_LAB_LLM_API_KEY
RAG_LAB_VISION_TEXT_MODEL=           # 为空时继承 RAG_LAB_LLM_MODEL
```

开发测试阶段不新增密钥，使用当前 `.env` 已配置的 Xiaomi API Key。代码和文档只能引用环境变量名，不能写入真实 key。

## 6. 数据与元数据

第一阶段优先复用现有表，不新增大表。必要字段放入 JSON metadata：

| 对象 | 字段 | 说明 |
| --- | --- | --- |
| `stored_files` | `mime_type` | 保存图片 MIME |
| `document_versions.metadata` | `sourceModality` | `image` |
| `parse_revisions.parse_options` | `visionProvider`、`visionModel` | 抽取模型和参数 |
| `chunks.metadata` | `sourceModality`、`sourceFileId`、`image` | 图片定位和抽取摘要 |
| `qa_run_evidence.source_snapshot` | `sourceModality` | Evidence 来源类型 |
| `qa_run_citations.location_snapshot` | `sourceFileId`、`region` | 图片 Citation 定位 |

如果第二阶段需要区域级 bbox 或视觉向量，再新增专用表，不在第一阶段提前扩表。

## 7. 错误处理

| 场景 | 处理 |
| --- | --- |
| 图片格式不支持 | 上传或解析阶段返回 `UNSUPPORTED_FILE_TYPE` |
| 图片过大 | 解析前压缩到配置上限，仍失败则返回 `IMAGE_TOO_LARGE` |
| Vision Provider 不可用 | `parse_status=failed`，错误码 `VISION_PROVIDER_UNAVAILABLE` |
| Vision Provider 返回非 JSON | 尝试降级解析纯文本；仍失败则 `VISION_PARSE_INVALID_RESPONSE` |
| 抽取为空 | `PARSE_EMPTY_CONTENT`，不生成 Chunk |

所有错误都写入 `LibraryParseJob` 或 `IngestJob` 的错误字段，前端显示可重试入口。

## 8. 验收标准

- 上传 `png/jpg/webp` 后，文档库能显示解析状态和图片基础元数据。
- 图片解析成功后，ParseRevision 中存在视觉文本 Markdown。
- 图片绑定知识库后，能生成 active Chunk，并写入 Dense/Sparse/Graph 中已启用的副本。
- 文本问题能召回图片生成的 Chunk，并生成带 Citation 的回答。
- Citation 可以回到原始图片文件，不暴露 base64。
- 无视觉模型或 Xiaomi endpoint 不支持图片时，解析失败可诊断，文本文档流程不受影响。
- `git diff --check`、后端编译、后端相关测试、OpenAPI 导出可通过。

## 9. 第二阶段预留

第二阶段不在本轮开发，只进入 Backlog。预留方向：

- 多模态 embedding 和 Visual Retrieval Provider。
- 以图搜图和图片作为 QA query。
- PDF/DOCX 内嵌图片抽取。
- bbox 区域级 Citation 和前端高亮。
- 视觉 rerank 和跨模态评估集。

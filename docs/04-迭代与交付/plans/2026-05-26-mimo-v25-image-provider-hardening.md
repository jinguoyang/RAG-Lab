# mimo-v2.5 图片 Provider 硬化实施计划

> 本文档为开发计划，承接 E31 图片多模态 RAG 演进的后续硬化工作。本文是历史执行证据，当前 Backlog 状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 1. 目标

在 Sprint 44 已完成“图片转视觉文本 Chunk”闭环的基础上，对齐小米 `mimo-v2.5` 图片理解 OpenAI-compatible API，并用两张固定图片样本验证文本问答可以召回图片内容。

## 2. 范围

- 升级 `VisionTextProvider` 请求结构，支持真实 MIME data URL、`api-key` 鉴权头、`mimo-v2.5` 默认模型和图片 token usage 摘要。
- 扩展图片格式白名单到 `jpg/jpeg/png/gif/webp/bmp`，并在 base64 编码超过 50 MB 时提前拒绝。
- 保留第一阶段架构：图片先转视觉文本 Markdown，再进入 ParseRevision、Chunk、Dense/Sparse/Graph、Evidence 和 Citation。
- 使用 `docs/examples/1I3A6520-opq3542107848.jpg` 和 `docs/examples/oxlndt5t1zr31.jpg` 进行问答验收。

## 3. 不做范围

- 不实现多模态 embedding、Visual Retrieval、以图搜图、图片作为 QA query 或 bbox 级 Citation。
- 不把图片 base64、API Key 或原图二进制写入日志、Trace、Evidence 或复测记录。
- 不改写 Sprint 44 历史归档，只新增 Sprint 54 作为后续硬化。

## 4. 实施任务

| Backlog | 任务 | 验收口径 |
| --- | --- | --- |
| B-275 | 对齐 mimo-v2.5 图片 API 请求格式、MIME data URL 和鉴权头 | HTTP payload 使用实际 MIME，鉴权头为 `api-key`，默认模型为 `mimo-v2.5` |
| B-276 | 图片解析记录 MIME、大小、image token usage 和 Provider 安全摘要 | Chunk metadata、ParseRevision options、DocumentVersion metadata 中只记录安全摘要 |
| B-277 | 补齐 VisionTextProvider HTTP payload、限制和错误码测试 | 单元测试覆盖 payload、50 MB 限制、gif/bmp 白名单和 usage 解析 |
| B-278 | 使用两张样本图片完成真实问答召回验收 | 四个自然语言问题能分别召回乔迁照片和猫咪照片 |
| B-279 | 同步系统设计、接口设计、数据模型、`.env.example` 和复测记录 | 文档术语一致，不暴露密钥或 base64 |

## 5. 样本问答验收

样本文件：

- `docs/examples/1I3A6520-opq3542107848.jpg`：中国中车 / CRRC / 中车数字科技园区乔迁新禧现场。
- `docs/examples/oxlndt5t1zr31.jpg`：一只猫坐在炉火或灶火旁。

验收问题：

1. `哪张图片和中国中车/CRRC/乔迁新禧有关？`
2. `哪张图片里有猫？猫旁边有什么？`
3. `有哪些图片内容和庆祝活动有关？`
4. `有哪些图片内容和动物有关？`

通过标准：

- 问题 1 和 3 的 Evidence/Citation 指向 `1I3A6520-opq3542107848.jpg`。
- 问题 2 和 4 的 Evidence/Citation 指向 `oxlndt5t1zr31.jpg`。
- 回答中能说明乔迁、CRRC、中国中车、猫、炉火等关键内容。

## 6. 验证命令

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab pytest app/tests/unit/test_image_document_parsing.py -v
conda run -n rag-lab pytest app/tests/unit/test_image_rag_citation.py -v
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run lint
npm run test
npm run build
```

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
git diff --check
```

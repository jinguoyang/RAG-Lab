# 迭代计划 Sprint 54

## 1. Sprint 基本信息

- Sprint 名称：Sprint 54
- Sprint 主题：mimo-v2.5 图片 Provider 对齐与样本问答验收硬化
- 涉及 Epic：E31 图片多模态 RAG 演进
- 建议版本：多模态 RAG Phase 1 硬化
- 时间范围：待排期
- 目标：在 Sprint 44 图片 RAG 第一阶段基础上，对齐小米 `mimo-v2.5` 图片理解 API，并用两张固定样本验证文本问答可以检索图片内容。

## 2. 关键假设

- 图片能力仍采用第一阶段方案：图片转视觉文本 Chunk 后进入现有文本检索链路。
- 不实现多模态 embedding、以图搜图、图片作为 QA query 或 bbox Citation。
- 真实 API Key 只从本地 `.env` 读取，不提交、不打印、不写入复测记录。
- 两张样本图片固定保留在 `docs/examples/`，只作为验收夹具。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-275 | 对齐 mimo-v2.5 图片 API 请求格式、MIME data URL 和鉴权头 | P0 | 1d | Done |
| B-276 | 图片解析记录 MIME、大小、image token usage 和 Provider 安全摘要 | P0 | 1d | Done |
| B-277 | 补齐 VisionTextProvider HTTP payload、限制和错误码测试 | P0 | 1d | Done |
| B-278 | 使用两张 `docs/examples` 图片完成真实问答召回验收 | P0 | 1d | Done |
| B-279 | 同步系统设计、接口设计、数据模型、`.env.example` 和复测记录 | P1 | 0.5d | Done |

## 4. 验收标准

- 图片 Provider 默认模型为 `mimo-v2.5`。
- HTTP payload 使用实际 MIME 构造 `data:{mime};base64,...`，不再固定为 `image/png`。
- 鉴权头默认使用 `api-key`，可通过环境变量改为 Bearer 兼容模式。
- 支持 `jpg/jpeg/png/gif/webp/bmp`；base64 编码后超过 50 MB 时提前拒绝。
- Provider 返回的 `image_tokens`、MIME、文件大小和模型名进入安全元数据，不保存 base64。
- `docs/examples/1I3A6520-opq3542107848.jpg` 可被“中国中车 / CRRC / 乔迁新禧 / 庆祝活动”类问题召回。
- `docs/examples/oxlndt5t1zr31.jpg` 可被“猫 / 动物 / 炉火”类问题召回。

## 5. 验收问题

1. 哪张图片和中国中车/CRRC/乔迁新禧有关？
2. 哪张图片里有猫？猫旁边有什么？
3. 有哪些图片内容和庆祝活动有关？
4. 有哪些图片内容和动物有关？

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

## 7. 关联文档

- `../../plans/2026-05-26-mimo-v25-image-provider-hardening.md`
- `../../specs/2026-05-21-image-rag-phase1-design.md`

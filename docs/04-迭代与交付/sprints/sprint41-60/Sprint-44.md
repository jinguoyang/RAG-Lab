# 迭代计划 Sprint 44

## 1. Sprint 基本信息

- Sprint 名称：Sprint 44
- Sprint 主题：图片 RAG 第一阶段：视觉文本 Chunk 闭环
- 涉及 Epic：E31 图片多模态 RAG 演进
- 建议版本：多模态 RAG Phase 1
- 时间范围：待排期
- 目标：支持独立图片文件通过视觉文本抽取进入现有文档库、知识库、Chunk、检索、QA Evidence 和 Citation 链路。

## 2. 关键假设

- 本阶段只做图片转视觉文本，不做真正多模态 embedding 或以图搜图。
- 测试开发阶段使用 `backend/.env` 中已配置的 Xiaomi API Key，不新增密钥，不提交 `.env`。
- 如果 Xiaomi endpoint 或模型不支持图片消息，后端以 mock Provider 完成自动化测试，并将真实复测标记为阻塞或不支持。
- 图片原件继续保存在对象存储，PostgreSQL 保存视觉文本 ParseRevision 和 Chunk 真值。
- 现有 Dense/Sparse/Graph、权限裁剪、QA Trace、Evidence、Citation 链路继续复用。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-218 | 设计图片第一阶段 Provider 与配置模型，复用现有 Xiaomi LLM 配置 | P0 | 1d | Ready |
| B-219 | 支持图片文件解析为视觉文本 ParseRevision | P0 | 2d | Ready |
| B-220 | 图片解析结果生成可检索 Chunk，并保留图片来源 metadata | P0 | 1.5d | Ready |
| B-221 | 图片 Chunk 复用现有 Dense/Sparse/Graph 入库和检索链路 | P0 | 1.5d | Ready |
| B-222 | QA Evidence/Citation 支持图片来源回溯和前端最小展示 | P0 | 2d | Ready |
| B-223 | 建立图片 RAG 第一阶段验证、Provider 复测和系统设计同步 | P1 | 1.5d | Ready |

## 4. 验收标准

- 用户可以上传 `png/jpg/jpeg/webp` 图片文件。
- 图片解析成功后生成 Markdown 格式 ParseRevision，包含图片描述、OCR 文本和结构化摘要。
- 图片绑定到知识库后生成 active Chunk，Chunk metadata 标记 `sourceModality=image`。
- 文本 QA 可以召回图片 Chunk，并在答案中给出 Citation。
- Citation 能回溯到原始图片文件或图片证据摘要，不在 Trace、Evidence 或日志中暴露 base64。
- Xiaomi API Key 真实复测有记录；若模型不支持图片消息，失败分类清楚且不影响文本 RAG 主链路。
- 第二阶段能力只进入 Backlog，不在本 Sprint 开发。

## 5. 范围边界

- 不实现多模态 embedding。
- 不实现以图搜图。
- 不支持图片作为 QA query。
- 不解析 PDF/DOCX 内嵌图片。
- 不实现 bbox 区域级高亮。
- 不更改当前 Pipeline 节点类型和至少启用 Dense/Sparse/Graph 一路的校验规则。

## 6. 验证命令

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

## 7. 关联文档

- `../../specs/2026-05-21-image-rag-phase1-design.md`
- `../../plans/2026-05-21-image-rag-phase1.md`

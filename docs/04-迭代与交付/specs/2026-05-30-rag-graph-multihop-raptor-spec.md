# Graph 多跳与 RAPTOR 层级摘要设计规范

> 用途：本文件是 B-326 / Sprint 68 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

增强图谱检索和层级摘要能力，使平台能处理跨文档、多跳关系和长文档主题聚合问题，并在证据链中解释推理路径。

## 范围

- Neo4j 图谱检索支持受控 `graphDepth`、路径模式和节点上限。
- 图谱结果返回路径、节点、边、关联 chunk 和权限状态。
- RAPTOR 或层级摘要索引用于长文档和多文档主题聚合。
- 图谱路径和摘要证据必须能回落到原始 chunk 或 ParsedDocumentV2 block。

## 不做

- 不把图谱作为业务真值。
- 不自动抽取所有实体关系并宣称高置信。
- 不让摘要替代原文证据引用。

## 设计要点

- 多跳路径适合关系问题，RAPTOR 适合层级主题和长上下文聚合。
- 图谱和摘要索引都需要构建版本、来源文档范围和权限继承。
- 检索融合时图谱路径提供线索，最终答案仍需引用原文证据。

## 开发注意项点

- 图谱扩展必须有节点上限和路径上限，防止查询爆炸。
- LLM 抽取关系和摘要要记录置信度、prompt 版本和缓存 key。
- 多文档摘要需要按用户权限动态过滤，不可返回无权文档摘要。

## 验收标准

- 设置 `graphDepth` 后，图谱检索路径长度发生可追踪变化。
- 多跳问题能返回路径解释和对应原文证据。
- 长文档问题可命中层级摘要，同时引用原文块。
- 权限收缩后图谱路径和摘要结果同步收缩。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_graph_multihop_retrieval.py -q
python -m pytest backend/app/tests/unit/test_raptor_summary_index.py -q
python -m pytest backend/app/tests/integration/test_graph_raptor_rag.py -q
python -m compileall backend/app
git diff --check
```

# Answer/Citation Verifier 设计规范

> 用途：本文件是 B-327 / Sprint 68 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

在答案输出前增加引用和事实一致性校验，减少无证据回答、错引、漏引和引用无法定位的问题，让平台输出更接近企业级可审计答案。

## 范围

- 校验答案中的关键断言是否被 evidence 支持。
- 校验 citation 是否包含文档、页码或 block provenance。
- 校验引用证据是否属于当前用户授权范围。
- 低置信答案可降级为“资料不足”、补充澄清问题或触发 Corrective RAG。

## 不做

- 不保证所有开放问题都能给出答案。
- 不把 verifier 作为法律或合规最终裁决。
- 不允许 verifier 使用未授权证据补充答案。

## 设计要点

- Verifier 应接收答案草稿、证据列表、引用列表和 trace。
- 可先实现规则校验，再引入 LLM faithfulness 评分。
- 校验失败要返回结构化原因，方便前端和调试页面展示。

## 开发注意项点

- LLM verifier 的输出必须 schema 校验，不能直接信任自由文本。
- 断言拆解要控制成本，优先对答案句子和引用段落做匹配。
- 被拒绝答案也要保存 trace，便于后续质量分析。

## 验收标准

- 无 citation 的答案会被标记失败或降级。
- 引用不存在、越权或无法定位时会被拒绝。
- 证据与答案明显冲突时不会直接输出原答案。
- 通过校验的答案包含可追踪引用。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_answer_citation_verifier.py -q
python -m pytest backend/app/tests/integration/test_verified_rag_answer.py -q
python -m compileall backend/app
git diff --check
```

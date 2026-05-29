# 员工培训 LLM 结构化 JSON 服务设计规范

> 用途：本文件是 B-305 / Sprint 59 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

为员工培训计划生成、题库生成和主观题评分提供统一的 LLM JSON 输出解析与校验能力，避免各服务重复写不一致的字符串解析逻辑。

## 范围

- 新增 `training_llm_service.py`。
- 支持解析普通 JSON 和 Markdown fenced JSON。
- 校验必需顶层字段。
- 解析失败或字段缺失时抛出稳定业务异常。
- 本任务不直接接入具体 Provider，Provider 调用由后续任务在业务服务中接入。

## 核心异常

- `TrainingLLMOutputError`

## 服务接口

- `parse_training_json(text: str, required_keys: set[str]) -> dict`

## 验收标准

- 能解析 ```json fenced block。
- 缺少必需字段会失败。
- 非 object JSON 会失败。
- 失败不会吞异常并误当作有效 AI 结果。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_training_llm_service.py -q
python -m compileall backend/app
```

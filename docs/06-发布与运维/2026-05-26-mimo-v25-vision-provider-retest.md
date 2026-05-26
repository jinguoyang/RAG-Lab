# mimo-v2.5 Vision Provider 复测结果

**日期:** 2026-05-26  
**Backlog:** B-278  
**Task:** 使用两张 `docs/examples` 图片完成真实 Provider 复测

## 1. 测试环境

- Vision Text Provider：`http`
- Endpoint：`https://token-plan-cn.xiaomimimo.com/v1/chat/completions`
- Model：`mimo-v2.5`
- Auth Header：`api-key`
- API Key：已配置，不输出、不记录

## 2. 测试样本

| 样本 | 用途 |
| --- | --- |
| `docs/examples/1I3A6520-opq3542107848.jpg` | 中国中车 / CRRC / 乔迁新禧样本 |
| `docs/examples/oxlndt5t1zr31.jpg` | 猫咪 / 动物 / 炉火样本 |

## 3. 测试方法

使用后端 `HttpVisionTextProvider` 直接调用真实 Vision API。请求使用实际 MIME `image/jpeg` 构造 `data:image/jpeg;base64,...`，输出只记录状态、`imageTokens` 和摘要字符数，不输出 API Key、base64 或图片二进制。

## 4. 复测结果

**状态:** `success`

| 样本 | 状态 | imageTokens | 摘要字符数 |
| --- | --- | ---: | ---: |
| `1I3A6520-opq3542107848.jpg` | success | 8030 | 104 |
| `oxlndt5t1zr31.jpg` | success | 5757 | 138 |

## 5. 结论

- `mimo-v2.5` 当前可处理两张真实 JPEG 样本。
- Provider 已能提取可进入 ParseRevision / Chunk 的视觉文本摘要。
- 完整问答召回仍需在具备数据库、知识库和索引副本的本地或测试环境中执行；Sprint 54 验收问题见 `docs/04-迭代与交付/sprints/sprint41-60/Sprint-54.md`。

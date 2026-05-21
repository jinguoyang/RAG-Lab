# 知识库 Chunk 管理设计

本文档为活文档，用于指导后续开发知识库 Chunk、文档版本切换、索引副本清理与 QA 历史回溯相关能力。

## 1. 设计目标

Chunk 是知识库检索和 QA 引用的最小证据单元，但不应成为完整文档正文的新真值来源。

本设计需要达成以下目标：

- 明确 Chunk、ParseRevision、BindingRevision、QA 证据之间的关系。
- 支持同一文档多版本入库，但默认检索只命中当前激活版本。
- 支持文档版本切换时平滑重建 Chunk 和检索索引。
- 支持删除文档版本时清理下游 Chunk 和索引副本。
- 保证 QA 历史可回溯，同时允许用户清理不再需要的源文件版本和解析产物。

## 2. 核心原则

1. QA 结果绑定 Chunk，不直接绑定 ParseRevision。
2. Chunk 必须能回溯到生成它的 ParseRevision、DocumentVersion 和 Document。
3. ParseRevision 保存解析后的完整正文或 Markdown/TXT，Chunk 不再保存完整正文副本。
4. 知识库默认只检索 active BindingRevision 下的 active Chunk。
5. 检索副本不是业务真值，PostgreSQL 中的绑定、版本和 Chunk 元数据才是业务真值。
6. 删除文档版本时，只要不影响当前 active 绑定和运行中任务，应级联清理该版本产生的 ParseRevision、BindingRevision、Chunk 和检索副本。
7. QA 历史允许保留运行记录；当引用源被清理后，证据展示为“引用文件已被清理”。

## 3. 对象关系

推荐的回溯链路如下：

```text
QARunEvidence
  -> Chunk
  -> BindingRevision
  -> ParseRevision
  -> DocumentVersion
  -> Document
```

各对象职责如下：

| 对象 | 职责 |
| --- | --- |
| Document | 用户上传文件的业务身份，承载文件名称、所属文档库、基础元数据 |
| DocumentVersion | 源文件版本，代表一次文件内容变更 |
| ParseRevision | 解析版本，代表某个 DocumentVersion 在特定解析配置下的解析产物 |
| DocumentKbBinding | 文档与知识库的绑定关系，持有当前激活的 BindingRevision |
| BindingRevision | 某次将 ParseRevision 物化到知识库的结果，承载索引构建状态 |
| Chunk | 知识库检索的最小证据单元，承载定位、摘要、哈希和回溯信息 |
| QARunEvidence | QA 运行命中的证据引用，记录当次回答使用了哪些 Chunk |

## 4. 推荐数据结构

### 4.1 BindingRevision

```text
binding_revision_id
binding_id
knowledge_base_id
document_id
document_version_id
parse_revision_id
status: building / active / retired / failed / deleted
chunk_count
index_status
build_started_at
build_finished_at
activated_at
retired_at
deleted_at
created_by
created_at
```

状态含义：

| 状态 | 含义 |
| --- | --- |
| building | 正在基于 ParseRevision 生成 Chunk 和检索副本 |
| active | 当前知识库默认检索使用的绑定版本 |
| retired | 历史绑定版本，不参与默认检索，可等待清理 |
| failed | 构建失败，不参与检索 |
| deleted | 已删除或已被文档版本删除级联清理 |

`DocumentKbBinding` 应持有 `active_binding_revision_id`，用于明确当前知识库对该文档采用哪个绑定版本。

### 4.2 Chunk

```text
chunk_id
knowledge_base_id
binding_revision_id
parse_revision_id
document_id
document_version_id
chunk_index
content_hash
start_offset
end_offset
page_no
section_path
heading
summary
token_count
status: building / active / retired / deleted
created_at
retired_at
deleted_at
```

字段说明：

- `content_hash` 用于识别 Chunk 内容是否变化，辅助增量构建和排查。
- `start_offset`、`end_offset`、`page_no`、`section_path` 用于从 ParseRevision 回查原始解析内容。
- `summary` 可以保存短摘要或展示片段，但不应保存完整文档正文。
- `status` 控制 Chunk 是否参与检索和是否仍可作为历史证据展示。

### 4.3 QARunEvidence

```text
evidence_id
run_id
chunk_id
evidence_order
score
source_status: available / source_deleted
created_at
```

`QARunEvidence` 记录当次 QA 命中的 Chunk。正常情况下通过 `chunk_id` 回溯证据来源；当 Chunk 或其上游 ParseRevision 被清理后，将 `source_status` 标记为 `source_deleted`，历史 QA 页面展示“引用文件已被清理”。

## 5. Chunk 与 ParseRevision 的边界

ParseRevision 是解析正文的真值来源。每个 ParseRevision 可以保存一份解析后的 Markdown、TXT 或结构化文本结果。

Chunk 是知识库内的检索证据单元。Chunk 不保存完整正文副本，只保存以下信息：

- 所属知识库和绑定版本。
- 对应的文档、文档版本和解析版本。
- 在 ParseRevision 正文中的定位信息。
- 检索、排序和展示所需的短字段。
- 与向量索引、全文索引、图谱副本关联所需的稳定标识。

因此，知识库不会再额外保存一份完整解析文本，避免数据源膨胀和真值不一致。

## 6. 多版本 Chunk 管理策略

同一文档可以存在多个 DocumentVersion，也可以存在多个 ParseRevision。知识库允许保留多个 BindingRevision 和对应 Chunk 元数据，但默认检索只能使用当前 active BindingRevision 下的 active Chunk。

推荐规则：

1. 同一 `DocumentKbBinding` 同一时刻只能有一个 active BindingRevision。
2. 新版本构建成功前，旧 active BindingRevision 继续服务检索。
3. 新 BindingRevision 激活后，旧 BindingRevision 进入 retired。
4. retired Chunk 不参与默认检索。
5. 管理端可以展示历史绑定版本，但普通 QA 不应混用同一文档多个版本的 Chunk。
6. 如未来需要“跨版本对比检索”，应作为独立高级能力实现，不能影响默认检索语义。

## 7. 文档版本切换流程

当用户在知识库内将某文档切换到新的文档版本或解析版本时，建议采用先构建后切换的流程：

1. 创建新的 BindingRevision，状态为 `building`。
2. 基于目标 ParseRevision 生成新的 Chunk，Chunk 状态为 `building`。
3. 写入向量库、全文索引和图结构等检索副本。
4. 检索副本全部成功后，在事务内完成激活：
   - 新 BindingRevision 置为 `active`。
   - 新 Chunk 置为 `active`。
   - `DocumentKbBinding.active_binding_revision_id` 指向新 BindingRevision。
   - 原 active BindingRevision 置为 `retired`。
   - 原 active Chunk 置为 `retired`。
5. 异步清理 retired Chunk 对应的检索副本。
6. 若构建失败，新 BindingRevision 置为 `failed`，旧 active BindingRevision 不受影响。

该流程保证版本切换对线上 QA 尽量无感，并避免半成品 Chunk 进入检索。

## 8. 检索副本管理

检索副本包括但不限于向量库、全文索引和图数据库中的节点或边。它们应被视为 Chunk 的派生数据，不是业务真值。

推荐规则：

- 写入检索副本时，必须携带 `chunk_id`、`binding_revision_id`、`knowledge_base_id`、`document_version_id` 和 `parse_revision_id`。
- 默认检索条件必须包含 `knowledge_base_id` 和 active Chunk 范围。
- BindingRevision 进入 retired 后，其检索副本可以异步删除。
- BindingRevision 进入 deleted 后，其检索副本必须被清理或进入待清理队列。
- 清理检索副本失败时，不应恢复业务数据状态，而应记录清理任务重试。

## 9. 删除文档版本对 Chunk 的影响

用户在文档库删除某个 DocumentVersion 时，该版本下游数据通常没有继续保留价值，应按以下规则处理。

### 9.1 禁止删除的场景

满足任一条件时，应禁止删除 DocumentVersion：

- 该版本支撑某个知识库当前 active BindingRevision。
- 该版本存在 building、running、pending 状态的解析、索引或 QA 相关任务。
- 该版本正在被权限、绑定或清理流程锁定。

提示语应明确说明阻塞原因，例如：需要先在相关知识库切换文档版本、解绑文档，或等待任务结束。

### 9.2 允许删除的场景

当 DocumentVersion 不再支撑 active BindingRevision，也没有运行中任务时，可以删除。删除时应级联清理：

- 该 DocumentVersion 下的 ParseRevision。
- 由这些 ParseRevision 产生的 BindingRevision。
- 由这些 BindingRevision 产生的 Chunk。
- 对应的向量库、全文索引和图结构副本。

如果仅有 QA 历史引用这些 Chunk，不阻止删除，但必须向用户强提醒：删除后历史 QA 的证据来源将显示为“引用文件已被清理”。

### 9.3 QA 历史处理

删除发生后，不删除 QA 运行记录本身。推荐处理方式：

- 保留 `qa_run`、问题、回答、运行时间、调用应用等运行记录。
- 将相关 `qa_run_evidence.source_status` 更新为 `source_deleted`。
- 如保留 `chunk_id` 会违反外键约束，可将证据表设计为允许软引用，或在删除前将证据转为 source_deleted 状态。
- QA 历史详情页不再展示原文片段，只展示“引用文件已被清理”。

## 10. 删除 ParseRevision 对 Chunk 的影响

普通用户界面不建议暴露独立删除 ParseRevision 的入口。ParseRevision 清理应主要通过删除文档版本触发。

若后续管理端确实需要独立清理 ParseRevision，应复用文档版本删除的保护规则：

- 若被 active BindingRevision 使用，禁止删除。
- 若存在运行中任务，禁止删除。
- 若仅被 retired BindingRevision、deleted BindingRevision 或 QA 历史引用，允许强确认删除。
- 删除后级联清理对应 BindingRevision、Chunk 和检索副本。

## 11. QA 回溯展示规则

QA 历史展示应按证据状态分流：

| source_status | 展示方式 |
| --- | --- |
| available | 展示文档名、版本、页码或章节、命中片段 |
| source_deleted | 展示“引用文件已被清理”，保留证据顺序和得分等运行信息 |

如果 Chunk 为 retired 但上游 ParseRevision 仍存在，可以正常回溯历史证据；retired 只表示不再参与默认检索，不表示历史不可见。

## 12. 权限和操作入口

Chunk 管理通常不作为普通用户的独立操作对象。用户主要通过以下入口间接影响 Chunk：

- 文档库：删除文档版本，触发下游 Chunk 清理。
- 知识库：绑定文档、切换文档版本、重建索引，触发 BindingRevision 和 Chunk 变更。
- QA 历史：查看证据来源，感知 Chunk 是否仍可回溯。

权限建议沿用权限设计文档：

- 删除文档版本需要文档库层面的文档删除或版本管理权限。
- 切换知识库绑定版本、重建索引需要知识库层面的编辑权限。
- 查看 QA 历史需要知识库层面的历史查看权限，或仅查看自己的 QA 结果。

## 13. 开发验收关注点

后续实现时至少验证以下场景：

1. 新版本构建失败时，旧 active Chunk 仍可检索。
2. 新版本构建成功后，默认检索只命中新 active BindingRevision 的 Chunk。
3. 删除 retired 文档版本后，对应 Chunk 和检索副本被清理。
4. 删除仍支撑 active BindingRevision 的文档版本被拒绝。
5. 删除仅被 QA 历史引用的文档版本时，需要强确认。
6. 源被删除后的 QA 历史仍可打开，并展示“引用文件已被清理”。
7. 检索副本清理失败时，业务状态不回滚，清理任务可重试。

## 14. 与现有设计的衔接

本文档延续以下已定设计：

- 权限角色与跨资源校验规则见 `2026-05-20-permission-role-model-design.md`。
- 文档版本、ParseRevision 删除规则见 `2026-05-21-document-version-parse-revision-deletion-design.md`。

如后续同步系统设计文档，应以本文档的 Chunk 真值边界和删除级联规则为准。

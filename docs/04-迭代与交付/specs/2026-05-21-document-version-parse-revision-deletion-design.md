# 文档版本与解析版本删除设计

本文档是文档版本管理、ParseRevision 清理和下游影响控制的设计规范，属于后续开发参考规格。本文聚焦文档、文档版本、解析版本、知识库绑定、Chunk 和 QA 历史之间的删除约束，不替代具体数据库迁移、接口 Schema 或前端交互设计。

## 1. 设计目标

- 避免知识库中保存完整解析文本副本，减少数据源重复。
- 让用户主要通过“文档”和“文档版本”管理存储，降低操作理解成本。
- 将 ParseRevision 定义为系统内部解析产物，普通用户不直接管理。
- 保护当前知识库检索和智能应用调用不被误删破坏。
- 允许用户在明确影响后清理旧文档版本及解析产物，控制存储膨胀。
- QA 历史保留运行记录；被清理的引用在查看时显示“引用文件已被清理”。

## 2. 核心对象关系

推荐关系如下：

```text
Document
  -> DocumentVersion
       -> ParseRevision
            -> BindingRevision
                 -> Chunk / IndexSyncJob
                      -> QARun Evidence / Citation
```

各对象职责：

| 对象 | 定位 | 是否面向普通用户 |
| --- | --- | --- |
| `Document` | 文档库中的文档主对象 | 是 |
| `DocumentVersion` | 某次上传或替换形成的源文件版本 | 是 |
| `ParseRevision` | 某个源文件版本的一次解析产物，例如 Markdown 或纯文本 | 默认否 |
| `BindingRevision` | 知识库对某个 ParseRevision 的切块和索引物化版本 | 默认否 |
| `Chunk` | 面向检索的片段和定位信息 | 管理/诊断视图可见 |
| `QARun Evidence` | QA 历史中的证据引用 | 是 |

## 3. 版本语义

### 3.1 DocumentVersion

`DocumentVersion` 表达源文件版本。以下操作应产生新版本：

- 上传新文件。
- 替换源文件。
- 用户明确选择“作为新版本上传”。

以下操作不产生新版本：

- 修改文档名称、描述、标签。
- 修改文档密级。
- 对同一源文件重新解析。
- 切换文档库 active version。

### 3.2 ParseRevision

`ParseRevision` 表达解析产物版本。以下操作应产生新的 ParseRevision：

- 同一源文件使用不同解析器版本重新解析。
- OCR、表格策略、版面识别策略等解析参数变化后重新解析。
- 旧 ParseRevision 解析失败后，用户触发重新解析并成功生成新文本。

ParseRevision 可以保存完整 Markdown 或纯文本内容，但知识库不再复制保存完整解析正文。

### 3.3 BindingRevision

`BindingRevision` 表达知识库对某个 ParseRevision 的物化结果。以下操作应产生新的 BindingRevision：

- 将知识库绑定升级到新的 DocumentVersion 或 ParseRevision。
- 修改切块参数。
- 修改会影响 Chunk 生成的知识库入库策略。

BindingRevision 成功激活后，旧 BindingRevision 可进入 retired 状态。历史 QA 继续引用当时使用的 Chunk 或证据记录，不被改写。

## 4. 存储策略

### 4.1 ParseRevision 保存完整解析正文

ParseRevision 可保存：

```text
parse_revision_id
document_version_id
content_format: markdown / text
content_object_key 或 content_text
content_hash
parser_name
parser_version
parse_options
status
created_at
```

如果解析正文较大，优先将正文存入对象存储，PostgreSQL 只保存 `content_object_key`、hash 和元数据。

### 4.2 Chunk 不保存完整正文副本

Chunk 或 BindingChunk 推荐只保存定位和索引所需摘要：

```text
chunk_id
binding_revision_id
parse_revision_id
start_offset
end_offset
content_hash
page_no
section
token_count
status
```

需要展示 Chunk 正文时，从 ParseRevision 正文按 offset 截取。这样知识库不再保存完整文档副本。

### 4.3 检索副本可保存必要片段

Milvus、OpenSearch、Neo4j 仍可保存检索所需的片段、向量或图结构副本，但它们不是业务真值。ParseRevision 或 BindingRevision 删除后，应由 IndexSyncJob 清理相关检索副本。

## 5. 用户可见删除入口

首版建议只向普通用户暴露两个入口：

| 入口 | 用途 | 说明 |
| --- | --- | --- |
| 删除文档 | 整个文档不再需要 | 影响全部版本和解析产物，必须强确认 |
| 删除文档版本 | 清理某次上传的源文件版本及其解析产物 | 推荐作为主要存储清理入口 |

ParseRevision 删除不作为普通入口，只用于高级维护或内部治理：

- 清理失败解析产物。
- 清理旧解析器产生的异常结果。
- 后台存储治理脚本按策略清理。

这样可以避免用户在“删文档、删版本、删解析版本”之间做过细选择，降低操作难度。

## 6. 删除文档版本

删除 DocumentVersion 是首版推荐的主要清理方式。它会级联清理该版本下所有 ParseRevision，并处理相关非活跃下游物化数据。

### 6.1 删除前检查

删除前必须执行影响分析：

| 检查项 | 规则 |
| --- | --- |
| 是否为文档库当前 active version | 默认禁止删除；需先切换 active version，若是唯一版本则改走删除文档流程 |
| 是否存在 active BindingRevision | 禁止删除，避免破坏当前知识库检索 |
| 是否存在 pending/running 任务 | 禁止删除，避免破坏正在执行的解析、绑定或索引任务 |
| 是否存在历史 QA 引用 | 允许删除，但必须展示强提醒和二次确认 |
| 是否只有 retired/disabled BindingRevision 引用 | 允许删除，并清理下游物化数据 |

### 6.2 删除流程

```text
校验 library.version.delete
-> 查询该 DocumentVersion 下所有 ParseRevision
-> 检查是否被 active BindingRevision 使用
-> 检查是否被 pending/running 作业使用
-> 汇总历史 QA 引用数量和影响范围
-> 用户强确认
-> 删除或归档 DocumentVersion
-> 删除其下所有 ParseRevision 正文和记录
-> 将相关 retired/disabled BindingRevision、Chunk、索引副本标记清理
-> 将相关 QA Evidence 标记为 source_deleted 或在查询时识别引用缺失
```

### 6.3 删除后的效果

- 不影响当前 active BindingRevision。
- 不影响当前知识库检索。
- 不影响智能应用新调用。
- 相关历史 QA 的问题、回答、运行配置、Trace 摘要和调用记录仍可查看。
- 相关历史 Evidence/Citation 不再展示原文，显示“引用文件已被清理”。

## 7. 删除文档

删除 Document 表示整个文档及全部版本不再需要，影响范围大于删除单个版本。

### 7.1 删除前检查

| 检查项 | 规则 |
| --- | --- |
| 任一版本被 active BindingRevision 使用 | 禁止删除，需先解绑或切换知识库绑定 |
| 任一版本存在 pending/running 任务 | 禁止删除 |
| 存在历史 QA 引用 | 允许删除，但必须强提醒 |
| 无下游引用 | 可普通确认删除 |

### 7.2 删除流程

```text
校验 library.document.delete
-> 汇总全部 DocumentVersion 和 ParseRevision 的下游引用
-> 若存在 active BindingRevision 或运行中任务，拒绝删除
-> 展示影响分析和强确认
-> 删除或归档 Document
-> 删除或归档全部 DocumentVersion
-> 删除全部 ParseRevision 正文和记录
-> 清理 retired/disabled BindingRevision、Chunk 和检索副本
-> 更新或查询时识别相关 QA Evidence 为 source_deleted
```

删除文档适合“整个文档不再保留”的场景；清理旧内容优先使用删除文档版本。

## 8. 删除 ParseRevision

ParseRevision 是系统内部解析产物，普通用户默认不直接操作。高级维护场景下可提供删除能力。

### 8.1 删除前检查

| 检查项 | 规则 |
| --- | --- |
| 被 active BindingRevision 使用 | 禁止删除 |
| 被 pending/running 作业使用 | 禁止删除 |
| 被历史 QA 引用 | 允许删除，但强提醒 |
| 无引用或仅被 retired/disabled 物化引用 | 允许删除 |

### 8.2 删除流程

```text
校验高级维护权限
-> 检查 active BindingRevision 和 running job
-> 汇总历史 QA 引用
-> 用户强确认
-> 删除 ParseRevision 正文和记录
-> 清理 retired/disabled BindingRevision、Chunk 和索引副本
-> 更新或查询时识别相关 QA Evidence 为 source_deleted
```

首版如果没有明确高级治理需求，可以不实现独立 ParseRevision 删除接口，只由删除文档版本级联触发。

## 9. QA 历史影响

### 9.1 基本规则

QA 历史的运行事实不因上游文档清理而删除。清理 DocumentVersion 或 ParseRevision 后：

- `QARun` 保留。
- 用户问题保留。
- 生成回答保留。
- 运行配置快照保留。
- App 调用记录保留。
- Evidence/Citation 原文不可再展开。

历史详情中显示：

```text
引用文件已被清理
原始证据片段不可查看
```

### 9.2 不做降级保留

本设计不保留被删除 ParseRevision 的降级元数据副本。用户强确认删除后，ParseRevision 相关正文和记录可以完全清理。

为支持历史展示，推荐只在 QARun Evidence 层保留最小状态：

```text
evidence_status: available / source_deleted
source_deleted_at
```

该状态只说明证据来源已被清理，不保存 ParseRevision 的历史详情。

### 9.3 外键策略

如果 `qa_run_evidence` 引用 `parse_revision_id` 或 `chunk_id`，推荐采用以下策略之一：

| 策略 | 说明 | 推荐度 |
| --- | --- | --- |
| `ON DELETE SET NULL` + 标记 `source_deleted` | 删除源记录后保留 QARun Evidence 行 | 推荐 |
| 弱引用字符串 + 查询时判断缺失 | 实现简单，但排障统计弱 | 可选 |
| 强外键阻止删除 | 与用户可强制清理的目标冲突 | 不推荐 |

推荐在删除时显式标记 `source_deleted`，便于历史详情、统计和排障。

## 10. 知识库和应用影响

### 10.1 当前知识库可用性保护

任何删除操作只要会影响当前 active BindingRevision，都必须禁止。用户必须先完成以下任一操作：

- 将知识库绑定切换到其他 DocumentVersion 或 ParseRevision。
- 解绑该文档。
- 停用或归档相关知识库绑定。

### 10.2 智能应用影响

智能应用只依赖知识库当前 active binding 和 active config。只要删除操作没有影响 active BindingRevision，就不影响 App Runtime。

如果某文档版本正在支撑 active BindingRevision，则删除被禁止，因此不会出现 App Runtime 引用缺失的情况。

## 11. 删除确认与影响提示

删除文档版本或文档时，必须展示影响分析。建议内容：

```text
即将清理：文档 xxx / 版本 v3
当前知识库使用：否
运行中任务：无
历史 QA 引用次数：28
影响知识库：A、B
影响时间范围：2026-05-01 至 2026-05-20

删除后：
- 不影响当前知识库检索和智能应用调用
- 相关 QA 历史仍可查看问题、回答、运行参数和调用记录
- 相关 Evidence/Citation 将显示“引用文件已被清理”
- 无法再查看当时引用的原文片段
```

当存在历史 QA 引用时，应要求用户二次确认：

```text
我确认清理该文档版本，并接受相关 QA 历史证据不可回放。
```

## 12. 权限建议

| 操作 | 权限 |
| --- | --- |
| 删除文档 | `library.document.delete` |
| 删除文档版本 | `library.version.delete` |
| 删除 ParseRevision | 高级维护权限，或内部任务权限 |
| 查看删除影响分析 | 与删除操作相同权限 |

删除操作必须写审计日志。审计记录至少包含：

- 操作者。
- 删除对象类型和 ID。
- 是否存在历史 QA 引用。
- 被影响知识库数量。
- 被影响 QARun 数量。
- 用户确认时间。

## 13. 首版不做范围

- 不向普通用户暴露独立 ParseRevision 删除入口。
- 不在知识库中保存完整解析文本副本。
- 不保留 ParseRevision 删除后的降级元数据副本。
- 不允许删除 active BindingRevision 正在使用的上游版本。
- 不保证被清理来源的 QA 历史可完整证据回放。
- 不做自动按时间清理策略；首版以用户手动清理为主。

## 14. 验收关注点

- 删除 DocumentVersion 时，如果其 ParseRevision 被 active BindingRevision 使用，必须拒绝。
- 删除 DocumentVersion 时，如果存在 running job，必须拒绝。
- 删除 DocumentVersion 时，如果仅存在历史 QA 引用，允许强确认删除。
- 删除后相关 QA 历史仍可打开，并显示“引用文件已被清理”。
- 删除后当前知识库检索和 App Runtime 不受影响。
- 普通用户界面不暴露 ParseRevision 删除入口。
- 删除操作写入审计日志。
- 知识库不保存完整解析文本副本，Chunk 只保存定位和摘要信息。

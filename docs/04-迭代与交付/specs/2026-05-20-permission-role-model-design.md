# 权限角色模型设计

本文档是文档库、知识库和智能应用三层权限模型的设计规范，属于后续开发参考规格。本文只定义角色、权限边界、控制对象和业务操作判定流程，不替代具体数据库迁移、接口 Schema 或前端交互设计。

## 1. 设计目标

- 使用少量固定角色覆盖首版业务需要，避免过早引入复杂策略引擎。
- 明确文档库、知识库、智能应用三层的控制对象和权限边界。
- 支持用户直接授权和用户组授权并存，首版有效权限采用 allow 并集。
- 保留权限码作为后端最终判定依据，角色只作为权限码集合的管理入口。
- 保证跨资源操作必须分别校验相关资源权限，避免单侧授权导致数据外泄。

## 2. 基本原则

### 2.1 平台角色与资源角色分离

平台角色决定用户在系统层面的资格，例如是否能管理用户、创建资源或旁路资源授权。资源角色决定用户在某个具体文档库、知识库或智能应用中的操作权限。

`platform_user` 不自动拥有任何具体资源权限。普通用户能操作某个文档库、知识库或智能应用，必须来自资源 owner、用户直接成员绑定或用户组成员绑定。

`platform_admin` 是超级管理员，可以旁路资源角色，但后端仍应记录审计日志。

### 2.2 角色映射权限码

后端业务判断不应直接散落判断角色名。推荐实现方式为：

```text
用户/用户组 -> 资源角色 -> 权限码集合 -> 后端业务操作校验
```

这样后续调整某个角色的权限，只需要修改角色到权限码的映射，不需要逐个改业务服务。

### 2.3 同一资源内权限取并集

同一资源内，用户直接角色和用户组继承角色的权限取并集：

```text
有效权限 = 用户直接角色权限 ∪ 用户所属用户组角色权限
```

首版不引入显式 deny。若后续需要“某用户在用户组中有权限，但对该用户单独禁止”，再引入 deny，并采用 deny 优先规则。

### 2.4 跨资源操作分别校验

跨资源操作不能只看单一资源权限。例如将文档绑定到知识库时，必须同时满足：

```text
源文档所在文档库具备绑定权限
+
目标知识库具备绑定权限
```

任一侧不满足，操作应失败。

### 2.5 禁用状态优先

以下对象处于禁用、归档或删除状态时，不参与权限授予：

- 用户
- 用户组
- 用户组成员关系
- 文档库成员绑定
- 知识库成员绑定
- 应用成员绑定
- 文档库、知识库、智能应用本身

资源被禁用时，应优先按资源状态拒绝写入或运行操作，再进行具体权限判断。

## 3. 控制对象

### 3.1 文档库层

```text
DocumentLibrary -> Document -> DocumentVersion -> StoredFile
```

文档库层控制源文档的归属、上传、预览、下载、版本管理、删除和对知识库的绑定授权。文档库权限不代表用户能在目标知识库中使用该文档。

### 3.2 知识库层

```text
KnowledgeBase -> DocumentKbBinding -> KbDocumentVersion / Chunk / IndexSyncJob -> QARun
```

知识库层控制文档版本是否进入某个知识库、是否生成 Chunk 和检索副本、是否可运行 QA、是否可查看 QA 历史和治理结果。

### 3.3 智能应用层

```text
RagApp -> AppApiKey -> AppInvocation / AppConversation / AppMessage
```

智能应用层控制外部 API 发布、API Key 管理、调用统计、调用记录和管理端试运行。App Runtime 使用 App API Key 鉴权，不复用后台用户登录态。

## 4. 平台角色

| 角色 | 定位 |
| --- | --- |
| `platform_admin` | 超级管理员，可管理用户、用户组、资源、权限和审计；可旁路资源角色 |
| `platform_user` | 普通用户，可登录平台；可创建自己被允许创建的文档库或知识库 |

平台角色不替代资源角色。除 `platform_admin` 外，平台角色只决定系统入口和全局资格，不直接授予某个具体资源的业务操作权限。

## 5. 文档库角色

| 角色 | 权限范围 |
| --- | --- |
| `library_owner` | 全部文档库权限；可转移 owner、删除或归档文档库、管理成员 |
| `library_manager` | 除转移 owner、删除整个文档库外的全部权限；可管理成员 |
| `library_editor` | 上传、更新、版本管理、绑定、归档或删除文档、下载 |
| `library_binder` | 查看、预览、下载、绑定到知识库 |
| `library_viewer` | 查看、预览、下载 |

### 5.1 文档库权限码建议

| 权限码 | 控制对象 | 说明 |
| --- | --- | --- |
| `library.view` | DocumentLibrary | 查看文档库基础信息 |
| `library.member.manage` | DocumentLibrary | 管理文档库成员 |
| `library.document.read` | Document | 查看文档列表、详情和预览 |
| `library.document.download` | StoredFile | 下载源文件 |
| `library.document.create` | Document | 上传新文档 |
| `library.document.update` | Document | 修改文档名称、密级、状态等基础信息 |
| `library.document.delete` | Document | 删除、停用或归档文档 |
| `library.version.create` | DocumentVersion | 上传新版本 |
| `library.version.activate` | DocumentVersion | 切换文档库 active version |
| `library.version.delete` | DocumentVersion | 删除未被引用的版本 |
| `library.document.bind` | Document / DocumentVersion | 允许将文档版本绑定到知识库 |

`library.document.bind` 必须独立于 `library.document.read`。只读用户可以查看文档，但不能把文档带入其他知识库。

### 5.2 角色到权限码映射

| 角色 | 权限码 |
| --- | --- |
| `library_owner` | 文档库全部权限码 |
| `library_manager` | 文档库全部权限码，排除转移 owner 和删除整个文档库 |
| `library_editor` | `library.view`、`library.document.read`、`library.document.download`、`library.document.create`、`library.document.update`、`library.document.delete`、`library.version.create`、`library.version.activate`、`library.version.delete`、`library.document.bind` |
| `library_binder` | `library.view`、`library.document.read`、`library.document.download`、`library.document.bind` |
| `library_viewer` | `library.view`、`library.document.read`、`library.document.download` |

## 6. 知识库角色

| 角色 | 权限范围 |
| --- | --- |
| `kb_owner` | 全部知识库权限；可转移 owner、删除或归档知识库、管理成员 |
| `kb_manager` | 除转移 owner、删除整个知识库外的全部权限；可管理成员、配置、文档绑定和应用 |
| `kb_editor` | 绑定文档、解绑、重建索引、管理配置、运行 QA、查看历史 |
| `kb_viewer` | 查看知识库、文档摘要、Chunk 摘要和 QA 历史 |
| `kb_qa_runner` | 运行 QA，查看自己的 QA 运行结果 |

### 6.1 知识库权限码建议

| 权限码 | 控制对象 | 说明 |
| --- | --- | --- |
| `kb.view` | KnowledgeBase | 查看知识库基础信息 |
| `kb.manage` | KnowledgeBase | 修改基础信息、启停知识库 |
| `kb.member.manage` | KbMemberBinding | 管理知识库成员 |
| `kb.document.bind` | DocumentKbBinding | 将文档版本绑定到知识库 |
| `kb.document.unbind` | DocumentKbBinding | 解绑文档 |
| `kb.document.rebuild` | DocumentKbBinding / Chunk | 重建 Chunk 和检索副本 |
| `kb.document.read` | DocumentKbBinding | 查看知识库文档摘要和绑定状态 |
| `kb.chunk.read` | Chunk | 查看 Chunk 正文或详情 |
| `kb.config.manage` | ConfigRevision | 保存、验证和激活配置 |
| `kb.qa.run` | QARun | 发起 QA |
| `kb.qa.history.read` | QARun | 查看知识库 QA 历史 |
| `kb.qa.history.read_own` | QARun | 查看自己发起的 QA 运行结果 |
| `kb.evaluation.manage` | EvaluationSample | 管理评估样本 |
| `kb.app.manage` | RagApp | 创建、编辑、停用知识库下的智能应用 |

### 6.2 角色到权限码映射

| 角色 | 权限码 |
| --- | --- |
| `kb_owner` | 知识库全部权限码 |
| `kb_manager` | 知识库全部权限码，排除转移 owner 和删除整个知识库 |
| `kb_editor` | `kb.view`、`kb.document.bind`、`kb.document.unbind`、`kb.document.rebuild`、`kb.document.read`、`kb.chunk.read`、`kb.config.manage`、`kb.qa.run`、`kb.qa.history.read`、`kb.evaluation.manage` |
| `kb_viewer` | `kb.view`、`kb.document.read`、`kb.qa.history.read` |
| `kb_qa_runner` | `kb.view`、`kb.qa.run`、`kb.qa.history.read_own` |

`kb_editor` 包含 `kb.config.manage`，因为能绑定文档、重建索引和运行 QA 的用户，通常也需要调整检索和生成配置。若部署环境希望配置权限更严格，可在后续版本拆出 `kb_config_manager`，首版不建议增加角色。

## 7. 应用角色

| 角色 | 权限范围 |
| --- | --- |
| `app_owner` | 管理 App、Key、统计、调用记录；可转移 owner、删除或归档 App |
| `app_operator` | 管理 Key、查看调用记录、查看统计、试运行 |
| `app_viewer` | 查看统计和调用记录 |

### 7.1 应用权限码建议

| 权限码 | 控制对象 | 说明 |
| --- | --- | --- |
| `app.view` | RagApp | 查看 App 基础信息 |
| `app.manage` | RagApp | 编辑、停用、归档 App |
| `app.owner.transfer` | RagApp | 转移 App owner |
| `app.delete` | RagApp | 删除或归档 App |
| `app.key.manage` | AppApiKey | 创建、删除、轮换 API Key |
| `app.invocation.read` | AppInvocation | 查看调用记录 |
| `app.stats.read` | AppInvocation | 查看调用统计 |
| `app.runtime.test` | RagApp | 在管理端试运行 Runtime |

### 7.2 角色到权限码映射

| 角色 | 权限码 |
| --- | --- |
| `app_owner` | 应用全部权限码 |
| `app_operator` | `app.view`、`app.key.manage`、`app.invocation.read`、`app.stats.read`、`app.runtime.test` |
| `app_viewer` | `app.view`、`app.invocation.read`、`app.stats.read` |

### 7.3 应用与知识库权限关系

创建智能应用前，用户必须具备所属知识库的应用管理权限：

```text
kb.app.manage on target knowledge base
```

App 创建后，App 内部操作由应用角色控制。应用角色不能突破所属知识库状态。知识库停用时，App 和 Key 不自动删除，但 App Runtime 必须拒绝新调用。

## 8. 典型业务操作流程

### 8.1 创建文档库

```text
用户为 platform_user 或 platform_admin
-> 创建 DocumentLibrary
-> 创建者自动成为 library_owner
```

### 8.2 上传文档

```text
校验 library.document.create
-> 保存 StoredFile
-> 创建 Document
-> 创建 DocumentVersion
-> 创建解析任务
```

### 8.3 文档版本切换

```text
校验 library.version.activate
-> 校验目标版本解析成功
-> 展示影响预览
-> 切换 Document.active_version_id
```

文档库 active version 切换不应自动改变已绑定知识库使用的版本。知识库绑定版本变更应走单独的绑定更新流程。

### 8.4 绑定文档到知识库

```text
校验源文档库 library.document.bind
-> 校验目标知识库 kb.document.bind
-> 校验目标文档版本解析成功
-> 创建或更新 DocumentKbBinding
-> 创建 KB 侧 Chunk 和检索副本
```

该流程必须同时满足源文档库和目标知识库两侧权限。

### 8.5 重建知识库索引

```text
校验 kb.document.rebuild
-> 校验知识库未禁用
-> 创建 IndexSyncJob 或 IngestJob
-> 根据 PostgreSQL 真值重建检索副本
```

### 8.6 运行 QA

```text
校验 kb.qa.run
-> 校验知识库 active
-> 校验存在可运行 ConfigRevision
-> 执行检索、权限裁剪、生成和 Citation
-> 写入 QARun 历史
```

`kb_qa_runner` 只能查看自己创建的 QA 运行结果；`kb_viewer` 及以上角色可查看知识库范围的 QA 历史。

### 8.7 创建智能应用

```text
校验 kb.app.manage
-> 校验知识库 active
-> 校验存在可运行 ConfigRevision
-> 创建 RagApp
-> 创建者自动成为 app_owner
```

### 8.8 生成 API Key

```text
校验 app.key.manage
-> 生成高熵 API Key
-> 仅保存 key_hash 和 key_prefix
-> 明文只在创建响应中展示一次
```

### 8.9 App Runtime 调用

```text
校验 App API Key
-> 解析 RagApp
-> 校验 App active
-> 校验 KnowledgeBase active
-> 使用 App 绑定的知识库和配置执行 QA
-> 写 AppInvocation / AppMessage / QARun
```

Runtime 不接受请求体传入 `kbId`、用户权限、主体过滤条件或 Provider 密钥。

## 9. 用户组授权规则

用户组可以被绑定到文档库、知识库或智能应用，并授予对应资源角色。权限计算流程为：

```text
读取用户直接资源角色
-> 读取用户所属有效用户组在该资源上的角色
-> 合并角色对应权限码
-> 得到有效权限集合
```

同一资源内只做 allow 并集。示例：

| 用户直接角色 | 用户组角色 | 最终权限 |
| --- | --- | --- |
| `library_viewer` | `library_editor` | 按 `library_editor` 执行 |
| 无直接角色 | `kb_qa_runner` | 可运行 QA 并查看自己的结果 |
| `app_viewer` | `app_operator` | 可管理 Key、查看记录、试运行 |

跨资源操作继续分别校验每个资源。例如用户通过用户组获得文档库绑定权限，但没有目标知识库绑定权限时，仍不能完成绑定。

## 10. 状态与安全边界

- 文档库禁用后，不允许新增、更新、删除或绑定文档；已有知识库绑定按知识库侧状态继续治理或由管理员解绑。
- 知识库禁用后，不允许新增绑定、重建索引、运行 QA 或 Runtime 调用；历史数据仍按权限可读。
- 智能应用禁用后，Runtime 调用拒绝，调用记录和统计仍按应用权限可读。
- 知识库停用不自动删除 App 或 API Key；知识库恢复 active 后，仍 active 且 Key 未过期的 App 可以恢复调用。
- 文档、版本、Chunk 和 QA 历史默认使用软删除、归档或退役状态，不做同步硬删除。
- QA 历史事实不可变；文档删除、版本切换、Chunk 退役只影响未来检索，不改写历史 QARun。

## 11. 首版不做范围

- 不引入显式 deny。
- 不做字段级权限。
- 不做基于内容标签的 ABAC 策略。
- 不做跨租户组织继承。
- 不把 App Runtime 与后台用户登录态混用。
- 不允许前端自行推导最终授权结果。

## 12. 验收关注点

- 普通用户无资源角色时不能访问他人资源。
- 用户直接角色和用户组角色在同一资源内按权限并集生效。
- 绑定文档到知识库必须同时校验 `library.document.bind` 和 `kb.document.bind`。
- `kb_qa_runner` 只能查看自己的 QA 运行结果。
- 创建 App 必须具备所属知识库的 `kb.app.manage`。
- API Key 管理必须具备 `app.key.manage`。
- 知识库 disabled 时 App Runtime 返回稳定错误，不删除 App 和 Key。
- 前端隐藏按钮只作为交互优化，后端必须执行最终权限判定。

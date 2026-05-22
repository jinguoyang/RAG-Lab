# Sprint 42 三层架构现有页面补齐设计

本文档是活文档，用于指导本次前端重做。目标是在不引入新设计系统、不新增独立菜单的前提下，把 Sprint 40-43 的三层架构能力补回现有文档库、知识库文档和应用中心页面。

## 1. 关键假设

- 继续使用正式前端 `frontend/`，不修改 `screanshot/prototype/`。
- 后端三层生命周期能力已基本存在，本次只补前端必要的 DTO 字段和最小 API 返回信息。
- 不新增三层架构总入口；P17/P18/P19、P06/P12、P13 是本次主要承载页。
- 不重写全站布局，不新增设计系统，不做与 Sprint 42 无关的图谱可视化。

## 2. 视觉主张

界面保持当前后台产品的克制风格，在现有菜单内强化“三层链路”：文档库负责文件和版本，知识库文档负责绑定和 BindingRevision，应用中心负责 Runtime、Key 和权限边界。右侧 Drawer 承载版本切换、删除影响、权限来源和 Runtime 拒绝原因等细节。

## 3. 页面结构

页面分区：

- 文档库：重构列表和库详情说明，突出可见性、成员权限、版本、ParseRevision 和删除影响。
- 知识库文档：展示当前绑定、BindingRevision 状态、版本切换和知识库权限摘要。
- 应用中心：增加权限管理区，说明应用运行权限继承自所属知识库和 API Key 状态，并提供跳转管理入口。

## 4. 现有页面补齐

- P06 文档中心：增加已绑定文档区，显示 BindingRevision 状态和“切换版本”入口，并补充知识库文档权限摘要。
- P12 成员与权限：用统一的权限来源展示组件，区分平台角色、直接知识库角色和用户组继承。
- P13 应用中心：增加权限管理区，展示所属知识库状态、Key 可用性和授权入口。
- P17/P18/P19 文档库：重构说明和状态摘要，明确文档库权限与知识库权限的边界。
- P10、P16：保留现有实现，必要时只补导航和文案，不重做主体。

## 5. 数据与接口

前端新增统一展示工具：

- `bindingRevisionStatusLabel(status)`
- `bindingRevisionStatusVariant(status)`
- `permissionSourceLabel(source)`
- `layerLabel(layer)`

绑定 DTO 需要包含可选字段：

- `activeBindingRevisionId`
- `bindingRevisionStatus`
- `bindingRevisionChunkCount`
- `bindingRevisionVersionId`

如果后端绑定列表已有 `active_binding_revision_id`，服务层将其映射为 camelCase 字段；如果暂时没有 active revision，则前端回退到绑定自身 `status`。

## 6. 验收标准

- 不新增独立 `三层工作台` 入口，现有菜单保持为文档库、应用中心和知识库内页。
- 文档库页面能解释文档库权限、版本和后续知识库绑定边界。
- P06 能直接看到每个绑定的 BindingRevision 状态，并可进入版本切换。
- P12 能清楚解释权限来源是平台角色、直接授权还是用户组继承。
- P13 能展示应用运行权限边界、Key 可用性和所属知识库权限管理入口。
- 前端 `npm run lint`、`npm run test`、`npm run build` 通过。
- 若修改后端 DTO，后端 `python -m compileall app` 通过。

## 7. 不做范围

- 不新增复杂三层图谱画布。
- 不替换现有 P06/P10/P12/P13/P16 的主体业务实现。
- 不把 mock 验证表述为真实 Provider 通过。
- 不同步改写历史 Sprint 正文。

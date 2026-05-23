# 合并入库与索引同步 Tab 实施计划

> 本文为本次页面收敛的实施记录，状态以实际代码和验证结果为准。

**目标：** 将文档详情页的“入库作业”和“索引同步作业”两个 Tab 合并为一个“处理作业” Tab，同时精简 Chunks Tab 的状态列、合并处理作业的状态与阶段列、处理链路 Badge 只保留阶段标签并用颜色表达状态。

**架构：** 在 `P07_DocumentDetail.tsx` 中移除 `indexSync` Tab 及其相关状态和 API 调用，在 `jobs` Tab 中收敛处理链路展示。前端 `documentService` 和 `types/document.ts` 同步清理已经没有调用方的旧客户端封装，后端 DTO 和接口不在本次页面收敛中删除。

**技术栈：** React、TypeScript、Radix Tabs、Badge/StatusBadge 组件

---

## 文件变更总览

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/app/pages/P07_DocumentDetail.tsx` | 修改 | 主要改动文件：合并 Tab、删除 `indexSync` 页面状态、精简表格列 |
| `frontend/src/app/adapters/documentAdapter.ts` | 修改 | 调整副本状态标签和作业视图字段 |
| `frontend/src/app/types/document.ts` | 修改 | 清理前端无调用方的旧 IndexSync 展示类型 |
| `frontend/src/app/services/documentService.ts` | 修改 | 清理前端无调用方的旧 reparse/index-sync 客户端函数 |

---

### 任务 1：移除 indexSync Tab 及相关 state 和 API 调用

**涉及文件：**
- 修改：`frontend/src/app/pages/P07_DocumentDetail.tsx`

- [x] **步骤 1：移除 indexSyncJobs state 和 rebuildTargetStore state**

删除以下 state 声明：
```tsx
// 删除这一行
const [indexSyncJobs, setIndexSyncJobs] = useState<IndexSyncJobDTO[]>([]);
// 删除这一行
const [rebuildTargetStore, setRebuildTargetStore] = useState("milvus");
```

- [x] **步骤 2：移除 loadData 中的 fetchIndexSyncJobs 调用**

在 `loadData` 函数中，将：
```tsx
const [nextDetail, nextVersions, nextJobs, nextIndexSyncJobPage] = await Promise.all([
  fetchDocumentDetail(kbId, docId),
  fetchDocumentVersions(kbId, docId),
  fetchIngestJobs(kbId, docId),
  fetchIndexSyncJobs(kbId, docId),
]);
// ...
setIndexSyncJobs(nextIndexSyncJobPage.items);
```

改为：
```tsx
const [nextDetail, nextVersions, nextJobs] = await Promise.all([
  fetchDocumentDetail(kbId, docId),
  fetchDocumentVersions(kbId, docId),
  fetchIngestJobs(kbId, docId),
]);
// 删除 setIndexSyncJobs 那一行
```

- [x] **步骤 3：移除 handleDocumentIndexRebuild 函数**

删除整个 `handleDocumentIndexRebuild` 函数（约第 278-303 行）。

- [x] **步骤 4：移除 Tab trigger 和 Tab content**

删除 indexSync 的 trigger：
```tsx
<UnderlineTabsTrigger value="indexSync">
  索引同步作业（{indexSyncJobs.length}）
</UnderlineTabsTrigger>
```

删除整个 `<UnderlineTabsContent value="indexSync"> ... </UnderlineTabsContent>` 块（约第 581-626 行）。

- [x] **步骤 5：清理未使用的 import**

从 import 中移除不再使用的：
- `Database` (lucide-react) — 仅用于重建索引按钮
- `rebuildIndexSync` (documentService)
- `fetchIndexSyncJobs` (documentService)
- `IndexSyncJobDTO` (types/document)

检查 `formatIndexStageStatus` 是否仍被版本 tab 使用 — 如果是则保留。

- [x] **步骤 6：验证**

在浏览器中打开文档详情页，确认：
- 只有 3 个 tab（版本、Chunks、处理作业）
- 页面无报错
- 版本 tab 的副本状态 Badge 仍正常显示

---

### 任务 2：将入库作业 Tab 重命名为“处理作业”并合并状态和阶段展示

**涉及文件：**
- 修改：`frontend/src/app/pages/P07_DocumentDetail.tsx`

- [x] **步骤 1：重命名 Tab trigger**

将：
```tsx
<UnderlineTabsTrigger value="jobs">
  入库作业（{jobRows.length}）
</UnderlineTabsTrigger>
```

改为：
```tsx
<UnderlineTabsTrigger value="jobs">
  处理作业（{jobRows.length}）
</UnderlineTabsTrigger>
```

- [x] **步骤 2：合并状态和阶段展示**

将 jobs tab 的表头从：
```tsx
<TableHead>作业 ID</TableHead>
<TableHead>状态</TableHead>
<TableHead>阶段</TableHead>
<TableHead>处理链路</TableHead>
<TableHead>进度</TableHead>
<TableHead>创建时间</TableHead>
<TableHead>错误信息</TableHead>
<TableHead>操作</TableHead>
```

改为：
```tsx
<TableHead>作业 ID</TableHead>
<TableHead>状态/阶段</TableHead>
<TableHead>处理链路</TableHead>
<TableHead>进度</TableHead>
<TableHead>创建时间</TableHead>
<TableHead>错误信息</TableHead>
<TableHead>操作</TableHead>
```

- [x] **步骤 3：调整状态和阶段的 TableCell**

将：
```tsx
<TableCell><StatusBadge status={row.status} /></TableCell>
<TableCell>{row.stage}</TableCell>
```

改为：
```tsx
<TableCell>
  <div className="flex items-center gap-2">
    <StatusBadge status={row.status} />
    <span className="text-xs text-stone-gray">{row.stage}</span>
  </div>
</TableCell>
```

- [x] **步骤 4：处理链路 Badge 只保留阶段标签，状态通过颜色和悬浮提示表达**

将：
```tsx
{row.indexStages.map((stage) => (
  <Badge key={stage.key} variant={indexStageVariant(stage.status)}>
    {stage.label}: {formatIndexStageStatus(stage.status)}
  </Badge>
))}
```

改为：
```tsx
{row.indexStages.map((stage) => (
  <Badge key={stage.key} variant={indexStageVariant(stage.status)} title={`${stage.label}: ${formatIndexStageStatus(stage.status)}`}>
    {stage.label}
  </Badge>
))}
```

这样 Badge 只显示阶段名（如"解析"、"Milvus"），通过颜色区分状态，hover 时 title 显示完整信息。

- [x] **步骤 5：验证**

在浏览器中确认：
- tab 名称显示为"处理作业"
- 状态和阶段合并为一列，StatusBadge + 阶段文字并排
- 处理链路 Badge 只显示阶段名，颜色正确区分状态
- hover Badge 显示完整状态信息

---

### 任务 3：Chunks Tab 移除状态列

**涉及文件：**
- 修改：`frontend/src/app/pages/P07_DocumentDetail.tsx`

- [x] **步骤 1：移除表头中的状态列**

将：
```tsx
<TableHead>序号</TableHead>
<TableHead>回溯版本</TableHead>
<TableHead>页码</TableHead>
<TableHead>章节 / 位置</TableHead>
<TableHead>正文摘要</TableHead>
<TableHead>Token</TableHead>
<TableHead>状态</TableHead>
<TableHead>操作</TableHead>
```

改为：
```tsx
<TableHead>序号</TableHead>
<TableHead>回溯版本</TableHead>
<TableHead>页码</TableHead>
<TableHead>章节 / 位置</TableHead>
<TableHead>正文摘要</TableHead>
<TableHead>Token</TableHead>
<TableHead>操作</TableHead>
```

- [x] **步骤 2：移除表格行中的状态单元格**

删除：
```tsx
<TableCell><StatusBadge status={chunks[index].status === "active" ? "success" : chunks[index].status === "retired" ? "cancelled" : "failed"} /></TableCell>
```

- [x] **步骤 3：确认无需保留旧空状态 colSpan**

如果有空状态行，将 `colSpan` 从 8 改为 7（如果有的话）。

- [x] **步骤 4：验证**

在浏览器中确认：
- Chunks 表格没有状态列
- 其他列正常显示
- 分页正常

---

### 任务 4：版本 Tab 处理链路同步收敛

**涉及文件：**
- 修改：`frontend/src/app/pages/P07_DocumentDetail.tsx`

- [x] **步骤 1：版本 Tab 的副本状态 Badge 只显示阶段标签**

将版本 tab 中的：
```tsx
{row.indexStages.map((stage) => (
  <Badge key={stage.key} variant={indexStageVariant(stage.status)}>
    {stage.label}: {formatIndexStageStatus(stage.status)}
  </Badge>
))}
```

改为：
```tsx
{row.indexStages.map((stage) => (
  <Badge key={stage.key} variant={indexStageVariant(stage.status)} title={`${stage.label}: ${formatIndexStageStatus(stage.status)}`}>
    {stage.label}
  </Badge>
))}
```

- [x] **步骤 2：验证**

在浏览器中确认版本 tab 的副本状态列只显示阶段名 Badge，颜色区分状态。

---

### 任务 5：最终验证

- [x] **步骤 1：全量功能验证**

在浏览器中打开文档详情页，逐一检查：

1. **版本 tab**: 4 列（版本、状态、解析状态、副本状态），副本状态 Badge 只显示阶段名 + 颜色
2. **Chunks tab**: 7 列（无状态列），分页正常
3. **处理作业 tab**: 7 列（状态/阶段合并），处理链路 Badge 只显示阶段名 + 颜色，重试/取消按钮功能正常
4. 不存在"索引同步作业" tab
5. 不存在"重建索引"按钮
6. 页面无 console error

- [x] **步骤 2：确认无残留引用**

检查 `P07_DocumentDetail.tsx` 中不再引用：
- `indexSyncJobs` state
- `rebuildTargetStore` state
- `handleDocumentIndexRebuild` 函数
- `fetchIndexSyncJobs` import
- `rebuildIndexSync` import
- `IndexSyncJobDTO` import
- `Database` icon import

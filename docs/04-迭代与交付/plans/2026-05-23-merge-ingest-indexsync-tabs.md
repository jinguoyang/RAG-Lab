# 合并入库/索引同步 Tab 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将文档详情页的"入库作业"和"索引同步作业"两个 tab 合并为一个"处理作业" tab，同时精简 Chunks tab 的状态列、合并处理作业的状态与阶段列、去掉处理链路中的文字标签只保留颜色 Badge。

**Architecture:** 在 `P07_DocumentDetail.tsx` 中移除 indexSync tab 及其相关 state/API 调用，在 jobs tab 中将状态和阶段合并为一列，处理链路 Badge 只用颜色区分。Chunks tab 移除状态列。adapter 和 types 保持不变（后端 DTO 不变，只改前端展示逻辑）。

**Tech Stack:** React, TypeScript, Radix UnderlineTabs, Badge/StatusBadge 组件

---

## 文件变更总览

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/app/pages/P07_DocumentDetail.tsx` | Modify | 主要改动文件：合并 tab、删 indexSync 相关代码、精简表格列 |
| `frontend/src/app/adapters/documentAdapter.ts` | 不变 | adapter 逻辑不变，`formatIndexStageStatus` 仍用于版本 tab |
| `frontend/src/app/types/document.ts` | 不变 | DTO 类型不变 |
| `frontend/src/app/services/documentService.ts` | 不变 | API 函数保留（其他页面可能用到） |

---

### Task 1: 移除 indexSync tab 及相关 state 和 API 调用

**Files:**
- Modify: `frontend/src/app/pages/P07_DocumentDetail.tsx`

- [ ] **Step 1: 移除 indexSyncJobs state 和 rebuildTargetStore state**

删除以下 state 声明：
```tsx
// 删除这一行
const [indexSyncJobs, setIndexSyncJobs] = useState<IndexSyncJobDTO[]>([]);
// 删除这一行
const [rebuildTargetStore, setRebuildTargetStore] = useState("milvus");
```

- [ ] **Step 2: 移除 loadData 中的 fetchIndexSyncJobs 调用**

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

- [ ] **Step 3: 移除 handleDocumentIndexRebuild 函数**

删除整个 `handleDocumentIndexRebuild` 函数（约第 278-303 行）。

- [ ] **Step 4: 移除 tab trigger 和 tab content**

删除 indexSync 的 trigger：
```tsx
<UnderlineTabsTrigger value="indexSync">
  索引同步作业（{indexSyncJobs.length}）
</UnderlineTabsTrigger>
```

删除整个 `<UnderlineTabsContent value="indexSync"> ... </UnderlineTabsContent>` 块（约第 581-626 行）。

- [ ] **Step 5: 清理未使用的 import**

从 import 中移除不再使用的：
- `Database` (lucide-react) — 仅用于重建索引按钮
- `rebuildIndexSync` (documentService)
- `fetchIndexSyncJobs` (documentService)
- `IndexSyncJobDTO` (types/document)

检查 `formatIndexStageStatus` 是否仍被版本 tab 使用 — 如果是则保留。

- [ ] **Step 6: 验证并提交**

在浏览器中打开文档详情页，确认：
- 只有 3 个 tab（版本、Chunks、处理作业）
- 页面无报错
- 版本 tab 的副本状态 Badge 仍正常显示

```bash
git add frontend/src/app/pages/P07_DocumentDetail.tsx
git commit -m "feat: remove indexSync tab, merge into jobs tab"
```

---

### Task 2: 将入库作业 tab 重命名为"处理作业"并合并状态+阶段列

**Files:**
- Modify: `frontend/src/app/pages/P07_DocumentDetail.tsx`

- [ ] **Step 1: 重命名 tab trigger**

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

- [ ] **Step 2: 合并状态和阶段列为一列**

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

- [ ] **Step 3: 合并状态和阶段的 TableCell**

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

- [ ] **Step 4: 处理链路 Badge 去掉文字，只保留颜色**

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

- [ ] **Step 5: 验证并提交**

在浏览器中确认：
- tab 名称显示为"处理作业"
- 状态和阶段合并为一列，StatusBadge + 阶段文字并排
- 处理链路 Badge 只显示阶段名，颜色正确区分状态
- hover Badge 显示完整状态信息

```bash
git add frontend/src/app/pages/P07_DocumentDetail.tsx
git commit -m "feat: merge status/stage column, badges show color only"
```

---

### Task 3: Chunks tab 移除状态列

**Files:**
- Modify: `frontend/src/app/pages/P07_DocumentDetail.tsx`

- [ ] **Step 1: 移除表头中的状态列**

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

- [ ] **Step 2: 移除表格行中的状态单元格**

删除：
```tsx
<TableCell><StatusBadge status={chunks[index].status === "active" ? "success" : chunks[index].status === "retired" ? "cancelled" : "failed"} /></TableCell>
```

- [ ] **Step 3: 更新空状态 colSpan**

如果有空状态行，将 `colSpan` 从 8 改为 7（如果有的话）。

- [ ] **Step 4: 验证并提交**

在浏览器中确认：
- Chunks 表格没有状态列
- 其他列正常显示
- 分页正常

```bash
git add frontend/src/app/pages/P07_DocumentDetail.tsx
git commit -m "feat: remove status column from chunks tab"
```

---

### Task 4: 版本 tab 处理链路同步去掉文字

**Files:**
- Modify: `frontend/src/app/pages/P07_DocumentDetail.tsx`

- [ ] **Step 1: 版本 tab 的副本状态 Badge 也去掉文字**

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

- [ ] **Step 2: 验证并提交**

在浏览器中确认版本 tab 的副本状态列只显示阶段名 Badge，颜色区分状态。

```bash
git add frontend/src/app/pages/P07_DocumentDetail.tsx
git commit -m "feat: version tab badges show color only, consistent with jobs tab"
```

---

### Task 5: 最终验证

- [ ] **Step 1: 全量功能验证**

在浏览器中打开文档详情页，逐一检查：

1. **版本 tab**: 4 列（版本、状态、解析状态、副本状态），副本状态 Badge 只显示阶段名 + 颜色
2. **Chunks tab**: 7 列（无状态列），分页正常
3. **处理作业 tab**: 7 列（状态/阶段合并），处理链路 Badge 只显示阶段名 + 颜色，重试/取消按钮功能正常
4. 不存在"索引同步作业" tab
5. 不存在"重建索引"按钮
6. 页面无 console error

- [ ] **Step 2: 确认无残留引用**

检查 `P07_DocumentDetail.tsx` 中不再引用：
- `indexSyncJobs` state
- `rebuildTargetStore` state
- `handleDocumentIndexRebuild` 函数
- `fetchIndexSyncJobs` import
- `rebuildIndexSync` import
- `IndexSyncJobDTO` import
- `Database` icon import

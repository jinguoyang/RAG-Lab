# Sprint 43 回归验收与文档同步设计

## 1. 背景与目标

Sprint 43 是 E30（三层架构模型收口）的最终 Sprint。Sprint 40 完成数据模型基线和权限，Sprint 41 完成后端生命周期改造，Sprint 42 完成前端体验改造。本轮不再新增功能，目标是：

- 用端到端自动化测试证明三层模型可运行、可追溯、可治理
- 同步接口设计、数据模型、测试计划和 OpenAPI
- 回填 E30 验收结论

### 关键决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| 验收范围 | 前后端全链路 | 验证完整用户路径 |
| 测试方式 | Playwright E2E 自动化 | 可重复、可追溯、覆盖真实 UI 交互 |
| 文档同步 | 全量同步 | OpenAPI + 设计文档一致性 + E30 验收结论 |
| LLM Provider | 真实 Provider | 验证完整链路，不 mock |

### 前置依赖

- Sprint 41 后端代码已合并（commit `3fc1a3b5`）
- Sprint 42 前端代码已完成并合并
- 测试环境可用：PostgreSQL、真实 LLM API Key、对象存储

## 2. 测试架构

### 2.1 目录结构

```
frontend/
  e2e/
    fixtures/                  # 测试数据 fixture
      seed-payloads.ts         # 预置数据定义
      test-files/              # 测试用文件（PDF、DOCX 等）
    tests/
      b214-main-flow.spec.ts   # 主链路 E2E
      b215-deletion-regression.spec.ts  # 删除回归
      b216-permission-runtime.spec.ts   # 权限与 Runtime 回归
      b217-doc-sync.spec.ts    # 文档一致性校验
    helpers/
      auth.ts                  # 登录、token 管理
      navigation.ts            # 页面导航封装
      assertions.ts            # 通用断言（状态轮询、元素等待）
      seed.ts                  # seed API 调用封装
    playwright.config.ts
```

### 2.2 技术选型

- **Playwright Test**：测试框架，内置断言、截图、trace 录制
- **Chromium 单浏览器**：回归验收不需要跨浏览器覆盖
- **真实 PostgreSQL**：E2E 测试使用真实数据库，不使用 SQLite in-memory
- **真实 LLM Provider**：通过环境变量注入 API Key

### 2.3 与现有测试的关系

| 测试层 | 工具 | 数据库 | LLM | 运行时机 |
|---|---|---|---|---|
| 后端单测 | pytest | SQLite in-memory | mock | 每次提交 |
| 后端集成测试 | pytest | SQLite in-memory | mock | 每次提交 |
| 前端单测 | vitest | N/A | N/A | 每次提交 |
| E2E 验收 | Playwright | PostgreSQL | 真实 Provider | Sprint 验收 |

## 3. 测试场景设计

### 3.1 B-214：三层主链路 E2E（P0，2d）

脚本：`b214-main-flow.spec.ts`

| 步骤 | 操作 | 断言 |
|---|---|---|
| 1 | 登录 → 进入文档库 → 上传 PDF | 文档列表出现新文档，版本号 = 1 |
| 2 | 等待解析完成（轮询状态） | ParseRevision status = completed，content_text 非空 |
| 3 | 进入知识库文档中心 → 选择文档版本 → 绑定 | BindingRevision status = building → 等待 → status = active，chunk_count > 0 |
| 4 | 上传同一文档第二版本 → 绑定新版本 | 新 BindingRevision = active，旧 = retired |
| 5 | 进入 QA 调试页 → 提问 | 返回答案，evidence 有内容，source_status = available |
| 6 | 通过 API 调用 App Runtime | 返回 200，invocation 记录写入 |

### 3.2 B-215：删除和清理回归（P0，1.5d）

脚本：`b215-deletion-regression.spec.ts`

| 步骤 | 操作 | 断言 |
|---|---|---|
| 1 | 尝试删除有 active BindingRevision 的文档版本 | 删除被拒绝，错误信息包含影响分析 |
| 2 | 删除仅被历史 QA 引用的旧版本 | 弹出确认弹窗，显示影响分析 |
| 3 | 确认删除 | QA 历史仍可打开，evidence 显示"引用文件已被清理" |
| 4 | 删除后检索当前 KB | 检索正常返回结果 |
| 5 | 删除后调用 App Runtime | 返回 200，不受旧版本删除影响 |

### 3.3 B-216：权限矩阵和 Runtime 状态回归（P0，1.5d）

脚本：`b216-permission-runtime.spec.ts`

| 步骤 | 操作 | 断言 |
|---|---|---|
| 1 | platform_admin 操作所有文档库和知识库 | 全部成功 |
| 2 | library_viewer 尝试删除文档版本 | 被拒绝 |
| 3 | 用户通过用户组获得 kb_editor → 绑定文档 | 成功 |
| 4 | 无 library.document.bind 权限的用户尝试绑定 | 被拒绝 |
| 5 | 禁用知识库 → 调用 App Runtime | 返回 KB_DISABLED 错误码 |
| 6 | 检查 App 和 Key | 未被删除 |

### 3.4 B-217：文档同步校验（P1，1.5d）

混合 Playwright + 脚本：

| 步骤 | 操作 | 断言 |
|---|---|---|
| 1 | 运行 `export_openapi.py` | 成功，输出文件存在 |
| 2 | 运行 `check_api_contract.py` | OpenAPI schema 与前端 types 字段一致 |
| 3 | 对照 E30 架构简报核心规则 vs 代码 | 无冲突 |
| 4 | 回填 E30 验收结论 | Sprint 43 文档更新 |

核心规则校验清单：

- 同一 DocumentKbBinding 同一时刻只有一个 active BindingRevision
- 默认检索只使用 active BindingRevision 下的 active Chunk
- 删除支撑 active BindingRevision 的文档版本被拒绝
- 知识库 disabled 时 App Runtime 返回稳定错误，不删除 App 和 Key
- 用户直接角色 + 用户组角色 = allow 并集
- 跨资源操作必须检查双方权限

## 4. 后端配套变更

Sprint 43 不新增业务功能，但需要以下配套变更以支持 E2E 测试和文档同步：

### 4.1 Seed API（测试专用）

新增 `POST /api/test/seed` 端点，仅在 `ENVIRONMENT=testing` 时注册路由。

功能：接受 JSON payload，批量创建用户、角色绑定、文档库、知识库等测试前置数据。

安全：非 testing 环境下该路由不存在，不会被意外调用。

### 4.2 API 契约检查脚本

新增 `backend/scripts/check_api_contract.py`：
- 读取 `docs/06-发布与运维/openapi.json` 中的 schema
- 解析前端 `frontend/src/app/types/*.ts` 中的类型定义
- 对比字段名、类型、必填性
- 输出不一致清单到 stdout，exit code 0 = 全部一致，1 = 有差异

### 4.3 现有测试保留

Sprint 41 的 47 单测 + 10 集测继续保留，不做修改。Sprint 43 E2E 测试是新增层，与现有测试独立运行。

## 5. 测试数据管理

### 5.1 数据策略

每个测试文件独立管理数据生命周期：

- **beforeAll**：通过 seed API 创建测试所需的文档库、知识库、用户、角色绑定
- **测试内**：每个 it() 块操作自己的数据
- **afterAll**：清理测试数据（删除文档库会级联清理所有子资源）

### 5.2 Seed API payload 示例

```json
{
  "users": [
    { "username": "admin", "platform_role": "platform_admin" },
    { "username": "lib_viewer", "platform_role": "platform_user" }
  ],
  "libraries": [
    {
      "name": "test-library",
      "members": [
        { "username": "admin", "role": "library_owner" },
        { "username": "lib_viewer", "role": "library_viewer" }
      ]
    }
  ],
  "knowledge_bases": [
    {
      "name": "test-kb",
      "library_name": "test-library",
      "members": [
        { "username": "admin", "role": "kb_owner" }
      ]
    }
  ]
}
```

### 5.3 环境变量

```env
TEST_BASE_URL=http://localhost:5173
TEST_API_URL=http://localhost:8000
TEST_LLM_API_KEY=sk-xxx
TEST_LLM_PROVIDER=openai
ENVIRONMENT=testing
```

### 5.4 Playwright 配置

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/tests',
  timeout: 60_000,
  retries: 1,
  use: {
    baseURL: process.env.TEST_BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

## 6. 文档同步策略

### 6.1 OpenAPI 导出

```powershell
cd backend
conda run -n rag-lab python scripts/export_openapi.py
```

### 6.2 前后端字段一致性脚本

运行 `check_api_contract.py`（详见 4.2），对比 OpenAPI schema 与前端 TypeScript types，输出不一致清单。

### 6.3 设计文档一致性检查

逐条对照以下文档中的核心规则 vs 代码实现：

- `specs/2026-05-21-document-kb-app-architecture-briefing.md`
- `specs/2026-05-20-permission-role-model-design.md`
- `specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `specs/2026-05-21-knowledge-base-chunk-management-design.md`

冲突项标记在 Sprint 43 验收报告中。

### 6.4 E30 验收结论回填

在本文档末尾追加"验收结论"章节，记录每条验收标准的通过/未通过状态和证据。

## 7. 验收标准

| 编号 | 验收标准 | 验证方式 |
|---|---|---|
| AC-1 | 三层主链路端到端通过 | B-214 Playwright 测试全部绿 |
| AC-2 | 删除旧版本不破坏当前 KB 检索和 App Runtime | B-215 测试通过 |
| AC-3 | 历史 QA 引用源清理后仍可打开 | B-215 测试中断言 |
| AC-4 | 权限矩阵覆盖全部角色组合 | B-216 测试通过 |
| AC-5 | OpenAPI 导出成功且与前端 types 一致 | B-217 脚本通过 |
| AC-6 | 设计文档与 E30 已确认规则无冲突 | B-217 人工 review |
| AC-7 | 全部自动化测试可重复执行 | 连续跑 2 次结果一致 |

## 8. 验证命令

```powershell
# 后端验证
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests
conda run -n rag-lab python scripts/export_openapi.py
conda run -n rag-lab python scripts/check_api_contract.py

# 前端验证
cd frontend
npm run lint
npm run test
npm run build

# E2E 验证（需要前后端都运行中）
cd frontend
npx playwright test

# Git 检查
git diff --check
```

## 9. 范围边界

- 不在本轮新增未规划功能
- 不为了同步历史归档而改写旧 Sprint 正文
- 不把本地 mock 验证表述为真实 Provider 网络级通过
- 不引入跨浏览器测试（仅 Chromium）
- 不实现视觉回归测试（截图对比）

## 10. 关联文档

- `../../plans/2026-05-21-e30-three-layer-architecture-refactor.md`
- `../../specs/2026-05-20-permission-role-model-design.md`
- `../../specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `../../specs/2026-05-21-knowledge-base-chunk-management-design.md`
- `../../specs/2026-05-21-document-kb-app-architecture-briefing.md`
- `../../specs/2026-05-21-sprint42-three-layer-frontend-design.md`

## 11. 验收结论

> 待 Sprint 43 执行完成后填写。

| 编号 | 验收标准 | 状态 | 证据 |
|---|---|---|---|
| AC-1 | 三层主链路端到端通过 | 待验收 | |
| AC-2 | 删除旧版本不破坏当前 KB 检索和 App Runtime | 待验收 | |
| AC-3 | 历史 QA 引用源清理后仍可打开 | 待验收 | |
| AC-4 | 权限矩阵覆盖全部角色组合 | 待验收 | |
| AC-5 | OpenAPI 导出成功且与前端 types 一致 | 待验收 | |
| AC-6 | 设计文档与 E30 已确认规则无冲突 | 待验收 | |
| AC-7 | 全部自动化测试可重复执行 | 待验收 | |

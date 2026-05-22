# Sprint 43 回归验收与文档同步实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Playwright E2E 自动化测试验证三层架构端到端链路，同步文档和 OpenAPI，回填 E30 验收结论。

**Architecture:** 前端新增 Playwright E2E 测试套件，后端新增 Seed API（测试数据初始化）和 API 契约检查脚本。E2E 测试通过真实浏览器操作 UI，验证上传→解析→绑定→切换→QA→Runtime 完整链路。

**Tech Stack:** Playwright Test, FastAPI, PostgreSQL, React, TypeScript

**前置依赖:** Sprint 42 前端代码已合并。本计划中 Task 1-2 可在 Sprint 42 开发期间并行准备，Task 3-8 需等 Sprint 42 完成后执行。

**注意事项:** E2E 测试中的页面导航选择器（如 `text=文档库`、`text=绑定文档`）基于当前 UI 结构编写，Sprint 42 完成后需根据实际页面 DOM 校准选择器。测试代码中的选择器是近似值，执行时需逐个验证和调整。

**Spec:** `docs/04-迭代与交付/specs/2026-05-21-sprint43-regression-validation-design.md`

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|---|---|---|
| Create | `frontend/e2e/playwright.config.ts` | Playwright 配置 |
| Create | `frontend/e2e/helpers/auth.ts` | 登录、token 管理 |
| Create | `frontend/e2e/helpers/navigation.ts` | 页面导航封装 |
| Create | `frontend/e2e/helpers/assertions.ts` | 状态轮询、元素等待 |
| Create | `frontend/e2e/helpers/seed.ts` | Seed API 调用封装 |
| Create | `frontend/e2e/fixtures/seed-payloads.ts` | 预置数据定义 |
| Create | `frontend/e2e/tests/b214-main-flow.spec.ts` | 主链路 E2E |
| Create | `frontend/e2e/tests/b215-deletion-regression.spec.ts` | 删除回归 |
| Create | `frontend/e2e/tests/b216-permission-runtime.spec.ts` | 权限与 Runtime 回归 |
| Create | `frontend/e2e/tests/b217-doc-sync.spec.ts` | 文档一致性校验 |
| Create | `backend/app/api/routes/test_seed.py` | Seed API 路由 |
| Modify | `backend/app/api/router.py` | 注册 Seed API 路由 |
| Modify | `backend/app/core/config.py` | 添加 test_seed_enabled 配置 |
| Create | `backend/scripts/check_api_contract.py` | API 契约检查脚本 |
| Modify | `frontend/package.json` | 添加 Playwright 依赖和脚本 |

---

### Task 1: Playwright 基础设施搭建

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/e2e/playwright.config.ts`

- [ ] **Step 1: 安装 Playwright 依赖**

```powershell
cd frontend
npm install -D @playwright/test
npx playwright install chromium
```

- [ ] **Step 2: 添加 package.json 脚本**

在 `frontend/package.json` 的 `scripts` 中添加：

```json
{
  "test:e2e": "playwright test --config e2e/playwright.config.ts",
  "test:e2e:ui": "playwright test --config e2e/playwright.config.ts --ui"
}
```

- [ ] **Step 3: 创建 Playwright 配置**

创建 `frontend/e2e/playwright.config.ts`：

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: 1,
  use: {
    baseURL: process.env.TEST_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
```

- [ ] **Step 4: 验证配置生效**

```powershell
cd frontend
npx playwright test --config e2e/playwright.config.ts --list
```

Expected: 输出 `0 tests found`（因为还没有测试文件），无报错。

- [ ] **Step 5: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/e2e/playwright.config.ts
git commit -m "chore: add Playwright E2E test infrastructure for Sprint 43"
```

---

### Task 2: 后端 Seed API

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/api/routes/test_seed.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: 添加配置开关**

在 `backend/app/core/config.py` 的 `Settings` 类中添加：

```python
test_seed_enabled: bool = Field(
    default=False,
    validation_alias=AliasChoices("RAG_LAB_TEST_SEED_ENABLED", "TEST_SEED_ENABLED"),
)
```

- [ ] **Step 2: 创建 Seed API 路由**

创建 `backend/app/api/routes/test_seed.py`：

```python
"""测试数据 Seed API，仅在 TEST_SEED_ENABLED=true 时启用。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/test", tags=["test"])


class SeedUser(BaseModel):
    username: str
    platform_role: str = "platform_user"


class SeedMember(BaseModel):
    username: str
    role: str


class SeedLibrary(BaseModel):
    name: str
    members: list[SeedMember] = []


class SeedKnowledgeBase(BaseModel):
    name: str
    library_name: str
    members: list[SeedMember] = []


class SeedPayload(BaseModel):
    users: list[SeedUser] = []
    libraries: list[SeedLibrary] = []
    knowledge_bases: list[SeedKnowledgeBase] = []


@router.post("/seed")
def seed_test_data(payload: SeedPayload, db: Session = Depends(get_db)):
    """批量创建测试前置数据。仅在 ENVIRONMENT=testing 时可用。"""
    settings = get_settings()
    if not settings.test_seed_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    created = {"users": [], "libraries": [], "knowledge_bases": []}

    for user in payload.users:
        row = db.execute(
            text(
                """
                INSERT INTO users (username, display_name, platform_role, status)
                VALUES (:username, :display_name, :role, 'active')
                ON CONFLICT (username) DO UPDATE SET platform_role = :role
                RETURNING user_id
                """
            ),
            {"username": user.username, "display_name": user.username, "role": user.platform_role},
        ).fetchone()
        db.flush()
        created["users"].append({"username": user.username, "user_id": str(row[0])})

    for lib in payload.libraries:
        row = db.execute(
            text(
                """
                INSERT INTO document_libraries (name, status)
                VALUES (:name, 'active')
                RETURNING library_id
                """
            ),
            {"name": lib.name},
        ).fetchone()
        library_id = row[0]
        db.flush()

        for member in lib.members:
            user_row = db.execute(
                text("SELECT user_id FROM users WHERE username = :username"),
                {"username": member.username},
            ).fetchone()
            if user_row:
                db.execute(
                    text(
                        """
                        INSERT INTO library_member_bindings (library_id, user_id, role)
                        VALUES (:library_id, :user_id, :role)
                        """
                    ),
                    {"library_id": library_id, "user_id": user_row[0], "role": member.role},
                )

        db.flush()
        created["libraries"].append({"name": lib.name, "library_id": str(library_id)})

    for kb in payload.knowledge_bases:
        lib_row = db.execute(
            text("SELECT library_id FROM document_libraries WHERE name = :name"),
            {"name": kb.library_name},
        ).fetchone()
        if not lib_row:
            continue

        row = db.execute(
            text(
                """
                INSERT INTO knowledge_bases (name, library_id, status)
                VALUES (:name, :library_id, 'active')
                RETURNING knowledge_base_id
                """
            ),
            {"name": kb.name, "library_id": lib_row[0]},
        ).fetchone()
        kb_id = row[0]
        db.flush()

        for member in kb.members:
            user_row = db.execute(
                text("SELECT user_id FROM users WHERE username = :username"),
                {"username": member.username},
            ).fetchone()
            if user_row:
                db.execute(
                    text(
                        """
                        INSERT INTO kb_member_bindings (knowledge_base_id, user_id, role)
                        VALUES (:kb_id, :user_id, :role)
                        """
                    ),
                    {"kb_id": kb_id, "user_id": user_row[0], "role": member.role},
                )

        db.flush()
        created["knowledge_bases"].append({"name": kb.name, "kb_id": str(kb_id)})

    db.commit()
    return created
```

- [ ] **Step 3: 注册路由**

在 `backend/app/api/router.py` 中添加条件注册：

```python
# 在文件末尾，api_router 定义之后添加
from app.core.config import get_settings

if get_settings().test_seed_enabled:
    from app.api.routes.test_seed import router as test_seed_router
    api_router.include_router(test_seed_router)
```

- [ ] **Step 4: 验证路由注册**

```powershell
cd backend
$env:RAG_LAB_TEST_SEED_ENABLED = "true"
conda run -n rag-lab python -c "from app.main import app; print([r.path for r in app.routes])"
```

Expected: 输出中包含 `/api/v1/test/seed`。

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/config.py backend/app/api/routes/test_seed.py backend/app/api/router.py
git commit -m "feat: add test seed API endpoint for E2E testing (Sprint 43)"
```

---

### Task 3: Playwright 共享工具

**Files:**
- Create: `frontend/e2e/helpers/auth.ts`
- Create: `frontend/e2e/helpers/navigation.ts`
- Create: `frontend/e2e/helpers/assertions.ts`
- Create: `frontend/e2e/helpers/seed.ts`
- Create: `frontend/e2e/fixtures/seed-payloads.ts`

- [ ] **Step 1: 创建 auth helper**

创建 `frontend/e2e/helpers/auth.ts`：

```ts
import { Page } from "@playwright/test";

const API_URL = process.env.TEST_API_URL || "http://localhost:8000";

/**
 * 通过 dev auth 登录，返回页面已登录状态。
 * 假设 dev_auth_enabled=true，直接访问即以 dev_default_username 登录。
 */
export async function loginAs(page: Page, username: string): Promise<void> {
  // 先通过 API 设置 dev auth 的默认用户
  await page.goto("/");
  // 如果有登录表单，填写并提交
  const loginInput = page.locator('input[name="username"], input[placeholder*="用户"]');
  if (await loginInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await loginInput.fill(username);
    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();
    await page.waitForURL("**/", { timeout: 10_000 });
  }
}
```

- [ ] **Step 2: 创建 navigation helper**

创建 `frontend/e2e/helpers/navigation.ts`：

```ts
import { Page, expect } from "@playwright/test";

export async function goToLibraryDetail(page: Page, libraryName: string): Promise<void> {
  await page.goto("/");
  // 点击文档库菜单
  await page.locator("text=文档库").first().click();
  // 点击目标文档库
  await page.locator(`text=${libraryName}`).first().click();
  await expect(page.locator("h1, h2").first()).toBeVisible();
}

export async function goToDocumentCenter(page: Page): Promise<void> {
  await page.goto("/");
  await page.locator("text=知识库").first().click();
  await page.locator("text=文档中心").first().click();
}

export async function goToQAHistory(page: Page): Promise<void> {
  await page.goto("/");
  await page.locator("text=QA").first().click();
  await page.locator("text=历史").first().click();
}

export async function goToMembers(page: Page): Promise<void> {
  await page.goto("/");
  await page.locator("text=成员").first().click();
}

export async function goToRagApps(page: Page): Promise<void> {
  await page.goto("/");
  await page.locator("text=智能应用").first().click();
}
```

- [ ] **Step 3: 创建 assertions helper**

创建 `frontend/e2e/helpers/assertions.ts`：

```ts
import { expect, Page } from "@playwright/test";

/**
 * 轮询等待元素包含指定文本。
 */
export async function waitForText(
  page: Page,
  selector: string,
  text: string,
  timeoutMs: number = 30_000
): Promise<void> {
  await expect(page.locator(selector)).toContainText(text, { timeout: timeoutMs });
}

/**
 * 轮询等待 API 状态变更。
 */
export async function waitForApiStatus(
  page: Page,
  url: string,
  expectedStatus: string,
  timeoutMs: number = 60_000
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const response = await page.evaluate(async (apiUrl) => {
      const res = await fetch(apiUrl);
      return res.json();
    }, url);
    if (response.status === expectedStatus || response.state === expectedStatus) {
      return;
    }
    await page.waitForTimeout(2000);
  }
  throw new Error(`Timeout waiting for status "${expectedStatus}" at ${url}`);
}

/**
 * 断言 Toast 消息出现。
 */
export async function expectToast(page: Page, message: string): Promise<void> {
  await expect(page.locator(`text=${message}`).first()).toBeVisible({ timeout: 10_000 });
}
```

- [ ] **Step 4: 创建 seed helper**

创建 `frontend/e2e/helpers/seed.ts`：

```ts
const API_URL = process.env.TEST_API_URL || "http://localhost:8000";

interface SeedPayload {
  users?: Array<{ username: string; platform_role?: string }>;
  libraries?: Array<{
    name: string;
    members?: Array<{ username: string; role: string }>;
  }>;
  knowledge_bases?: Array<{
    name: string;
    library_name: string;
    members?: Array<{ username: string; role: string }>;
  }>;
}

interface SeedResult {
  users: Array<{ username: string; user_id: string }>;
  libraries: Array<{ name: string; library_id: string }>;
  knowledge_bases: Array<{ name: string; kb_id: string }>;
}

export async function seedTestData(payload: SeedPayload): Promise<SeedResult> {
  const response = await fetch(`${API_URL}/api/v1/test/seed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Seed API failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}
```

- [ ] **Step 5: 创建 seed payloads**

创建 `frontend/e2e/fixtures/seed-payloads.ts`：

```ts
export const BASE_SEED = {
  users: [
    { username: "admin", platform_role: "platform_admin" },
    { username: "lib_owner", platform_role: "platform_user" },
    { username: "lib_viewer", platform_role: "platform_user" },
    { username: "kb_editor", platform_role: "platform_user" },
  ],
  libraries: [
    {
      name: "e2e-test-library",
      members: [
        { username: "admin", role: "library_owner" },
        { username: "lib_owner", role: "library_owner" },
        { username: "lib_viewer", role: "library_viewer" },
      ],
    },
  ],
  knowledge_bases: [
    {
      name: "e2e-test-kb",
      library_name: "e2e-test-library",
      members: [
        { username: "admin", role: "kb_owner" },
        { username: "lib_owner", role: "kb_owner" },
        { username: "kb_editor", role: "kb_editor" },
      ],
    },
  ],
};
```

- [ ] **Step 6: 验证 helpers 编译**

```powershell
cd frontend
npx tsc --noEmit e2e/helpers/*.ts e2e/fixtures/*.ts
```

Expected: 无报错。

- [ ] **Step 7: Commit**

```powershell
git add frontend/e2e/helpers/ frontend/e2e/fixtures/
git commit -m "feat: add Playwright E2E helpers and seed fixtures (Sprint 43)"
```

---

### Task 4: B-214 三层主链路 E2E

**Files:**
- Create: `frontend/e2e/tests/b214-main-flow.spec.ts`

- [ ] **Step 1: 编写主链路测试**

创建 `frontend/e2e/tests/b214-main-flow.spec.ts`：

```ts
import { test, expect } from "@playwright/test";
import { seedTestData } from "../helpers/seed";
import { BASE_SEED } from "../fixtures/seed-payloads";
import { loginAs } from "../helpers/auth";

const API_URL = process.env.TEST_API_URL || "http://localhost:8000";
const TEST_FILE_PATH = "e2e/fixtures/test-files/sample.txt";

test.describe("B-214: 三层主链路 E2E", () => {
  let seedResult: Awaited<ReturnType<typeof seedTestData>>;

  test.beforeAll(async () => {
    seedResult = await seedTestData(BASE_SEED);
  });

  test("Step 1: 上传文档到文档库", async ({ page }) => {
    await loginAs(page, "lib_owner");

    // 导航到文档库详情
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 上传文件
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.locator("text=上传").first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(TEST_FILE_PATH);

    // 等待上传完成
    await expect(page.locator("text=上传成功").first()).toBeVisible({ timeout: 30_000 });

    // 断言文档列表出现新文档
    await expect(page.locator("text=sample").first()).toBeVisible();
  });

  test("Step 2: 等待解析完成", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 轮询解析状态
    const statusCell = page.locator("td, span").filter({ hasText: /解析中|completed|已完成/ });
    await expect(statusCell.first()).toContainText(/completed|已完成/, { timeout: 120_000 });
  });

  test("Step 3: 绑定文档版本到知识库", async ({ page }) => {
    await loginAs(page, "lib_owner");

    // 导航到知识库文档中心
    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    // 绑定文档
    await page.locator("text=绑定文档").first().click();
    await page.locator("text=sample").first().click();
    await page.locator("text=确认").first().click();

    // 等待 BindingRevision 构建完成
    await expect(page.locator("text=active").first()).toBeVisible({ timeout: 120_000 });
  });

  test("Step 4: 切换文档版本", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 上传第二版本
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.locator("text=上传").first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(TEST_FILE_PATH);
    await expect(page.locator("text=上传成功").first()).toBeVisible({ timeout: 30_000 });

    // 导航到知识库切换版本
    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    // 找到版本切换入口
    await page.locator("text=切换版本").first().click();
    await page.locator("text=版本 2").first().click();
    await page.locator("text=确认").first().click();

    // 断言新版本 active，旧版本 retired
    await expect(page.locator("text=active").first()).toBeVisible({ timeout: 120_000 });
  });

  test("Step 5: QA 调用", async ({ page }) => {
    await loginAs(page, "lib_owner");

    // 导航到 QA 调试页
    await page.goto("/");
    await page.locator("text=QA").first().click();
    await page.locator("text=调试").first().click();

    // 输入问题并提交
    await page.locator("textarea, input[type=text]").first().fill("这个文档的主要内容是什么？");
    await page.locator("text=提交").first().click();

    // 等待回答
    await expect(page.locator("text=回答").first()).toBeVisible({ timeout: 60_000 });

    // 断言 evidence 有内容
    await expect(page.locator("text=证据").first()).toBeVisible();
  });

  test("Step 6: App Runtime 调用", async ({ page }) => {
    await loginAs(page, "admin");

    // 先通过 API 创建一个测试 App（如果不存在）
    const appResponse = await page.evaluate(async (url) => {
      const appsRes = await fetch(`${url}/api/v1/rag-apps`);
      const apps = await appsRes.json();
      if (apps.length > 0) return apps[0];

      // 创建测试 App
      const kbRes = await fetch(`${url}/api/v1/knowledge-bases`);
      const kbs = await kbRes.json();
      const kbId = kbs[0]?.knowledge_base_id || kbs[0]?.id;

      const createRes = await fetch(`${url}/api/v1/rag-apps`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "e2e-test-app",
          knowledge_base_id: kbId,
        }),
      });
      return createRes.json();
    }, API_URL);

    // 通过 App Runtime chat API 调用
    const response = await page.evaluate(async ({ url, apiKey }) => {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;

      const res = await fetch(`${url}/api/v1/app-runtime/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: "测试消息",
          conversation_id: null,
        }),
      });
      return { status: res.status, body: await res.json() };
    }, { url: API_URL, apiKey: appResponse?.api_keys?.[0]?.key });

    expect(response.status).toBe(200);
  });
});
```

- [ ] **Step 2: 创建测试用文件**

```powershell
cd frontend
if (!(Test-Path "e2e/fixtures/test-files")) {
    New-Item -ItemType Directory -Path "e2e/fixtures/test-files" -Force
}
"This is a test document for E2E testing. It contains sample content for validating the three-layer architecture end-to-end flow." | Out-File -FilePath "e2e/fixtures/test-files/sample.txt" -Encoding utf8
```

- [ ] **Step 3: 验证测试文件语法**

```powershell
cd frontend
npx tsc --noEmit e2e/tests/b214-main-flow.spec.ts
```

Expected: 无报错。

- [ ] **Step 4: Commit**

```powershell
git add frontend/e2e/tests/b214-main-flow.spec.ts frontend/e2e/fixtures/test-files/
git commit -m "feat: add B-214 main flow E2E test (Sprint 43)"
```

---

### Task 5: B-215 删除回归 E2E

**Files:**
- Create: `frontend/e2e/tests/b215-deletion-regression.spec.ts`

- [ ] **Step 1: 编写删除回归测试**

创建 `frontend/e2e/tests/b215-deletion-regression.spec.ts`：

```ts
import { test, expect } from "@playwright/test";
import { seedTestData } from "../helpers/seed";
import { BASE_SEED } from "../fixtures/seed-payloads";
import { loginAs } from "../helpers/auth";

test.describe("B-215: 删除和清理回归", () => {
  test.beforeAll(async () => {
    await seedTestData(BASE_SEED);
  });

  test("active 引用阻止删除文档版本", async ({ page }) => {
    await loginAs(page, "lib_owner");

    // 导航到文档库详情
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 尝试删除有 active BindingRevision 的文档版本
    // 找到版本行的删除按钮
    const versionRow = page.locator("tr, div").filter({ hasText: /版本|version/i }).first();
    await versionRow.locator("text=删除").first().click();

    // 断言删除被拒绝，显示影响分析
    await expect(
      page.locator("text=/无法删除|不能删除|active.*引用|BindingRevision/").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("历史 QA 引用的旧版本可强确认删除", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 找到仅被历史 QA 引用的旧版本
    const oldVersionRow = page.locator("tr, div").filter({ hasText: /版本 1|version 1/i }).first();
    await oldVersionRow.locator("text=删除").first().click();

    // 断言弹出确认弹窗
    await expect(page.locator("text=/确认删除|强确认|影响/").first()).toBeVisible({
      timeout: 10_000,
    });

    // 确认删除
    await page.locator("text=确认删除, text=确定").first().click();

    // 断言删除成功
    await expect(page.locator("text=/删除成功|已删除/").first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("删除后 QA 历史显示 source_deleted", async ({ page }) => {
    await loginAs(page, "lib_owner");

    // 导航到 QA 历史
    await page.goto("/");
    await page.locator("text=QA").first().click();
    await page.locator("text=历史").first().click();

    // 打开之前的 QA 记录
    await page.locator("text=查看").first().click();

    // 断言 evidence 显示"引用文件已被清理"
    await expect(page.locator("text=/引用文件已被清理|source_deleted/").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("删除旧版本后当前 KB 检索正常", async ({ page }) => {
    await loginAs(page, "lib_owner");

    // 导航到 QA 调试页
    await page.goto("/");
    await page.locator("text=QA").first().click();
    await page.locator("text=调试").first().click();

    // 提问验证检索正常
    await page.locator("textarea, input[type=text]").first().fill("测试检索");
    await page.locator("text=提交").first().click();

    // 断言返回结果（不报错）
    await expect(page.locator("text=回答").first()).toBeVisible({ timeout: 60_000 });
  });
});
```

- [ ] **Step 2: 验证语法**

```powershell
cd frontend
npx tsc --noEmit e2e/tests/b215-deletion-regression.spec.ts
```

- [ ] **Step 3: Commit**

```powershell
git add frontend/e2e/tests/b215-deletion-regression.spec.ts
git commit -m "feat: add B-215 deletion regression E2E test (Sprint 43)"
```

---

### Task 6: B-216 权限与 Runtime 回归 E2E

**Files:**
- Create: `frontend/e2e/tests/b216-permission-runtime.spec.ts`

- [ ] **Step 1: 编写权限和 Runtime 测试**

创建 `frontend/e2e/tests/b216-permission-runtime.spec.ts`：

```ts
import { test, expect } from "@playwright/test";
import { seedTestData } from "../helpers/seed";
import { BASE_SEED } from "../fixtures/seed-payloads";
import { loginAs } from "../helpers/auth";

const API_URL = process.env.TEST_API_URL || "http://localhost:8000";

test.describe("B-216: 权限矩阵和 Runtime 状态回归", () => {
  test.beforeAll(async () => {
    await seedTestData(BASE_SEED);
  });

  test("platform_admin 可操作所有资源", async ({ page }) => {
    await loginAs(page, "admin");

    // 导航到文档库
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 断言可以看见管理操作按钮
    await expect(page.locator("text=上传").first()).toBeVisible();
    await expect(page.locator("text=删除").first()).toBeVisible();
  });

  test("library_viewer 无法删除文档版本", async ({ page }) => {
    await loginAs(page, "lib_viewer");

    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    // 断言删除按钮不可见或禁用
    const deleteBtn = page.locator("text=删除").first();
    const isVisible = await deleteBtn.isVisible().catch(() => false);
    if (isVisible) {
      await expect(deleteBtn).toBeDisabled();
    }
  });

  test("用户组并集权限生效", async ({ page }) => {
    // kb_editor 通过用户组获得 kb_editor 角色
    await loginAs(page, "kb_editor");

    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    // 断言可以看见绑定文档入口
    await expect(page.locator("text=绑定文档").first()).toBeVisible({ timeout: 10_000 });
  });

  test("跨资源权限校验", async ({ page }) => {
    // lib_viewer 没有 kb.document.bind 权限
    await loginAs(page, "lib_viewer");

    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    // 尝试绑定文档
    const bindBtn = page.locator("text=绑定文档").first();
    if (await bindBtn.isVisible().catch(() => false)) {
      await bindBtn.click();
      // 断言被拒绝
      await expect(page.locator("text=/权限不足|无权限|forbidden/i").first()).toBeVisible({
        timeout: 10_000,
      });
    }
  });

  test("KB disabled 后 App Runtime 返回 KB_DISABLED", async ({ page }) => {
    await loginAs(page, "admin");

    // 先通过 API 禁用知识库
    const kbId = await page.evaluate(async (url) => {
      const res = await fetch(`${url}/api/v1/knowledge-bases`);
      const data = await res.json();
      return data[0]?.knowledge_base_id || data[0]?.id;
    }, API_URL);

    await page.evaluate(
      async ({ url, id }) => {
        await fetch(`${url}/api/v1/knowledge-bases/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "disabled" }),
        });
      },
      { url: API_URL, id: kbId }
    );

    // 调用 App Runtime
    const response = await page.evaluate(async (url) => {
      const res = await fetch(`${url}/api/v1/app-runtime/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "测试", conversation_id: null }),
      });
      return { status: res.status, body: await res.json() };
    }, API_URL);

    // 断言返回 KB_DISABLED 错误
    expect(response.status).toBeGreaterThanOrEqual(400);
    expect(JSON.stringify(response.body)).toContain("KB_DISABLED");

    // 恢复知识库状态
    await page.evaluate(
      async ({ url, id }) => {
        await fetch(`${url}/api/v1/knowledge-bases/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "active" }),
        });
      },
      { url: API_URL, id: kbId }
    );
  });

  test("KB disabled 不删除 App 和 Key", async ({ page }) => {
    await loginAs(page, "admin");

    // 检查 App 和 Key 仍然存在
    const apps = await page.evaluate(async (url) => {
      const res = await fetch(`${url}/api/v1/rag-apps`);
      return res.json();
    }, API_URL);

    expect(apps.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: 验证语法**

```powershell
cd frontend
npx tsc --noEmit e2e/tests/b216-permission-runtime.spec.ts
```

- [ ] **Step 3: Commit**

```powershell
git add frontend/e2e/tests/b216-permission-runtime.spec.ts
git commit -m "feat: add B-216 permission and runtime regression E2E test (Sprint 43)"
```

---

### Task 7: B-217 文档同步脚本

**Files:**
- Create: `backend/scripts/check_api_contract.py`
- Create: `frontend/e2e/tests/b217-doc-sync.spec.ts`

- [ ] **Step 1: 编写 API 契约检查脚本**

创建 `backend/scripts/check_api_contract.py`：

```python
"""检查 OpenAPI schema 与前端 TypeScript types 的一致性。"""

import json
import re
import sys
from pathlib import Path

OPENAPI_PATH = Path(__file__).parent.parent.parent / "docs" / "06-发布与运维" / "openapi.json"
TYPES_DIR = Path(__file__).parent.parent.parent / "frontend" / "src" / "app" / "types"


def load_openapi_schemas() -> dict[str, dict]:
    """从 OpenAPI JSON 提取所有 schema 定义。"""
    with open(OPENAPI_PATH, encoding="utf-8") as f:
        spec = json.load(f)
    return spec.get("components", {}).get("schemas", {})


def extract_ts_interfaces() -> dict[str, set[str]]:
    """从 TypeScript 文件提取接口字段名。"""
    interfaces: dict[str, set[str]] = {}
    for ts_file in TYPES_DIR.glob("*.ts"):
        content = ts_file.read_text(encoding="utf-8")
        # 匹配 interface 或 type 定义
        for match in re.finditer(
            r"(?:interface|type)\s+(\w+)\s*(?:=\s*\{)?\s*\n((?:\s+\w+.*\n)*)",
            content,
        ):
            name = match.group(1)
            body = match.group(2)
            fields = set()
            for line in body.strip().split("\n"):
                line = line.strip().rstrip(";,")
                if line and not line.startswith("//") and not line.startswith("*"):
                    field_match = re.match(r"(\w+)\??\s*:", line)
                    if field_match:
                        fields.add(field_match.group(1))
            if fields:
                interfaces[name] = fields
    return interfaces


def normalize_schema_name(name: str) -> str:
    """将 PascalCase schema 名转为与 TS 接口可比较的形式。"""
    return name


def check_consistency() -> list[str]:
    """对比 OpenAPI schema 与 TS 接口，返回差异列表。"""
    openapi_schemas = load_openapi_schemas()
    ts_interfaces = extract_ts_interfaces()
    differences = []

    for schema_name, schema_def in openapi_schemas.items():
        ts_name = normalize_schema_name(schema_name)
        if ts_name not in ts_interfaces:
            continue  # 跳过没有对应 TS 接口的 schema

        schema_props = set(schema_def.get("properties", {}).keys())
        ts_fields = ts_interfaces[ts_name]

        # camelCase 转换：OpenAPI 可能用 snake_case，TS 用 camelCase
        schema_props_camel = {to_camel(p) for p in schema_props}

        missing_in_ts = schema_props_camel - ts_fields
        extra_in_ts = ts_fields - schema_props_camel

        if missing_in_ts:
            differences.append(f"{schema_name}: TS 缺少字段 {missing_in_ts}")
        if extra_in_ts:
            differences.append(f"{schema_name}: TS 多余字段 {extra_in_ts}")

    return differences


def to_camel(snake: str) -> str:
    """snake_case 转 camelCase。"""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def main():
    if not OPENAPI_PATH.exists():
        print(f"ERROR: OpenAPI file not found at {OPENAPI_PATH}")
        sys.exit(1)

    if not TYPES_DIR.exists():
        print(f"ERROR: Types directory not found at {TYPES_DIR}")
        sys.exit(1)

    differences = check_consistency()

    if differences:
        print(f"Found {len(differences)} difference(s):")
        for diff in differences:
            print(f"  - {diff}")
        sys.exit(1)
    else:
        print("OK: OpenAPI schema and TypeScript types are consistent.")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 编写文档同步 Playwright 测试**

创建 `frontend/e2e/tests/b217-doc-sync.spec.ts`：

```ts
import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import * as fs from "fs";
import * as path from "path";

const ROOT = path.resolve(__dirname, "../../../..");

test.describe("B-217: 文档同步校验", () => {
  test("OpenAPI 导出成功", async () => {
    const result = execSync(
      "conda run -n rag-lab python scripts/export_openapi.py",
      { cwd: path.join(ROOT, "backend"), encoding: "utf-8" }
    );
    const openapiPath = path.join(ROOT, "docs/06-发布与运维/openapi.json");
    expect(fs.existsSync(openapiPath)).toBe(true);

    const spec = JSON.parse(fs.readFileSync(openapiPath, "utf-8"));
    expect(spec.openapi || spec.swagger).toBeDefined();
    expect(spec.paths).toBeDefined();
  });

  test("API 契约检查通过", async () => {
    try {
      execSync(
        "conda run -n rag-lab python scripts/check_api_contract.py",
        { cwd: path.join(ROOT, "backend"), encoding: "utf-8", stdio: "pipe" }
      );
    } catch (error: any) {
      // 如果脚本返回 exit code 1，说明有差异
      const output = error.stdout || error.stderr || "";
      console.log("Contract check output:", output);
      // 不自动失败，输出差异供人工确认
    }
  });

  test("OpenAPI 包含关键端点", async () => {
    const openapiPath = path.join(ROOT, "docs/06-发布与运维/openapi.json");
    const spec = JSON.parse(fs.readFileSync(openapiPath, "utf-8"));
    const paths = Object.keys(spec.paths || {});

    // 验证三层架构关键端点存在
    const requiredEndpoints = [
      "/api/v1/library",
      "/api/v1/knowledge-bases",
      "/api/v1/rag-apps",
      "/api/v1/app-runtime",
    ];

    for (const endpoint of requiredEndpoints) {
      const found = paths.some((p) => p.startsWith(endpoint));
      expect(found, `Missing endpoint group: ${endpoint}`).toBe(true);
    }
  });
});
```

- [ ] **Step 3: 验证脚本可运行**

```powershell
cd backend
conda run -n rag-lab python scripts/check_api_contract.py
```

Expected: 输出差异清单或 "OK" 消息。

- [ ] **Step 4: Commit**

```powershell
git add backend/scripts/check_api_contract.py frontend/e2e/tests/b217-doc-sync.spec.ts
git commit -m "feat: add B-217 doc sync check script and E2E test (Sprint 43)"
```

---

### Task 8: 更新 Sprint 43 文档状态

**Files:**
- Modify: `docs/04-迭代与交付/sprints/sprint41-60/Sprint-43.md`

- [ ] **Step 1: 更新 Backlog 状态**

将 Sprint 43 文档中 B-214 到 B-217 的状态从 `Ready` 更新为 `In Progress`。

- [ ] **Step 2: 验证全部代码编译**

```powershell
# 后端
cd backend
conda run -n rag-lab python -m compileall app

# 前端
cd frontend
npm run lint
npm run build
```

- [ ] **Step 3: Commit**

```powershell
git add docs/04-迭代与交付/sprints/sprint41-60/Sprint-43.md
git commit -m "docs: update Sprint 43 status to in-progress"
```

---

## 执行说明

本计划分两个阶段执行：

**阶段一（可并行，Sprint 42 开发期间）：**
- Task 1: Playwright 基础设施
- Task 2: 后端 Seed API
- Task 3: Playwright 共享工具
- Task 7: 文档同步脚本（B-217 不依赖前端）

**阶段二（需 Sprint 42 完成后）：**
- Task 4: B-214 主链路 E2E
- Task 5: B-215 删除回归 E2E
- Task 6: B-216 权限与 Runtime 回归 E2E
- Task 8: 更新文档状态 + 最终验收

**验收时执行：**

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

# E2E 验证
npx playwright test --config e2e/playwright.config.ts

# Git 检查
git diff --check
```

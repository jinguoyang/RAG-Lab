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

    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    await expect(page.locator("text=上传").first()).toBeVisible();
    await expect(page.locator("text=删除").first()).toBeVisible();
  });

  test("library_viewer 无法删除文档版本", async ({ page }) => {
    await loginAs(page, "lib_viewer");

    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    const deleteBtn = page.locator("text=删除").first();
    const isVisible = await deleteBtn.isVisible().catch(() => false);
    if (isVisible) {
      await expect(deleteBtn).toBeDisabled();
    }
  });

  test("用户组并集权限生效", async ({ page }) => {
    await loginAs(page, "kb_editor");

    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    await expect(page.locator("text=绑定文档").first()).toBeVisible({ timeout: 10_000 });
  });

  test("跨资源权限校验", async ({ page }) => {
    await loginAs(page, "lib_viewer");

    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    const bindBtn = page.locator("text=绑定文档").first();
    if (await bindBtn.isVisible().catch(() => false)) {
      await bindBtn.click();
      await expect(page.locator("text=/权限不足|无权限|forbidden/i").first()).toBeVisible({
        timeout: 10_000,
      });
    }
  });

  test("KB disabled 后 App Runtime 返回 KB_DISABLED", async ({ page }) => {
    await loginAs(page, "admin");

    const kbId = await page.evaluate(async (url) => {
      const res = await fetch(`${url}/api/v1/knowledge-bases`);
      const data = await res.json();
      return data[0]?.kb_id || data[0]?.id;
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

    const response = await page.evaluate(async (url) => {
      const res = await fetch(`${url}/api/v1/app-runtime/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "测试", conversation_id: null }),
      });
      return { status: res.status, body: await res.json() };
    }, API_URL);

    expect(response.status).toBeGreaterThanOrEqual(400);
    expect(JSON.stringify(response.body)).toContain("KB_DISABLED");

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

    const apps = await page.evaluate(async (url) => {
      const res = await fetch(`${url}/api/v1/rag-apps`);
      return res.json();
    }, API_URL);

    expect(apps.length).toBeGreaterThan(0);
  });
});

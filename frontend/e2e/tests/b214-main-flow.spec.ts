import { test, expect } from "@playwright/test";
import { seedTestData } from "../helpers/seed";
import { BASE_SEED } from "../fixtures/seed-payloads";
import { loginAs } from "../helpers/auth";

const API_URL = process.env.TEST_API_URL || "http://localhost:8000";
const TEST_FILE_PATH = "e2e/fixtures/test-files/sample.txt";

test.describe("B-214: 三层主链路 E2E", () => {
  test.beforeAll(async () => {
    await seedTestData(BASE_SEED);
  });

  test("Step 1: 上传文档到文档库", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.locator("text=上传").first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(TEST_FILE_PATH);

    await expect(page.locator("text=上传成功").first()).toBeVisible({ timeout: 30_000 });
    await expect(page.locator("text=sample").first()).toBeVisible();
  });

  test("Step 2: 等待解析完成", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    const statusCell = page.locator("td, span").filter({ hasText: /解析中|completed|已完成/ });
    await expect(statusCell.first()).toContainText(/completed|已完成/, { timeout: 120_000 });
  });

  test("Step 3: 绑定文档版本到知识库", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    await page.locator("text=绑定文档").first().click();
    await page.locator("text=sample").first().click();
    await page.locator("text=确认").first().click();

    await expect(page.locator("text=active").first()).toBeVisible({ timeout: 120_000 });
  });

  test("Step 4: 切换文档版本", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.locator("text=上传").first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(TEST_FILE_PATH);
    await expect(page.locator("text=上传成功").first()).toBeVisible({ timeout: 30_000 });

    await page.goto("/");
    await page.locator("text=知识库").first().click();
    await page.locator("text=文档中心").first().click();

    await page.locator("text=切换版本").first().click();
    await page.locator("text=版本 2").first().click();
    await page.locator("text=确认").first().click();

    await expect(page.locator("text=active").first()).toBeVisible({ timeout: 120_000 });
  });

  test("Step 5: QA 调用", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=QA").first().click();
    await page.locator("text=调试").first().click();

    await page.locator("textarea, input[type=text]").first().fill("这个文档的主要内容是什么？");
    await page.locator("text=提交").first().click();

    await expect(page.locator("text=回答").first()).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("text=证据").first()).toBeVisible();
  });

  test("Step 6: App Runtime 调用", async ({ page }) => {
    await loginAs(page, "admin");

    const appResponse = await page.evaluate(async (url) => {
      const appsRes = await fetch(`${url}/api/v1/rag-apps`);
      const apps = await appsRes.json();
      if (apps.length > 0) return apps[0];

      const kbRes = await fetch(`${url}/api/v1/knowledge-bases`);
      const kbs = await kbRes.json();
      const kbId = kbs[0]?.kb_id || kbs[0]?.id;

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

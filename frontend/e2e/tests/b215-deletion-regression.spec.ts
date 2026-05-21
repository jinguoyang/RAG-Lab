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

    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    const versionRow = page.locator("tr, div").filter({ hasText: /版本|version/i }).first();
    await versionRow.locator("text=删除").first().click();

    await expect(
      page.locator("text=/无法删除|不能删除|active.*引用|BindingRevision/").first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("历史 QA 引用的旧版本可强确认删除", async ({ page }) => {
    await loginAs(page, "lib_owner");
    await page.goto("/");
    await page.locator("text=文档库").first().click();
    await page.locator("text=e2e-test-library").first().click();

    const oldVersionRow = page.locator("tr, div").filter({ hasText: /版本 1|version 1/i }).first();
    await oldVersionRow.locator("text=删除").first().click();

    await expect(page.locator("text=/确认删除|强确认|影响/").first()).toBeVisible({
      timeout: 10_000,
    });

    await page.locator("text=确认删除, text=确定").first().click();

    await expect(page.locator("text=/删除成功|已删除/").first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("删除后 QA 历史显示 source_deleted", async ({ page }) => {
    await loginAs(page, "lib_owner");

    await page.goto("/");
    await page.locator("text=QA").first().click();
    await page.locator("text=历史").first().click();

    await page.locator("text=查看").first().click();

    await expect(page.locator("text=/引用文件已被清理|source_deleted/").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("删除旧版本后当前 KB 检索正常", async ({ page }) => {
    await loginAs(page, "lib_owner");

    await page.goto("/");
    await page.locator("text=QA").first().click();
    await page.locator("text=调试").first().click();

    await page.locator("textarea, input[type=text]").first().fill("测试检索");
    await page.locator("text=提交").first().click();

    await expect(page.locator("text=回答").first()).toBeVisible({ timeout: 60_000 });
  });
});

import { Page } from "@playwright/test";

/**
 * 通过 dev auth 登录，返回页面已登录状态。
 * 假设 dev_auth_enabled=true，直接访问即以 dev_default_username 登录。
 */
export async function loginAs(page: Page, username: string): Promise<void> {
  await page.goto("/");
  const loginInput = page.locator(
    'input[name="username"], input[placeholder*="用户"]'
  );
  if (await loginInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await loginInput.fill(username);
    const submitBtn = page.locator('button[type="submit"]');
    await submitBtn.click();
    await page.waitForURL("**/", { timeout: 10_000 });
  }
}

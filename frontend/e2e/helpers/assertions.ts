import { expect, Page } from "@playwright/test";

export async function waitForText(
  page: Page,
  selector: string,
  text: string,
  timeoutMs: number = 30_000
): Promise<void> {
  await expect(page.locator(selector)).toContainText(text, {
    timeout: timeoutMs,
  });
}

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
  throw new Error(
    `Timeout waiting for status "${expectedStatus}" at ${url}`
  );
}

export async function expectToast(page: Page, message: string): Promise<void> {
  await expect(page.locator(`text=${message}`).first()).toBeVisible({
    timeout: 10_000,
  });
}

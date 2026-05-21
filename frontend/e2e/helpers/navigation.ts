import { Page, expect } from "@playwright/test";

export async function goToLibraryDetail(
  page: Page,
  libraryName: string
): Promise<void> {
  await page.goto("/");
  await page.locator("text=文档库").first().click();
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

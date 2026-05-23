import { expect, test } from "@playwright/test";

const now = "2026-05-24T02:00:00Z";

const kbPage = {
  items: [
    {
      id: "kb-1",
      kbId: "kb-1",
      name: "制度知识库",
      description: null,
      ownerId: "admin",
      status: "active",
      activeConfigRevisionId: "rev-1",
      documentCount: 1,
      chunkCount: 2,
      createdAt: now,
      updatedAt: now,
    },
  ],
  pageNo: 1,
  pageSize: 50,
  total: 1,
};

const appPage = {
  items: [
    {
      appId: "app-training",
      kbId: "kb-1",
      defaultConfigRevisionId: "rev-1",
      name: "员工培训助手",
      description: "用于安全制度培训",
      status: "active",
      outputPolicy: {},
      metadata: {},
      createdAt: now,
      updatedAt: now,
      knowledgeBaseName: "制度知识库",
      knowledgeBaseStatus: "active",
      scenarioType: "employee_training",
      scenarioTemplateId: "builtin_employee_training_v1",
      scenarioConfig: { difficulty: "normal", questionCount: 2, passingScore: 80 },
      publishChannels: { api: true, embed: true },
      embedSettings: { enabled: true, allowedOrigins: [] },
    },
    {
      appId: "app-qa",
      kbId: "kb-1",
      defaultConfigRevisionId: "rev-1",
      name: "知识库问答助手",
      description: "用于制度问答",
      status: "active",
      outputPolicy: {},
      metadata: {},
      createdAt: now,
      updatedAt: now,
      knowledgeBaseName: "制度知识库",
      knowledgeBaseStatus: "active",
      scenarioType: "knowledge_qa",
      scenarioTemplateId: "builtin_knowledge_qa_v1",
      scenarioConfig: { citationCount: 3, noEvidencePolicy: "refuse" },
      publishChannels: { api: true, embed: false },
      embedSettings: { enabled: false, allowedOrigins: [] },
    },
  ],
  pageNo: 1,
  pageSize: 10,
  total: 2,
};

async function mockScenarioRuntimeApis(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/knowledge-bases?**", (route) => route.fulfill({ json: kbPage }));
  await page.route("**/api/v1/agent-scenario-templates", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/dictionaries/feedback_status/items?**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/rag-apps?**", (route) => route.fulfill({ json: appPage }));
  await page.route("**/api/v1/rag-apps/*/api-keys", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/rag-apps/*/invocations?**", (route) => route.fulfill({ json: { items: [], pageNo: 1, pageSize: 20, total: 0 } }));
  await page.route("**/api/v1/knowledge-bases/*/config-revisions?**", (route) => route.fulfill({ json: { items: [], pageNo: 1, pageSize: 50, total: 0 } }));
  await page.route("**/api/v1/rag-apps/*/stats", (route) => route.fulfill({
    json: {
      appId: "app-training",
      totalInvocations: 2,
      runningInvocations: 0,
      successInvocations: 2,
      failedInvocations: 0,
      quotaExceededInvocations: 0,
      concurrencyExceededInvocations: 0,
      noEvidenceInvocations: 0,
      averageLatencyMs: 18,
      failureRate: 0,
      noEvidenceRate: 0,
    },
  }));
  await page.route("**/api/v1/rag-apps/app-training/training-report", (route) => route.fulfill({
    json: {
      appId: "app-training",
      totalSubmissions: 2,
      passedSubmissions: 1,
      failedSubmissions: 1,
      averageScore: 75,
      passRate: 0.5,
      latestSubmittedAt: now,
      recentResults: [],
    },
  }));
}

test.describe("B-256/B-257: 场景助手验收硬化", () => {
  test("P13 展示两个场景并呈现员工培训报告摘要", async ({ page }) => {
    await mockScenarioRuntimeApis(page);

    await page.goto("/rag-apps");

    await expect(page.getByText("员工培训助手").first()).toBeVisible();
    await expect(page.getByText("知识库问答助手").first()).toBeVisible();

    await page.getByText("员工培训助手").first().click();

    await expect(page.getByText("培训报告")).toBeVisible();
    await expect(page.getByText("2 次训练 · 通过率 50% · 平均分 75")).toBeVisible();
    await expect(page.getByText("通过：1", { exact: true })).toBeVisible();
    await expect(page.getByText("未通过：1", { exact: true })).toBeVisible();
  });
});

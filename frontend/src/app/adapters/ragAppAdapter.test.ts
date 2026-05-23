import { describe, expect, it } from "vitest";

import { toAppMessageViewModel, toRagAppTrainingReportViewModel, toRagAppViewModel } from "./ragAppAdapter";
import type { AppMessageDTO, RagAppDTO } from "../types/ragApp";

function buildApp(overrides: Partial<RagAppDTO> = {}): RagAppDTO {
  return {
    appId: "app-001",
    kbId: "kb-001",
    defaultConfigRevisionId: null,
    name: "培训助手",
    description: "用于员工培训",
    status: "active",
    outputPolicy: {},
    metadata: {},
    createdAt: "2026-05-24T10:00:00+08:00",
    updatedAt: "2026-05-24T10:30:00+08:00",
    scenarioType: "employee_training",
    scenarioTemplateId: "builtin_employee_training_v1",
    scenarioConfig: { questionCount: 5 },
    publishChannels: { api: true, embed: false },
    embedSettings: { enabled: false, allowedOrigins: [] },
    ...overrides,
  };
}

describe("toRagAppViewModel", () => {
  it("formats scenario and publish labels for app rows", () => {
    const viewModel = toRagAppViewModel(buildApp());

    expect(viewModel.scenarioLabel).toBe("员工培训助手");
    expect(viewModel.publishChannelLabel).toBe("API");
    expect(viewModel.embedStatusLabel).toBe("未启用");
  });

  it("formats enabled embed channel", () => {
    const viewModel = toRagAppViewModel(
      buildApp({
        scenarioType: "knowledge_qa",
        publishChannels: { api: true, embed: true },
        embedSettings: { enabled: true, allowedOrigins: ["https://example.com"] },
      }),
    );

    expect(viewModel.scenarioLabel).toBe("知识库问答助手");
    expect(viewModel.publishChannelLabel).toBe("API / 嵌入页");
    expect(viewModel.embedStatusLabel).toBe("已启用");
  });
});

describe("toAppMessageViewModel", () => {
  it("formats training result metadata for conversation detail", () => {
    const message: AppMessageDTO = {
      messageId: "msg-001",
      conversationId: "conv-001",
      role: "assistant",
      content: "训练得分 50，未通过。",
      qaRunId: "run-001",
      status: "success",
      metadata: {
        trainingResult: {
          score: 50,
          passed: false,
          passingScore: 80,
        },
      },
      createdAt: "2026-05-24T10:30:00+08:00",
    };

    const viewModel = toAppMessageViewModel(message);

    expect(viewModel.trainingResultLabel).toBe("训练得分 50 / 100 · 未通过 · 及格分 80");
  });

  it("formats training report summary", () => {
    const viewModel = toRagAppTrainingReportViewModel({
      appId: "app-1",
      totalSubmissions: 4,
      passedSubmissions: 3,
      failedSubmissions: 1,
      averageScore: 82.5,
      passRate: 0.75,
      latestSubmittedAt: "2026-05-24T02:00:00Z",
      recentResults: [],
    });

    expect(viewModel.summaryLabel).toBe("4 次训练 · 通过率 75% · 平均分 82.5");
    expect(viewModel.latestSubmittedAtLabel).not.toBe("-");
  });
});

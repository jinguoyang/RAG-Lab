import { describe, expect, it } from "vitest";

import { toRagAppViewModel } from "./ragAppAdapter";
import type { RagAppDTO } from "../types/ragApp";

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

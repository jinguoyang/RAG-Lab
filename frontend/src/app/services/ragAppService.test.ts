import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./apiClient", () => ({
  apiGet: vi.fn(),
}));

import { apiGet } from "./apiClient";
import { getRagAppTrainingReport } from "./ragAppService";

describe("ragAppService training report", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("gets training report by app id", async () => {
    vi.mocked(apiGet).mockResolvedValue({ totalSubmissions: 2 });

    await getRagAppTrainingReport("app-1");

    expect(apiGet).toHaveBeenCalledWith("/rag-apps/app-1/training-report");
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./apiClient", () => ({
  apiPostJsonStreamWithHeaders: vi.fn(),
  apiPostJsonWithHeaders: vi.fn(),
}));

import { apiPostJsonWithHeaders } from "./apiClient";
import {
  createStructuredRunWithAppRuntime,
  submitTrainingQuizWithAppRuntime,
} from "./appRuntimeService";

describe("appRuntimeService training APIs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("posts structured runs with bearer credential", async () => {
    vi.mocked(apiPostJsonWithHeaders).mockResolvedValue({ messageId: "msg-1" });

    await createStructuredRunWithAppRuntime("rlet_token", {
      action: "training_quiz_generate",
      topic: "现场安全",
      questionCount: 2,
    });

    expect(apiPostJsonWithHeaders).toHaveBeenCalledWith(
      "/app-runtime/structured-runs",
      { action: "training_quiz_generate", topic: "现场安全", questionCount: 2 },
      { Authorization: "Bearer rlet_token" },
    );
  });

  it("posts training quiz submissions with bearer credential", async () => {
    vi.mocked(apiPostJsonWithHeaders).mockResolvedValue({ score: 100 });

    await submitTrainingQuizWithAppRuntime("rlak_key", {
      conversationId: "conv-1",
      quizMessageId: "msg-1",
      answers: [{ questionId: "q1", answer: "A" }],
    });

    expect(apiPostJsonWithHeaders).toHaveBeenCalledWith(
      "/app-runtime/training/quiz-submissions",
      {
        conversationId: "conv-1",
        quizMessageId: "msg-1",
        answers: [{ questionId: "q1", answer: "A" }],
      },
      { Authorization: "Bearer rlak_key" },
    );
  });
});

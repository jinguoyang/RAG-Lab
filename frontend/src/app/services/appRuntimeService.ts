import {
  apiPostJsonStreamWithHeaders,
  apiPostJsonWithHeaders,
} from "./apiClient";
import type {
  AppRuntimeChatRequest,
  AppRuntimeChatResponse,
  AppRuntimeEmbedTokenRequest,
  AppRuntimeEmbedTokenResponse,
  AppRuntimeFeedbackRequest,
  AppRuntimeFeedbackResponse,
  AppRuntimeRetrieveRequest,
  AppRuntimeRetrieveResponse,
  AppRuntimeSseEvent,
  AppRuntimeStructuredRunRequest,
  AppRuntimeStructuredRunResponse,
  AppRuntimeTrainingQuizSubmissionRequest,
  AppRuntimeTrainingQuizSubmissionResponse,
} from "../types/appRuntime";

function buildRuntimeHeaders(apiKey: string): Record<string, string> {
  const trimmedKey = apiKey.trim();
  if (!trimmedKey) {
    throw new Error("App API Key 不能为空。");
  }
  return { Authorization: `Bearer ${trimmedKey}` };
}

function normalizeChatRequest(
  request: AppRuntimeChatRequest,
  responseMode: "blocking" | "streaming",
): AppRuntimeChatRequest {
  return {
    ...request,
    query: request.query.trim(),
    responseMode,
  };
}

export async function chatWithAppRuntime(
  apiKey: string,
  request: AppRuntimeChatRequest,
): Promise<AppRuntimeChatResponse> {
  return apiPostJsonWithHeaders<AppRuntimeChatResponse>(
    "/app-runtime/chat-messages",
    normalizeChatRequest(request, "blocking"),
    buildRuntimeHeaders(apiKey),
  );
}

export async function streamChatWithAppRuntime(
  apiKey: string,
  request: AppRuntimeChatRequest,
): Promise<Response> {
  return apiPostJsonStreamWithHeaders(
    "/app-runtime/chat-messages",
    normalizeChatRequest(request, "streaming"),
    buildRuntimeHeaders(apiKey),
  );
}

export async function createAppRuntimeEmbedToken(
  apiKey: string,
  request: AppRuntimeEmbedTokenRequest = {},
): Promise<AppRuntimeEmbedTokenResponse> {
  return apiPostJsonWithHeaders<AppRuntimeEmbedTokenResponse>(
    "/app-runtime/embed-tokens",
    request,
    buildRuntimeHeaders(apiKey),
  );
}

export async function retrieveWithAppRuntime(
  credential: string,
  request: AppRuntimeRetrieveRequest,
): Promise<AppRuntimeRetrieveResponse> {
  return apiPostJsonWithHeaders<AppRuntimeRetrieveResponse>(
    "/app-runtime/retrieve",
    request,
    buildRuntimeHeaders(credential),
  );
}

export async function createStructuredRunWithAppRuntime(
  credential: string,
  request: AppRuntimeStructuredRunRequest,
): Promise<AppRuntimeStructuredRunResponse> {
  return apiPostJsonWithHeaders<AppRuntimeStructuredRunResponse>(
    "/app-runtime/structured-runs",
    request,
    buildRuntimeHeaders(credential),
  );
}

export async function submitTrainingQuizWithAppRuntime(
  credential: string,
  request: AppRuntimeTrainingQuizSubmissionRequest,
): Promise<AppRuntimeTrainingQuizSubmissionResponse> {
  return apiPostJsonWithHeaders<AppRuntimeTrainingQuizSubmissionResponse>(
    "/app-runtime/training/quiz-submissions",
    request,
    buildRuntimeHeaders(credential),
  );
}

export async function submitAppRuntimeFeedback(
  apiKey: string,
  messageId: string,
  request: AppRuntimeFeedbackRequest,
): Promise<AppRuntimeFeedbackResponse> {
  return apiPostJsonWithHeaders<AppRuntimeFeedbackResponse>(
    `/app-runtime/messages/${messageId}/feedback`,
    request,
    buildRuntimeHeaders(apiKey),
  );
}

export function parseAppRuntimeSse(payload: string): AppRuntimeSseEvent[] {
  return payload
    .split(/\r?\n\r?\n/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      let event = "message";
      const dataLines: string[] = [];
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event:")) {
          event = line.slice("event:".length).trim();
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.slice("data:".length).trim());
        }
      }
      const dataText = dataLines.join("\n");
      return {
        event,
        data: dataText ? JSON.parse(dataText) : null,
      };
    });
}

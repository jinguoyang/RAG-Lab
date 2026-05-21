import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock apiClient
vi.mock("./apiClient", () => ({
  API_BASE_URL: "/api/v1",
  apiGet: vi.fn(),
  apiPostJson: vi.fn(),
  apiPostForm: vi.fn(),
  apiDelete: vi.fn(),
  apiPatchJson: vi.fn(),
  apiDownload: vi.fn(),
}));

import { apiGet, apiPostJson } from "./apiClient";
import {
  fetchLibraryStats,
  batchAction,
  fetchLibraryDocuments,
  fetchLibraryParseRevisions,
  createLibraryParseRevision,
  fetchDocumentText,
} from "./libraryService";

describe("libraryService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchLibraryStats", () => {
    it("should call GET /library/documents/stats", async () => {
      const mockStats = { totalDocuments: 10, todayUploads: 2, pendingParse: 3 };
      vi.mocked(apiGet).mockResolvedValue(mockStats);

      const result = await fetchLibraryStats();

      expect(apiGet).toHaveBeenCalledWith("/library/documents/stats");
      expect(result).toEqual(mockStats);
    });
  });

  describe("batchAction", () => {
    it("should call POST /library/documents/batch-actions with correct body", async () => {
      const mockResponse = {
        succeeded: ["doc-1"],
        failed: [],
        summary: { total: 1, succeeded: 1, failed: 0 },
      };
      vi.mocked(apiPostJson).mockResolvedValue(mockResponse);

      const result = await batchAction(["doc-1"], "delete");

      expect(apiPostJson).toHaveBeenCalledWith("/library/documents/batch-actions", {
        documentIds: ["doc-1"],
        action: "delete",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("fetchLibraryDocuments", () => {
    it("should pass query parameters correctly", async () => {
      const mockPage = { items: [], pageNo: 1, pageSize: 20, total: 0 };
      vi.mocked(apiGet).mockResolvedValue(mockPage);

      await fetchLibraryDocuments({ keyword: "test", pageNo: 2, status: "active" });

      expect(apiGet).toHaveBeenCalledWith(
        expect.stringContaining("keyword=test"),
      );
      expect(apiGet).toHaveBeenCalledWith(
        expect.stringContaining("pageNo=2"),
      );
      expect(apiGet).toHaveBeenCalledWith(
        expect.stringContaining("status=active"),
      );
    });
  });

  describe("parse revision APIs", () => {
    it("should list parse revisions for a document version", async () => {
      const mockRevisions = [{ parseRevisionId: "pr-1", documentVersionId: "v-1", status: "success" }];
      vi.mocked(apiGet).mockResolvedValue(mockRevisions);

      const result = await fetchLibraryParseRevisions("doc-1", "v-1");

      expect(apiGet).toHaveBeenCalledWith("/library/documents/doc-1/versions/v-1/parse-revisions");
      expect(result).toEqual(mockRevisions);
    });

    it("should create a parse revision with parser options", async () => {
      const mockResponse = { jobId: "job-1", parseRevisionId: "pr-1", status: "queued" };
      vi.mocked(apiPostJson).mockResolvedValue(mockResponse);

      const body = {
        parserName: "auto",
        contentFormat: "markdown" as const,
        parseOptions: { ocrEnabled: true },
        reason: "manual_reparse",
      };
      const result = await createLibraryParseRevision("doc-1", "v-1", body);

      expect(apiPostJson).toHaveBeenCalledWith(
        "/library/documents/doc-1/versions/v-1/parse-revisions",
        body,
      );
      expect(result).toEqual(mockResponse);
    });

    it("should include parseRevisionId when fetching parsed text", async () => {
      vi.mocked(apiGet).mockResolvedValue({ text: "parsed", truncated: false, fullLength: 6 });

      await fetchDocumentText("doc-1", "preview", "pr-1");

      expect(apiGet).toHaveBeenCalledWith(
        "/library/documents/doc-1/text?mode=preview&parseRevisionId=pr-1",
      );
    });
  });
});

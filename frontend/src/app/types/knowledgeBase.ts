export interface KnowledgeBase {
  kbId: string;
  name: string;
  description: string | null;
  ownerId: string;
  defaultSecurityLevel: string;
  sparseIndexEnabled: boolean;
  graphIndexEnabled: boolean;
  requiredForActivation: {
    dense: boolean;
    sparse: boolean;
    graph: boolean;
  };
  status: "draft" | "active" | "disabled" | "archived";
  activeConfigRevisionId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeBaseCardViewModel {
  id: string;
  name: string;
  description: string;
  status: "active" | "inactive";
  updatedAtLabel: string;
  retrievalSummary: string;
}

export interface PageResponse<T> {
  items: T[];
  pageNo: number;
  pageSize: number;
  total: number;
}

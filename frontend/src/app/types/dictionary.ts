export type DictionaryStatus = "active" | "disabled";

export type DictionaryTypeCode =
  | "security_level"
  | "document_source_type"
  | "file_role"
  | "platform_role"
  | "kb_role"
  | "feedback_status";

export interface DictionaryTypeDTO {
  dictTypeId: string;
  code: DictionaryTypeCode | string;
  name: string;
  description: string | null;
  status: DictionaryStatus;
  createdAt: string;
  updatedAt: string;
}

export interface DictionaryItemDTO {
  dictItemId: string;
  typeCode: DictionaryTypeCode | string;
  code: string;
  name: string;
  description: string | null;
  sortOrder: number;
  status: DictionaryStatus;
  extra: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface DictionaryItemCreateRequest {
  code: string;
  name: string;
  description?: string | null;
  sortOrder?: number;
  status?: DictionaryStatus;
  extra?: Record<string, unknown>;
}

export interface DictionaryItemUpdateRequest {
  name?: string;
  description?: string | null;
  sortOrder?: number;
  status?: DictionaryStatus;
  extra?: Record<string, unknown>;
}

export interface DictionaryOption {
  value: string;
  label: string;
  disabled?: boolean;
}

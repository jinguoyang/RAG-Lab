import { apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type {
  DictionaryItemCreateRequest,
  DictionaryItemDTO,
  DictionaryItemUpdateRequest,
  DictionaryOption,
  DictionaryTypeCode,
  DictionaryTypeDTO,
} from "../types/dictionary";

const now = "1970-01-01T00:00:00Z";

function item(typeCode: DictionaryTypeCode, code: string, name: string, sortOrder: number): DictionaryItemDTO {
  return {
    dictItemId: `${typeCode}:${code}`,
    typeCode,
    code,
    name,
    description: null,
    sortOrder,
    status: "active",
    extra: {},
    createdAt: now,
    updatedAt: now,
  };
}

export const SYSTEM_DICTIONARY_FALLBACKS: Record<DictionaryTypeCode, DictionaryItemDTO[]> = {
  document_source_type: [
    item("document_source_type", "upload", "上传", 10),
    item("document_source_type", "sync", "同步", 20),
    item("document_source_type", "import", "导入", 30),
  ],
  file_role: [
    item("file_role", "source", "源文件", 10),
    item("file_role", "parsed_artifact", "解析产物", 20),
    item("file_role", "attachment", "附件", 30),
  ],
  platform_role: [
    item("platform_role", "platform_admin", "平台管理员", 10),
    item("platform_role", "platform_user", "平台用户", 20),
  ],
  kb_role: [
    item("kb_role", "kb_owner", "知识库管理员", 10),
    item("kb_role", "kb_editor", "知识库编辑", 20),
    item("kb_role", "kb_operator", "QA 操作员", 30),
    item("kb_role", "kb_viewer", "知识库读者", 40),
  ],
  feedback_status: [
    item("feedback_status", "unrated", "未标注", 10),
    item("feedback_status", "correct", "正确", 20),
    item("feedback_status", "partially_correct", "部分正确", 30),
    item("feedback_status", "wrong", "错误", 40),
    item("feedback_status", "citation_error", "引用错误", 50),
    item("feedback_status", "no_evidence", "无证据", 60),
  ],
};

export const SYSTEM_DICTIONARY_TYPES: Array<{ code: DictionaryTypeCode; name: string; fixedCodes?: boolean }> = [
  { code: "document_source_type", name: "文档来源" },
  { code: "file_role", name: "文件角色" },
  { code: "platform_role", name: "平台角色", fixedCodes: true },
  { code: "kb_role", name: "知识库角色", fixedCodes: true },
  { code: "feedback_status", name: "反馈状态" },
];

export async function fetchDictionaryTypes(): Promise<DictionaryTypeDTO[]> {
  return apiGet<DictionaryTypeDTO[]>("/dictionaries");
}

export async function fetchDictionaryItems(
  typeCode: string,
  activeOnly = true,
): Promise<DictionaryItemDTO[]> {
  const params = new URLSearchParams({ activeOnly: String(activeOnly) });
  return apiGet<DictionaryItemDTO[]>(`/dictionaries/${typeCode}/items?${params.toString()}`);
}

export async function fetchDictionaryItemsWithFallback(typeCode: string): Promise<DictionaryItemDTO[]> {
  try {
    const items = await fetchDictionaryItems(typeCode, true);
    if (items.length > 0) return items;
  } catch {
    // fall through to fallback
  }
  return (SYSTEM_DICTIONARY_FALLBACKS as Record<string, DictionaryItemDTO[]>)[typeCode] ?? [];
}

export async function fetchDictionaryBundle<T extends readonly string[]>(
  typeCodes: T,
): Promise<Record<T[number], DictionaryItemDTO[]>> {
  const entries = await Promise.all(
    typeCodes.map(async (typeCode) => [typeCode, await fetchDictionaryItemsWithFallback(typeCode)] as const),
  );
  return Object.fromEntries(entries) as Record<T[number], DictionaryItemDTO[]>;
}

export async function createDictionaryItem(
  typeCode: DictionaryTypeCode,
  request: DictionaryItemCreateRequest,
): Promise<DictionaryItemDTO> {
  return apiPostJson<DictionaryItemDTO>(`/dictionaries/${typeCode}/items`, request);
}

export async function updateDictionaryItem(
  typeCode: DictionaryTypeCode,
  itemCode: string,
  request: DictionaryItemUpdateRequest,
): Promise<DictionaryItemDTO> {
  return apiPatchJson<DictionaryItemDTO>(`/dictionaries/${typeCode}/items/${itemCode}`, request);
}

export function dictionaryItemsToOptions(items: DictionaryItemDTO[]): DictionaryOption[] {
  return items.map((item) => ({ value: item.code, label: item.name, disabled: item.status !== "active" }));
}

export function chooseActiveDictionaryValue(
  items: DictionaryItemDTO[],
  currentValue: string | null | undefined,
  fallbackValue = "",
): string {
  const activeCodes = items.filter((item) => item.status === "active").map((item) => item.code);
  if (currentValue && activeCodes.includes(currentValue)) return currentValue;
  if (fallbackValue && activeCodes.includes(fallbackValue)) return fallbackValue;
  return activeCodes[0] ?? currentValue ?? fallbackValue;
}

export function dictionaryLabel(items: DictionaryItemDTO[], code: string, fallback = code): string {
  return items.find((item) => item.code === code)?.name ?? fallback;
}

import { apiGet, apiPost } from "./apiClient";
import type { BindingCreateRequest, BindingResponse } from "../types/binding";

export function createBinding(data: BindingCreateRequest): Promise<BindingResponse> {
  return apiPost("/bindings", data);
}

export function listBindings(): Promise<BindingResponse[]> {
  return apiGet("/bindings");
}

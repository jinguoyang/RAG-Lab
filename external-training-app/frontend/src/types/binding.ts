export interface BindingCreateRequest {
  platformBaseUrl: string;
  platformApiKey: string;
}

export interface BindingResponse {
  id: string;
  platformBaseUrl: string;
  status: string;
  createdAt: string;
}

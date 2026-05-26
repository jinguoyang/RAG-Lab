export interface BindingCreateRequest {
  platformBaseUrl: string;
  platformAppId: string;
  platformApiKey: string;
}

export interface BindingResponse {
  id: string;
  platformBaseUrl: string;
  platformAppId: string;
  status: string;
  createdAt: string;
}

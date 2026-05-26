"""平台绑定 schemas。"""
from pydantic import BaseModel, Field


class BindingCreateRequest(BaseModel):
    platformBaseUrl: str = Field(min_length=1, max_length=512)
    platformAppId: str = Field(min_length=1, max_length=36)
    platformApiKey: str = Field(min_length=1, max_length=256)


class BindingResponse(BaseModel):
    id: str
    platformBaseUrl: str
    platformAppId: str
    status: str
    createdAt: str

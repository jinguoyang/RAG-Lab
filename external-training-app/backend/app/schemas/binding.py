"""平台绑定 schemas。"""
from pydantic import BaseModel, Field


class BindingCreateRequest(BaseModel):
    platformBaseUrl: str = Field(min_length=1, max_length=512)
    platformApiKey: str = Field(min_length=1, max_length=256)


class BindingResponse(BaseModel):
    id: str
    platformBaseUrl: str
    status: str
    createdAt: str

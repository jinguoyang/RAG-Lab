from pydantic import BaseModel


class HealthResponse(BaseModel):
    """健康检查响应，用于本地启动验证和基础探活。"""

    status: str
    app_name: str
    version: str
    environment: str

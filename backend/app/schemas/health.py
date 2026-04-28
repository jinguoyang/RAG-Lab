from pydantic import BaseModel


class HealthResponse(BaseModel):
    """健康检查响应，用于本地启动验证和基础探活。"""

    status: str
    app_name: str
    version: str
    environment: str


class DependencyHealthDTO(BaseModel):
    """单个外部依赖的健康摘要，不暴露密钥或连接串。"""

    name: str
    status: str
    detail: str


class DependencyHealthResponse(BaseModel):
    """外部依赖健康检查响应，用于发布前确认配置完整性。"""

    status: str
    dependencies: list[DependencyHealthDTO]

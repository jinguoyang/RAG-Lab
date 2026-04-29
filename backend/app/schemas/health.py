from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应，用于本地启动验证和基础探活。"""

    status: str
    app_name: str
    version: str
    environment: str


class DependencyConfigItemDTO(BaseModel):
    """依赖配置项摘要，只展示脱敏后的值和本地校验状态。"""

    key: str
    status: str
    displayValue: str | None
    sensitive: bool


class DependencyHealthDTO(BaseModel):
    """单个外部依赖的健康摘要，不暴露密钥或连接串。"""

    name: str
    status: str
    detail: str
    provider: str | None = None
    config: list[DependencyConfigItemDTO] = Field(default_factory=list)


class DependencyHealthResponse(BaseModel):
    """外部依赖健康检查响应，用于发布前确认配置完整性。"""

    status: str
    dependencies: list[DependencyHealthDTO]


class ProviderDiagnosticDTO(BaseModel):
    """模型类 Provider 诊断结果，默认只做本地配置和限流配置检查。"""

    name: str
    provider: str
    status: str
    connectivityStatus: str
    rateLimitStatus: str
    detail: str
    config: list[DependencyConfigItemDTO] = Field(default_factory=list)


class ProviderDiagnosticsResponse(BaseModel):
    """LLM、Embedding、Rerank Provider 的生产化诊断摘要。"""

    status: str
    diagnostics: list[ProviderDiagnosticDTO]

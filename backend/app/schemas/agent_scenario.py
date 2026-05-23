from typing import Any

from pydantic import BaseModel


class AgentScenarioFieldOptionDTO(BaseModel):
    """场景配置字段的可选项。"""

    value: str | int | bool
    label: str
    description: str | None = None


class AgentScenarioConfigFieldDTO(BaseModel):
    """场景模板暴露给前端的可配置字段。"""

    key: str
    label: str
    fieldType: str
    required: bool = False
    defaultValue: str | int | bool | list[str] | None = None
    options: list[AgentScenarioFieldOptionDTO] = []
    description: str | None = None


class AgentScenarioTemplateDTO(BaseModel):
    """内置场景模板摘要，用于创建场景化智能应用。"""

    templateId: str
    scenarioType: str
    name: str
    description: str
    defaultScenarioConfig: dict[str, Any]
    defaultPublishChannels: dict[str, bool]
    defaultEmbedSettings: dict[str, Any]
    configFields: list[AgentScenarioConfigFieldDTO]

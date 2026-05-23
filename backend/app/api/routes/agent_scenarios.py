from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.agent_scenario import AgentScenarioTemplateDTO
from app.schemas.auth import CurrentUserResponse
from app.services.agent_scenario_template_service import list_agent_scenario_templates

router = APIRouter(prefix="/agent-scenario-templates", tags=["agent-scenario-templates"])


@router.get("", response_model=list[AgentScenarioTemplateDTO])
def read_agent_scenario_templates(
    current_user: CurrentUserResponse = Depends(get_current_user),
) -> list[AgentScenarioTemplateDTO]:
    """返回内置业务助手场景模板；第一版只要求登录态。"""
    _ = current_user
    return list_agent_scenario_templates()

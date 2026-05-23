"""内置 Agent 场景模板服务。"""

from app.schemas.agent_scenario import (
    AgentScenarioConfigFieldDTO,
    AgentScenarioFieldOptionDTO,
    AgentScenarioTemplateDTO,
)


def list_agent_scenario_templates() -> list[AgentScenarioTemplateDTO]:
    """返回第一版内置场景模板，避免在 Sprint 47 引入模板 CRUD。"""
    return [
        AgentScenarioTemplateDTO(
            templateId="builtin_knowledge_qa_v1",
            scenarioType="knowledge_qa",
            name="知识库问答助手",
            description="面向制度、手册和业务文档的受控问答助手，默认要求回答带引用且无证据时拒答。",
            defaultScenarioConfig={
                "answerLength": "standard",
                "citationCount": 3,
                "noEvidencePolicy": "refuse",
                "showSuggestedQuestions": True,
                "greeting": "你好，我可以基于当前知识库回答问题。",
            },
            defaultPublishChannels={"api": True, "embed": False},
            defaultEmbedSettings={
                "enabled": False,
                "allowedOrigins": [],
                "theme": "light",
                "greeting": "你好，我是知识库问答助手。",
            },
            configFields=[
                AgentScenarioConfigFieldDTO(
                    key="answerLength",
                    label="回答长度",
                    fieldType="select",
                    required=True,
                    defaultValue="standard",
                    options=[
                        AgentScenarioFieldOptionDTO(value="brief", label="简洁"),
                        AgentScenarioFieldOptionDTO(value="standard", label="标准"),
                        AgentScenarioFieldOptionDTO(value="detailed", label="详细"),
                    ],
                ),
                AgentScenarioConfigFieldDTO(
                    key="citationCount",
                    label="引用数量",
                    fieldType="number",
                    required=True,
                    defaultValue=3,
                    description="建议返回的最大引用数量。",
                ),
                AgentScenarioConfigFieldDTO(
                    key="noEvidencePolicy",
                    label="无证据策略",
                    fieldType="select",
                    required=True,
                    defaultValue="refuse",
                    options=[
                        AgentScenarioFieldOptionDTO(value="refuse", label="拒答"),
                        AgentScenarioFieldOptionDTO(value="cautious", label="谨慎提示"),
                    ],
                ),
            ],
        ),
        AgentScenarioTemplateDTO(
            templateId="builtin_employee_training_v1",
            scenarioType="employee_training",
            name="员工培训助手",
            description="面向培训材料的讲解和测验助手，第一版聚焦主题讲解、出题、评分和错题解释。",
            defaultScenarioConfig={
                "audience": "new_employee",
                "defaultTopic": "",
                "difficulty": "normal",
                "questionCount": 5,
                "passingScore": 80,
                "recordTrainingResult": True,
            },
            defaultPublishChannels={"api": True, "embed": False},
            defaultEmbedSettings={
                "enabled": False,
                "allowedOrigins": [],
                "theme": "light",
                "greeting": "你好，我是员工培训助手。",
            },
            configFields=[
                AgentScenarioConfigFieldDTO(
                    key="audience",
                    label="培训对象",
                    fieldType="select",
                    required=True,
                    defaultValue="new_employee",
                    options=[
                        AgentScenarioFieldOptionDTO(value="new_employee", label="新员工"),
                        AgentScenarioFieldOptionDTO(value="frontline_staff", label="一线员工"),
                        AgentScenarioFieldOptionDTO(value="manager", label="管理人员"),
                    ],
                ),
                AgentScenarioConfigFieldDTO(
                    key="difficulty",
                    label="默认难度",
                    fieldType="select",
                    required=True,
                    defaultValue="normal",
                    options=[
                        AgentScenarioFieldOptionDTO(value="easy", label="基础"),
                        AgentScenarioFieldOptionDTO(value="normal", label="标准"),
                        AgentScenarioFieldOptionDTO(value="hard", label="进阶"),
                    ],
                ),
                AgentScenarioConfigFieldDTO(
                    key="questionCount",
                    label="题目数量",
                    fieldType="number",
                    required=True,
                    defaultValue=5,
                ),
                AgentScenarioConfigFieldDTO(
                    key="passingScore",
                    label="及格分",
                    fieldType="number",
                    required=True,
                    defaultValue=80,
                ),
            ],
        ),
    ]

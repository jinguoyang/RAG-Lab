"""Agent Runtime Task 7: 平台 Skill 适配器测试。"""

from app.services.agent_runtime.skill_adapter import PlatformSkill, select_allowed_skills


def test_select_allowed_skills_filters_by_scenario():
    skills = [
        PlatformSkill(name="retrieveDocuments", scenarios={"knowledge_qa", "employee_training"}, readonly=True),
        PlatformSkill(name="gradeSubjectiveAnswer", scenarios={"employee_training"}, readonly=False),
    ]

    selected = select_allowed_skills(skills, scenario_type="knowledge_qa")

    assert [item.name for item in selected] == ["retrieveDocuments"]


def test_select_allowed_skills_returns_empty_for_unknown_scenario():
    skills = [PlatformSkill(name="retrieveDocuments", scenarios={"knowledge_qa"})]

    selected = select_allowed_skills(skills, scenario_type="unknown")

    assert selected == []

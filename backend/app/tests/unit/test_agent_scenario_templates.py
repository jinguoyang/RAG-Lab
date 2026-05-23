"""内置场景模板接口测试。"""

from fastapi.testclient import TestClient

from app.main import app


def test_agent_scenario_templates_api_returns_builtin_templates():
    """场景模板接口应返回两个可创建智能应用的内置模板。"""
    client = TestClient(app)

    response = client.get("/api/v1/agent-scenario-templates", headers={"X-Dev-User": "admin"})

    assert response.status_code == 200
    data = response.json()
    template_ids = {item["templateId"] for item in data}
    assert template_ids == {"builtin_knowledge_qa_v1", "builtin_employee_training_v1"}

    knowledge_qa = next(item for item in data if item["scenarioType"] == "knowledge_qa")
    assert knowledge_qa["name"] == "知识库问答助手"
    assert knowledge_qa["defaultScenarioConfig"]["noEvidencePolicy"] == "refuse"
    assert any(field["key"] == "citationCount" for field in knowledge_qa["configFields"])

    employee_training = next(item for item in data if item["scenarioType"] == "employee_training")
    assert employee_training["name"] == "员工培训助手"
    assert employee_training["defaultScenarioConfig"]["questionCount"] == 5
    assert any(field["key"] == "passingScore" for field in employee_training["configFields"])

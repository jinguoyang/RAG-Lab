"""Agent Runtime Skill 适配器测试。

覆盖：场景筛选、Schema 构建、Tool 转换、审计、预算和异常。
"""
import json

import pytest

from app.services.agent_runtime.skill_adapter import (
    PlatformSkill,
    SkillBudgetExceededError,
    SkillSideEffectLevel,
    _build_pydantic_input_model,
    _maybe_record_audit,
    create_skill_tool,
    create_skill_tools,
    select_allowed_skills,
)


# ---------------------------------------------------------------------------
# 场景筛选
# ---------------------------------------------------------------------------


def test_select_allowed_skills_filters_by_scenario():
    skills = [
        PlatformSkill(name="retrieveDocuments", scenarios={"knowledge_qa", "employee_training"}),
        PlatformSkill(name="gradeSubjectiveAnswer", scenarios={"employee_training"}),
    ]
    selected = select_allowed_skills(skills, scenario_type="knowledge_qa")
    assert [item.name for item in selected] == ["retrieveDocuments"]


def test_select_allowed_skills_returns_empty_for_unknown_scenario():
    skills = [PlatformSkill(name="retrieveDocuments", scenarios={"knowledge_qa"})]
    selected = select_allowed_skills(skills, scenario_type="unknown")
    assert selected == []


def test_select_allowed_skills_filters_by_agent():
    skills = [
        PlatformSkill(name="skill_a", scenarios={"qa"}, allowed_agents={"agent_1"}),
        PlatformSkill(name="skill_b", scenarios={"qa"}, allowed_agents=set()),
    ]
    selected = select_allowed_skills(skills, scenario_type="qa", agent_id="agent_2")
    # skill_a 不允许 agent_2，skill_b 不限 agent
    assert [item.name for item in selected] == ["skill_b"]


# ---------------------------------------------------------------------------
# Schema 构建
# ---------------------------------------------------------------------------


def test_build_pydantic_input_model_required_fields():
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "查询文本"},
            "count": {"type": "integer", "description": "数量"},
        },
        "required": ["query"],
    }
    model = _build_pydantic_input_model("TestSkill", schema)
    # query 必填
    inst = model(query="hello")
    assert inst.query == "hello"
    assert inst.count is None


def test_build_pydantic_input_model_all_types():
    schema = {
        "type": "object",
        "properties": {
            "s": {"type": "string"},
            "i": {"type": "integer"},
            "f": {"type": "number"},
            "b": {"type": "boolean"},
            "a": {"type": "array"},
            "o": {"type": "object"},
        },
        "required": [],
    }
    model = _build_pydantic_input_model("AllTypes", schema)
    inst = model(s="x", i=1, f=1.5, b=True, a=[1], o={"k": "v"})
    assert inst.s == "x"
    assert inst.i == 1


# ---------------------------------------------------------------------------
# Tool 转换
# ---------------------------------------------------------------------------


def test_create_skill_tool_basic():
    skill = PlatformSkill(
        name="testSkill",
        description="测试 Skill",
        scenarios={"qa"},
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    tool = create_skill_tool(skill, invoke_fn=lambda query: {"result": query})
    assert tool.name == "testSkill"
    assert "测试" in tool.description


def test_create_skill_tool_invokes_fn():
    skill = PlatformSkill(
        name="echo",
        scenarios=set(),
        input_schema={
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        },
    )
    tool = create_skill_tool(skill, invoke_fn=lambda msg: {"echo": msg})
    result = tool.invoke({"msg": "hello"})
    assert result["echo"] == "hello"


def test_create_skill_tool_records_audit():
    audit_calls = []
    skill = PlatformSkill(
        name="audited",
        scenarios=set(),
        audit_required=True,
        input_schema={
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        },
    )
    tool = create_skill_tool(
        skill,
        invoke_fn=lambda x: {"ok": True},
        record_call_fn=lambda **kwargs: audit_calls.append(kwargs),
    )
    tool.invoke({"x": "test"})
    assert len(audit_calls) == 1
    assert audit_calls[0]["skill_name"] == "audited"
    assert audit_calls[0]["status"] == "success"


def test_create_skill_tool_records_audit_on_failure():
    audit_calls = []
    skill = PlatformSkill(
        name="fail_skill",
        scenarios=set(),
        audit_required=True,
        input_schema={"type": "object", "properties": {}, "required": []},
    )

    def _fail(**kwargs):
        raise ValueError("boom")

    tool = create_skill_tool(
        skill,
        invoke_fn=_fail,
        record_call_fn=lambda **kwargs: audit_calls.append(kwargs),
    )
    with pytest.raises(ValueError, match="boom"):
        tool.invoke({})
    assert len(audit_calls) == 1
    assert audit_calls[0]["status"] == "failed"
    assert audit_calls[0]["error_code"] == "ValueError"


def test_create_skill_tool_no_audit_when_disabled():
    audit_calls = []
    skill = PlatformSkill(
        name="no_audit",
        scenarios=set(),
        audit_required=False,
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    tool = create_skill_tool(
        skill,
        invoke_fn=lambda: {"ok": True},
        record_call_fn=lambda **kwargs: audit_calls.append(kwargs),
    )
    tool.invoke({})
    assert len(audit_calls) == 0


# ---------------------------------------------------------------------------
# 预算
# ---------------------------------------------------------------------------


def test_create_skill_tool_budget_exceeded():
    skill = PlatformSkill(
        name="limited",
        scenarios=set(),
        budget_calls_per_session=2,
        input_schema={"type": "object", "properties": {}, "required": []},
    )
    call_count = [0]

    def _get_count():
        return call_count[0]

    tool = create_skill_tool(
        skill,
        invoke_fn=lambda: {"ok": True},
        get_call_count_fn=_get_count,
    )
    # 前两次成功
    call_count[0] = 0
    tool.invoke({})
    call_count[0] = 1
    tool.invoke({})
    # 第三次超限
    call_count[0] = 2
    with pytest.raises(SkillBudgetExceededError):
        tool.invoke({})


# ---------------------------------------------------------------------------
# 批量转换
# ---------------------------------------------------------------------------


def test_create_skill_tools_batch():
    skills = [
        PlatformSkill(
            name="a",
            scenarios=set(),
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        PlatformSkill(
            name="b",
            scenarios=set(),
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
    ]
    tools = create_skill_tools(
        skills,
        invoke_fn_map={"a": lambda: {"a": 1}, "b": lambda: {"b": 2}},
    )
    assert len(tools) == 2
    assert {t.name for t in tools} == {"a", "b"}


def test_create_skill_tools_skips_missing_invoke_fn():
    skills = [
        PlatformSkill(
            name="exists",
            scenarios=set(),
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
        PlatformSkill(
            name="missing",
            scenarios=set(),
            input_schema={"type": "object", "properties": {}, "required": []},
        ),
    ]
    tools = create_skill_tools(
        skills,
        invoke_fn_map={"exists": lambda: {"ok": True}},
    )
    assert len(tools) == 1
    assert tools[0].name == "exists"


# ---------------------------------------------------------------------------
# 审计辅助
# ---------------------------------------------------------------------------


def test_maybe_record_audit_skips_when_not_required():
    calls = []
    skill = PlatformSkill(name="x", audit_required=False)
    _maybe_record_audit(skill, lambda **kw: calls.append(kw), "success", {}, None, None, 0.0)
    assert len(calls) == 0


def test_maybe_record_audit_skips_when_no_callback():
    skill = PlatformSkill(name="x", audit_required=True)
    # 不应抛异常
    _maybe_record_audit(skill, None, "success", {}, None, None, 0.0)


# ---------------------------------------------------------------------------
# 副作用等级
# ---------------------------------------------------------------------------


def test_side_effect_levels():
    assert SkillSideEffectLevel.READ_ONLY == "read_only"
    assert SkillSideEffectLevel.WRITE_SAFE == "write_safe"
    assert SkillSideEffectLevel.WRITE_DESTRUCTIVE == "write_destructive"


def test_platform_skill_defaults():
    skill = PlatformSkill(name="test")
    assert skill.side_effect_level == SkillSideEffectLevel.READ_ONLY
    assert skill.timeout_seconds == 30.0
    assert skill.max_retries == 0
    assert skill.budget_calls_per_session == 0
    assert skill.audit_required is True

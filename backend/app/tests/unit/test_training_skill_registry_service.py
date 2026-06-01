"""培训 Skill Registry 服务单元测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.schemas.training_skill import TrainingSkillDTO
from app.services.training_skill_registry_service import (
    get_training_skill,
    list_training_skills,
    record_training_skill_call,
)
from app.tables import training_skill_calls


# ---------------------------------------------------------------------------
# list_training_skills
# ---------------------------------------------------------------------------


def test_list_training_skills_returns_four():
    skills = list_training_skills()
    assert len(skills) == 4


def test_list_training_skills_returns_dto_instances():
    for skill in list_training_skills():
        assert isinstance(skill, TrainingSkillDTO)


# ---------------------------------------------------------------------------
# get_training_skill
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["buildLearningPlanDraft", "generateQuestionDrafts", "gradeSubjectiveAnswer", "classifyIntent"],
)
def test_get_training_skill_registered(name: str):
    skill = get_training_skill(name)
    assert skill is not None
    assert skill.skillName == name


def test_get_training_skill_unregistered_returns_none():
    assert get_training_skill("nonExistentSkill") is None


# ---------------------------------------------------------------------------
# inputSchema / outputSchema 非空
# ---------------------------------------------------------------------------


def test_all_skills_have_non_empty_schemas():
    for skill in list_training_skills():
        assert skill.inputSchema, f"{skill.skillName} inputSchema is empty"
        assert skill.outputSchema, f"{skill.skillName} outputSchema is empty"


def test_classify_intent_schema_describes_structured_decision():
    """Registry 应公开 Graph 实际使用的完整分类结构。"""
    skill = get_training_skill("classifyIntent")
    assert skill is not None
    properties = skill.outputSchema["properties"]
    assert set(properties["intent"]["enum"]) == {
        "domain_command",
        "course_qa",
        "teaching_adjustment",
        "multi_tool_task",
        "classroom_meta",
        "content_feedback",
        "off_topic",
        "clarification_required",
        "forbidden",
    }
    assert "command" in properties
    assert "reason" in properties


# ---------------------------------------------------------------------------
# record_training_skill_call
# ---------------------------------------------------------------------------


def test_record_training_skill_call_writes_row(db):
    record_training_skill_call(
        db,
        skill_name="buildLearningPlanDraft",
        status="success",
        session_id="sess-001",
        app_id="app-001",
        input_summary='{"jobTitle": "工程师"}',
        output_summary='{"planId": "plan-001"}',
        latency_ms=120,
    )
    db.flush()

    rows = db.execute(select(training_skill_calls)).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row.skill_name == "buildLearningPlanDraft"
    assert row.status == "success"
    assert row.session_id == "sess-001"
    assert row.app_id == "app-001"
    assert row.latency_ms == 120
    assert row.error_code is None


def test_record_training_skill_call_error_with_code(db):
    record_training_skill_call(
        db,
        skill_name="classifyIntent",
        status="error",
        error_code="LLM_TIMEOUT",
        latency_ms=5000,
    )
    db.flush()

    rows = db.execute(select(training_skill_calls)).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "error"
    assert row.error_code == "LLM_TIMEOUT"
    assert row.session_id is None

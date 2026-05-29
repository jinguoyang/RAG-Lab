"""培训 Skill Registry 服务。

显式管理允许调用的培训 Skill，维护审计日志。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_skill import TrainingSkillDTO
from app.tables import training_skill_calls

# ---------------------------------------------------------------------------
# Skill 定义（静态注册表）
# ---------------------------------------------------------------------------

_SKILLS: dict[str, TrainingSkillDTO] = {
    "buildLearningPlanDraft": TrainingSkillDTO(
        skillName="buildLearningPlanDraft",
        description="根据岗位信息和知识库文档，生成培训学习计划草案。",
        inputSchema={
            "type": "object",
            "properties": {
                "jobTitle": {"type": "string", "description": "岗位名称"},
                "jobDescription": {"type": "string", "description": "岗位职责描述"},
                "documentIds": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "关联的知识库文档 ID 列表",
                },
            },
            "required": ["jobTitle"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "planId": {"type": "string", "description": "生成的计划 ID"},
                "abilityGroups": {"type": "array", "description": "能力分组列表"},
                "status": {"type": "string", "description": "计划状态"},
            },
        },
    ),
    "generateQuestionDrafts": TrainingSkillDTO(
        skillName="generateQuestionDrafts",
        description="基于学习计划和知识库内容，生成培训考核题目草案。",
        inputSchema={
            "type": "object",
            "properties": {
                "planId": {"type": "string", "description": "学习计划 ID"},
                "sectionIndex": {"type": "integer", "description": "章节索引"},
                "questionCount": {"type": "integer", "description": "生成题目数量"},
            },
            "required": ["planId"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "description": "生成的题目列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "questionType": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
            },
        },
    ),
    "gradeSubjectiveAnswer": TrainingSkillDTO(
        skillName="gradeSubjectiveAnswer",
        description="对学员提交的主观题答案进行自动评分和反馈。",
        inputSchema={
            "type": "object",
            "properties": {
                "questionId": {"type": "string", "description": "题目 ID"},
                "answer": {"type": "string", "description": "学员提交的答案"},
                "rubric": {"type": "object", "description": "评分标准"},
            },
            "required": ["questionId", "answer"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "score": {"type": "number", "description": "得分"},
                "feedback": {"type": "string", "description": "评分反馈"},
                "passed": {"type": "boolean", "description": "是否通过"},
            },
        },
    ),
    "classifyIntent": TrainingSkillDTO(
        skillName="classifyIntent",
        description="识别学员在课堂对话中的意图类别，用于状态机路由。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "学员输入文本"},
                "currentState": {"type": "string", "description": "当前课堂状态"},
            },
            "required": ["query"],
        },
        outputSchema={
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "识别出的意图类别"},
                "confidence": {"type": "number", "description": "置信度 0-1"},
            },
        },
    ),
}


# ---------------------------------------------------------------------------
# 查询接口
# ---------------------------------------------------------------------------


def list_training_skills() -> list[TrainingSkillDTO]:
    """返回所有已注册 Skill 的描述列表。"""
    return list(_SKILLS.values())


def get_training_skill(skill_name: str) -> TrainingSkillDTO | None:
    """按名称获取已注册 Skill，未注册返回 None。"""
    return _SKILLS.get(skill_name)


# ---------------------------------------------------------------------------
# 审计写入
# ---------------------------------------------------------------------------


def record_training_skill_call(
    session: Session,
    *,
    skill_name: str,
    status: str,
    session_id: str | None = None,
    app_id: str | None = None,
    input_summary: str | None = None,
    output_summary: str | None = None,
    error_code: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """向审计表写入一条 Skill 调用记录。"""
    session.execute(
        insert(training_skill_calls).values(
            skill_call_id=new_id(),
            session_id=session_id,
            app_id=app_id,
            skill_name=skill_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            error_code=error_code,
            latency_ms=latency_ms,
            created_at=datetime.now(UTC),
        )
    )

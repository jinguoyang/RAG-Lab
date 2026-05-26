"""课堂会话、状态机、事件处理和受控答疑服务。"""
from __future__ import annotations


# ── 课堂状态机 ────────────────────────────────────────────────────────

CLASSROOM_STATES = (
    "INIT",
    "PLAN",
    "TEACH",
    "CHECK_UNDERSTAND",
    "QUIZ",
    "GRADE",
    "REVIEW",
    "SUMMARY",
    "NEXT_SECTION",
    "COMPLETED",
    "OFF_TOPIC",
)

CLASSROOM_TRANSITIONS: dict[str, list[str]] = {
    "INIT": ["PLAN"],
    "PLAN": ["TEACH"],
    "TEACH": ["CHECK_UNDERSTAND", "QUIZ", "OFF_TOPIC"],
    "CHECK_UNDERSTAND": ["QUIZ", "TEACH"],
    "QUIZ": ["GRADE"],
    "GRADE": ["REVIEW"],
    "REVIEW": ["SUMMARY", "TEACH"],
    "SUMMARY": ["NEXT_SECTION", "COMPLETED"],
    "NEXT_SECTION": ["TEACH"],
    "COMPLETED": [],
    "OFF_TOPIC": ["TEACH"],
}


def validate_classroom_transition(current_state: str, next_state: str) -> bool:
    """判断状态流转是否合法。"""
    allowed = CLASSROOM_TRANSITIONS.get(current_state, [])
    return next_state in allowed


# ── 异常定义 ──────────────────────────────────────────────────────────

class ClassroomSessionNotFoundError(Exception):
    """课堂会话不存在。"""


class ClassroomSessionConflictError(ValueError):
    """课堂会话冲突。"""


class ClassroomTransitionError(ValueError):
    """非法状态流转。"""


class ClassroomEventError(ValueError):
    """课堂事件处理错误。"""

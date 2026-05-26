"""课堂状态机流转规则测试。"""
import pytest


def test_valid_transitions():
    """验证所有合法的状态流转。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert "PLAN" in CLASSROOM_TRANSITIONS["INIT"]
    assert "TEACH" in CLASSROOM_TRANSITIONS["PLAN"]
    assert "CHECK_UNDERSTAND" in CLASSROOM_TRANSITIONS["TEACH"]
    assert "QUIZ" in CLASSROOM_TRANSITIONS["CHECK_UNDERSTAND"]
    assert "QUIZ" in CLASSROOM_TRANSITIONS["TEACH"]
    assert "GRADE" in CLASSROOM_TRANSITIONS["QUIZ"]
    assert "REVIEW" in CLASSROOM_TRANSITIONS["GRADE"]
    assert "SUMMARY" in CLASSROOM_TRANSITIONS["REVIEW"]
    assert "COMPLETED" in CLASSROOM_TRANSITIONS["SUMMARY"]
    assert "OFF_TOPIC" in CLASSROOM_TRANSITIONS["TEACH"]
    assert "TEACH" in CLASSROOM_TRANSITIONS["OFF_TOPIC"]


def test_invalid_transitions_rejected():
    """非法流转应不在目标列表中。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert "COMPLETED" not in CLASSROOM_TRANSITIONS["INIT"]
    assert "QUIZ" not in CLASSROOM_TRANSITIONS["INIT"]
    assert "INIT" not in CLASSROOM_TRANSITIONS["TEACH"]
    assert "PLAN" not in CLASSROOM_TRANSITIONS["QUIZ"]


def test_completed_is_terminal():
    """COMPLETED 是终态，不能流转到其他状态。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert CLASSROOM_TRANSITIONS.get("COMPLETED", []) == []


def test_off_topic_can_return_to_teach():
    """偏题状态可以回到教学状态。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert "TEACH" in CLASSROOM_TRANSITIONS["OFF_TOPIC"]


def test_validate_transition_accepts_valid():
    """validate_classroom_transition 接受合法流转。"""
    from app.services.training_classroom_service import validate_classroom_transition

    assert validate_classroom_transition("INIT", "PLAN") is True
    assert validate_classroom_transition("TEACH", "OFF_TOPIC") is True
    assert validate_classroom_transition("OFF_TOPIC", "TEACH") is True


def test_validate_transition_rejects_invalid():
    """validate_classroom_transition 拒绝非法流转。"""
    from app.services.training_classroom_service import validate_classroom_transition

    assert validate_classroom_transition("INIT", "COMPLETED") is False
    assert validate_classroom_transition("COMPLETED", "TEACH") is False
    assert validate_classroom_transition("QUIZ", "PLAN") is False

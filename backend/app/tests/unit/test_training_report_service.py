"""training_report_service 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from app.schemas.training_report import TrainingReportDTO, WeaknessItemDTO
from app.services.training_report_service import get_training_report


class _Row:
    """模拟 SQLAlchemy 行对象。"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# 无数据时返回空报表
# ---------------------------------------------------------------------------


class TestGetTrainingReportEmpty:
    """无进度、无答题记录时应返回空报表。"""

    def test_empty_report(self):
        mock_session = MagicMock()
        # 第一次 execute -> progress stats
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=0, passed_count=0, avg_score=None,
        )
        # 第二次 execute -> weakness rows
        mock_session.execute.return_value.all.return_value = []

        result = get_training_report(mock_session, "app-empty")

        assert result.appId == "app-empty"
        assert result.totalCount == 0
        assert result.passedCount == 0
        assert result.completionRate == 0.0
        assert result.averageScore == 0.0
        assert result.failedQuestionCount == 0
        assert result.weaknesses == []


# ---------------------------------------------------------------------------
# 有数据时的报表计算
# ---------------------------------------------------------------------------


class TestGetTrainingReportWithData:
    """有进度和答题记录时应正确计算报表。"""

    def test_report_with_data(self):
        mock_session = MagicMock()
        # progress: 4 total, 3 completed, avg 85.0
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=4, passed_count=3, avg_score=85.0,
        )
        # weakness: one question with 2 fails out of 4 attempts
        mock_session.execute.return_value.all.return_value = [
            _Row(
                question_id="q-001",
                content="什么是 RAG?",
                total_attempts=4,
                fail_count=2,
            ),
        ]

        result = get_training_report(mock_session, "app-001")

        assert result.appId == "app-001"
        assert result.totalCount == 4
        assert result.passedCount == 3
        assert result.completionRate == 0.75
        assert result.averageScore == 85.0
        assert result.failedQuestionCount == 1
        assert len(result.weaknesses) == 1
        assert result.weaknesses[0].questionId == "q-001"
        assert result.weaknesses[0].content == "什么是 RAG?"
        assert result.weaknesses[0].failCount == 2
        assert result.weaknesses[0].failRate == 0.5


# ---------------------------------------------------------------------------
# 完成率计算
# ---------------------------------------------------------------------------


class TestCompletionRate:
    """完成率边界情况。"""

    def test_all_completed(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=5, passed_count=5, avg_score=90.0,
        )
        mock_session.execute.return_value.all.return_value = []

        result = get_training_report(mock_session, "app-all-done")

        assert result.completionRate == 1.0
        assert result.passedCount == 5
        assert result.totalCount == 5

    def test_none_completed(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=3, passed_count=0, avg_score=40.0,
        )
        mock_session.execute.return_value.all.return_value = []

        result = get_training_report(mock_session, "app-none-done")

        assert result.completionRate == 0.0
        assert result.passedCount == 0

    def test_no_progress_records(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=0, passed_count=0, avg_score=None,
        )
        mock_session.execute.return_value.all.return_value = []

        result = get_training_report(mock_session, "app-no-records")

        assert result.completionRate == 0.0
        assert result.averageScore == 0.0


# ---------------------------------------------------------------------------
# 薄弱点排序
# ---------------------------------------------------------------------------


class TestWeaknessSorting:
    """薄弱点应按错误次数降序排列。"""

    def test_weaknesses_sorted_by_fail_count(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=10, passed_count=5, avg_score=70.0,
        )
        # 模拟 SQL 已按 fail_count DESC 排序
        mock_session.execute.return_value.all.return_value = [
            _Row(question_id="q-hard", content="难题", total_attempts=10, fail_count=8),
            _Row(question_id="q-mid", content="中等题", total_attempts=10, fail_count=4),
            _Row(question_id="q-easy", content="简单题", total_attempts=10, fail_count=1),
        ]

        result = get_training_report(mock_session, "app-sort")

        assert len(result.weaknesses) == 3
        assert result.weaknesses[0].questionId == "q-hard"
        assert result.weaknesses[0].failCount == 8
        assert result.weaknesses[1].questionId == "q-mid"
        assert result.weaknesses[1].failCount == 4
        assert result.weaknesses[2].questionId == "q-easy"
        assert result.weaknesses[2].failCount == 1

    def test_weakness_fail_rate_calculation(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=2, passed_count=1, avg_score=60.0,
        )
        mock_session.execute.return_value.all.return_value = [
            _Row(question_id="q-001", content="题目", total_attempts=8, fail_count=5),
        ]

        result = get_training_report(mock_session, "app-rate")

        assert result.weaknesses[0].failRate == 0.625

    def test_no_weaknesses(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.one.return_value = _Row(
            total_count=5, passed_count=5, avg_score=95.0,
        )
        mock_session.execute.return_value.all.return_value = []

        result = get_training_report(mock_session, "app-perfect")

        assert result.failedQuestionCount == 0
        assert result.weaknesses == []

"""学习计划本地保存和出题触发服务测试。"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas.training_plan import TrainingPlanSaveRequest
import pytest

from app.services.training_plan_service import (
    TrainingPlanConflictError,
    create_plan_draft,
    delete_plan,
    generate_questions_for_plan,
    get_plan,
    list_plans,
    save_plan,
    update_plan,
)
from app.tables import metadata, training_plans, training_post_quizzes, training_questions


def _session():
    """创建共享内存数据库会话。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    return engine, session


def test_list_plans_includes_platform_draft_not_saved_locally(monkeypatch):
    """本地列表应合并平台草稿，使服务重启后仍可继续编辑。"""
    session = MagicMock()
    mappings = MagicMock()
    mappings.all.return_value = []
    result = MagicMock()
    result.mappings.return_value = mappings
    session.execute.return_value = result

    class FakeClient:
        def __init__(self, base_url, api_key):
            pass

        def list_plan_drafts(self):
            return [{
                "planId": "plan-001",
                "appId": "app-001",
                "jobTitle": "财务",
                "jobDescription": "财务",
                "status": "draft",
                "abilityGroups": [],
                "documents": [],
                "evidenceChunkIds": [],
                "recommendReason": "",
                "version": 1,
                "createdAt": "2026-06-09T00:00:00+00:00",
                "updatedAt": "2026-06-09T00:00:00+00:00",
            }]

    monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
    monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

    plans = list_plans(session)

    assert [item["planId"] for item in plans] == ["plan-001"]
    assert plans[0]["status"] == "draft"


def test_create_plan_draft_rejects_duplicate_name_ignoring_case_and_spaces(monkeypatch):
    """新建计划名称应去除首尾空格并忽略英文大小写判重。"""
    session = MagicMock()
    mappings = MagicMock()
    mappings.all.return_value = []
    result = MagicMock()
    result.mappings.return_value = mappings
    session.execute.return_value = result

    class FakeClient:
        def __init__(self, base_url, api_key):
            pass

        def list_plan_drafts(self):
            return [{"planId": "draft-001", "planName": "Finance Plan", "jobTitle": "财务"}]

    monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
    monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)
    request = MagicMock(planName=" finance plan ", jobTitle="财务", jobDescription="财务")

    with pytest.raises(TrainingPlanConflictError, match="计划名称已存在"):
        create_plan_draft(session, "admin", request)


def test_save_plan_rejects_duplicate_local_name():
    """保存平台草稿时不得使用其他本地计划的名称。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-existing",
                app_id="app-001",
                job_title="安全员",
                job_description="",
                status="saved",
                ability_groups=[],
                documents=[],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=[],
                version=1,
                metadata={"planName": "财务计划"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        request = TrainingPlanSaveRequest(
            planName=" 财务计划 ",
            appId="app-001",
            jobTitle="财务",
            documents=[{
                "documentId": "doc-001",
                "title": "财务制度",
                "sections": [{
                    "sectionId": "section-001",
                    "title": "财务制度概览",
                    "learningObjective": "掌握财务制度基本要求",
                }],
            }],
        )

        with pytest.raises(TrainingPlanConflictError, match="计划名称已存在"):
            save_plan(session, "admin", "plan-new", request)
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_update_plan_allows_current_name_but_rejects_other_plan_name():
    """编辑计划时允许保留自身名称，但不能改成其他计划的名称。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        for plan_id, plan_name in (("plan-001", "财务计划"), ("plan-002", "安全计划")):
            session.execute(
                training_plans.insert().values(
                    plan_id=plan_id,
                    app_id="app-001",
                    job_title=plan_name,
                    job_description="",
                    status="saved",
                    ability_groups=[],
                    documents=[],
                    evidence_chunk_ids=[],
                    recommend_reason="",
                    reading_order=[],
                    version=1,
                    metadata={"planName": plan_name},
                    created_at=now,
                    updated_at=now,
                )
            )
        session.commit()

        update_plan(session, "admin", "plan-001", MagicMock(
            planName=" 财务计划 ",
            documents=None,
            readingOrder=None,
            employeeIds=None,
            sections=None,
        ))
        with pytest.raises(TrainingPlanConflictError, match="计划名称已存在"):
            update_plan(session, "admin", "plan-001", MagicMock(
                planName="安全计划",
                documents=None,
                readingOrder=None,
                employeeIds=None,
                sections=None,
            ))
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_delete_plan_proxies_platform_draft_when_not_saved_locally(monkeypatch):
    """本地不存在记录时，删除操作应代理到平台草稿。"""
    session = MagicMock()
    mapping = MagicMock()
    mapping.first.return_value = None
    result = MagicMock()
    result.mappings.return_value = mapping
    session.execute.return_value = result

    class FakeClient:
        def __init__(self, base_url, api_key):
            pass

        def delete_plan_draft(self, plan_id):
            return {"planId": plan_id, "status": "deleted"}

    monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
    monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

    assert delete_plan(session, "admin", "draft-001") == {
        "planId": "draft-001",
        "status": "deleted",
    }


def test_delete_saved_plan_also_deletes_platform_draft(monkeypatch):
    """删除已保存计划时应同步删除平台草稿，避免刷新后重新显示为草稿。"""
    engine, session = _session()
    deleted_platform_plan_ids: list[str] = []
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-001",
                app_id="app-001",
                job_title="财务",
                job_description="",
                status="saved",
                ability_groups=[],
                documents=[],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=[],
                version=1,
                metadata={"planName": "财务计划"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

        class FakeClient:
            def __init__(self, base_url, api_key):
                pass

            def delete_plan_draft(self, plan_id):
                deleted_platform_plan_ids.append(plan_id)
                return {"planId": plan_id, "status": "deleted"}

        monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
        monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

        assert delete_plan(session, "admin", "plan-001") == {
            "planId": "plan-001",
            "status": "deleted",
        }
        assert deleted_platform_plan_ids == ["plan-001"]
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_save_plan_inserts_final_plan_without_existing_draft():
    """最终保存计划时允许本地不存在草稿，只落库 saved 计划并回显员工绑定。"""
    engine, session = _session()
    try:
        request = TrainingPlanSaveRequest(
            planName="安全员入职计划",
            appId="app-001",
            jobTitle="安全员",
            jobDescription="负责现场风险识别",
            abilityGroups=[{"name": "基础认知"}],
            documents=[{
                "documentId": "doc-001",
                "title": "安全手册",
                "difficulty": "初级",
                "category": "安全",
                "sections": [{
                    "sectionId": "section-001",
                    "title": "识别现场风险",
                    "learningObjective": "能够识别现场风险",
                    "evidenceChunkIds": ["chunk-001"],
                    "keyPoints": ["风险识别"],
                    "checkpointCriteria": ["能识别风险"],
                    "estimatedMinutes": 8,
                    "required": True,
                }],
            }],
            evidenceChunkIds=["chunk-001"],
            recommendReason="覆盖基础安全要求",
            employeeIds=["emp-001", "emp-002"],
            version=1,
        )

        result = save_plan(session, "admin", "plan-001", request)
        plan = get_plan(session, "plan-001")

        assert result == {"planId": "plan-001", "status": "saved"}
        assert plan["status"] == "saved"
        assert plan["employeeIds"] == ["emp-001", "emp-002"]
        assert plan["documents"][0]["documentId"] == "doc-001"
        assert plan["documents"][0]["sections"][0]["sectionId"] == "section-001"
        assert "sections" not in plan
        assert "readingOrder" not in plan
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_get_plan_keeps_document_passed_after_later_failed_retry():
    """文档任意一次课后测验通过后，后续重考失败仍保持通过状态。"""
    engine, session = _session()
    try:
        request = TrainingPlanSaveRequest(
            planName="安全员入职计划",
            appId="app-001",
            jobTitle="安全员",
            documents=[{
                "documentId": "doc-001",
                "title": "安全手册",
                "sections": [{
                    "sectionId": "section-001",
                    "title": "安全要求",
                    "learningObjective": "掌握安全要求",
                }],
            }],
        )
        save_plan(session, "admin", "plan-001", request)
        now = datetime.now(timezone.utc)
        session.execute(
            training_post_quizzes.insert(),
            [
                {
                    "quiz_id": "quiz-passed",
                    "session_id": "session-001",
                    "plan_id": "plan-001",
                    "app_id": "app-001",
                    "end_user_id": "demo-user",
                    "document_id": "doc-001",
                    "questions": [],
                    "answers": [],
                    "results": [],
                    "score": 20,
                    "passed": True,
                    "status": "submitted",
                    "created_at": now,
                    "submitted_at": now,
                    "updated_at": now,
                },
                {
                    "quiz_id": "quiz-failed-retry",
                    "session_id": "session-002",
                    "plan_id": "plan-001",
                    "app_id": "app-001",
                    "end_user_id": "demo-user",
                    "document_id": "doc-001",
                    "questions": [],
                    "answers": [],
                    "results": [],
                    "score": 15,
                    "passed": False,
                    "status": "submitted",
                    "created_at": now,
                    "submitted_at": now,
                    "updated_at": now,
                },
            ],
        )
        session.commit()

        plan = get_plan(session, "plan-001")

        assert plan["passedDocuments"] == ["doc-001"]
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_generate_questions_skips_document_generated_in_other_plan(monkeypatch):
    """同一文档已有草稿题目时，后台自动出题不重复调用平台。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-001",
                app_id="app-001",
                job_title="安全员",
                job_description="负责现场风险识别",
                status="saved",
                ability_groups=[],
                documents=[{"documentId": "doc-001", "title": "安全手册"}],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=["doc-001"],
                version=1,
                metadata={"planName": "安全员入职计划", "employeeIds": []},
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            training_questions.insert().values(
                question_id="question-existing",
                plan_id="other-plan",
                app_id="app-001",
                question_type="single_choice",
                category="practice",
                content="已有题目",
                options=[],
                correct_answer="A",
                explanation="",
                rubric=None,
                evidence_chunk_ids=[],
                status="draft",
                metadata={"documentId": "doc-001"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

        calls = []

        class FakeClient:
            def __init__(self, base_url, api_key):
                pass

            def create_question_drafts(self, **kwargs):
                calls.append(kwargs)
                return []

        class SessionFactory:
            def __call__(self):
                return session

        monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
        monkeypatch.setattr("app.core.database.SessionLocal", SessionFactory())
        monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

        generate_questions_for_plan("plan-001")

        assert calls == []
    finally:
        if session.is_active:
            session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_generate_questions_does_not_treat_legacy_approved_as_duplicate(monkeypatch):
    """自动生成只以 draft/published 去重，旧 approved 状态不阻止生成。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-001",
                app_id="app-001",
                job_title="安全员",
                job_description="负责现场风险识别",
                status="saved",
                ability_groups=[],
                documents=[{"documentId": "doc-001", "title": "安全手册"}],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=["doc-001"],
                version=1,
                metadata={"planName": "安全员入职计划", "employeeIds": []},
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            training_questions.insert().values(
                question_id="question-approved",
                plan_id="other-plan",
                app_id="app-001",
                question_type="single_choice",
                category="practice",
                content="旧状态题目",
                options=[],
                correct_answer="A",
                explanation="",
                rubric=None,
                evidence_chunk_ids=[],
                status="approved",
                metadata={"documentId": "doc-001"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        calls = []

        class FakeClient:
            def __init__(self, base_url, api_key):
                pass

            def create_question_drafts(self, **kwargs):
                calls.append(kwargs)
                return []

        class SessionFactory:
            def __call__(self):
                return session

        monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
        monkeypatch.setattr("app.core.database.SessionLocal", SessionFactory())
        monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

        generate_questions_for_plan("plan-001")

        assert len(calls) == 1
        assert calls[0]["document_ids"] == ["doc-001"]
    finally:
        if session.is_active:
            session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_generate_questions_sends_ability_group_names(monkeypatch):
    """自动出题只向平台发送能力组名称，避免对象结构触发请求校验失败。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-001",
                app_id="app-001",
                job_title="财务",
                job_description="",
                status="saved",
                ability_groups=[
                    {"name": "呆滞物料识别与管理", "description": "掌握识别和处置要求"},
                    {"name": "物料存贮与环境控制", "description": "掌握存贮环境要求"},
                ],
                documents=[{"documentId": "doc-001", "title": "管理办法"}],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=["doc-001"],
                version=1,
                metadata={"planName": "财务学习计划", "employeeIds": []},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        calls = []

        class FakeClient:
            def __init__(self, base_url, api_key):
                pass

            def create_question_drafts(self, **kwargs):
                calls.append(kwargs)
                return []

        class SessionFactory:
            def __call__(self):
                return session

        monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
        monkeypatch.setattr("app.core.database.SessionLocal", SessionFactory())
        monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

        generate_questions_for_plan("plan-001")

        assert calls[0]["ability_groups"] == [
            "呆滞物料识别与管理",
            "物料存贮与环境控制",
        ]
    finally:
        if session.is_active:
            session.close()
        metadata.drop_all(engine)
        engine.dispose()

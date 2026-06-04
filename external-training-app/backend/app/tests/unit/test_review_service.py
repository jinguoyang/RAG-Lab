"""审核服务调用平台侧草稿生成的回归测试。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.tables import metadata, training_plans


def test_generate_plan_draft_uses_platform_response_app_id(monkeypatch):
    """生成学习计划草稿时应使用平台返回的真实草稿数据。"""
    expected_app_id = "11111111-1111-4111-8111-111111111111"
    platform_plan_id = "22222222-2222-4222-8222-222222222222"
    platform_created_at = "2026-06-04T07:12:12.863064+00:00"
    captured = {}

    monkeypatch.setenv("EXT_TRAINING_PLATFORM_BASE_URL", "http://platform/api/v1")
    monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")

    def fake_create_plan_draft(self, job_title, job_description):
        captured.update(
            {
                "job_title": job_title,
                "job_description": job_description,
            }
        )
        return {
            "planId": platform_plan_id,
            "appId": expected_app_id,
            "jobTitle": job_title,
            "jobDescription": job_description,
            "status": "draft",
            "abilityGroups": [{"name": "基础认知", "description": "理解岗位基础。"}],
            "documents": [],
            "evidenceChunkIds": [],
            "recommendReason": "测试推荐理由",
            "readingOrder": [],
            "version": 1,
            "createdAt": platform_created_at,
            "updatedAt": platform_created_at,
        }

    monkeypatch.setattr(
        "app.services.platform_client.PlatformClient.create_plan_draft",
        fake_create_plan_draft,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    try:
        from app.services.review_service import generate_plan_draft

        result = generate_plan_draft(session, "安全员", "负责现场风险识别")
        mirrored_plan = session.execute(training_plans.select()).mappings().one()
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()

    assert "app_id" not in captured
    assert result["draft"]["appId"] == expected_app_id
    assert result["draft"]["planId"] == platform_plan_id
    assert result["draft"]["createdAt"] == platform_created_at
    assert mirrored_plan["plan_id"] == platform_plan_id

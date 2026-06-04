"""审核服务调用平台侧草稿生成的回归测试。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.tables import metadata


def test_generate_plan_draft_uses_configured_platform_app_id(monkeypatch):
    """生成学习计划草稿时应使用 env 配置的平台 App ID。"""
    expected_app_id = "11111111-1111-4111-8111-111111111111"
    captured = {}

    monkeypatch.setenv("EXT_TRAINING_PLATFORM_BASE_URL", "http://platform/api/v1")
    monkeypatch.setenv("EXT_TRAINING_PLATFORM_APP_ID", expected_app_id)
    monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")

    def fake_create_plan_draft(self, app_id, job_title, job_description):
        captured.update(
            {
                "app_id": app_id,
                "job_title": job_title,
                "job_description": job_description,
            }
        )
        return {
            "abilityGroups": [{"name": "基础认知", "description": "理解岗位基础。"}],
            "documents": [],
            "evidenceChunkIds": [],
            "recommendReason": "测试推荐理由",
            "readingOrder": [],
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
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()

    assert captured["app_id"] == expected_app_id
    assert result["draft"]["appId"] == expected_app_id

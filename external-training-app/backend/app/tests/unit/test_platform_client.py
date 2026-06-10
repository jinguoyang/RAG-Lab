"""平台客户端契约测试。"""

import httpx


def test_chat_uses_platform_camel_case_conversation_id(monkeypatch):
    """应用端调用平台对话接口时应使用 conversationId。"""
    from app.services.platform_client import PlatformClient

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            status_code=200,
            json={"answer": "ok", "conversationId": "conv-001"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    PlatformClient("http://platform/api/v1", "key").chat("conv-001", "你好", {"k": "v"})

    assert captured["json"]["conversationId"] == "conv-001"
    assert "conversation_id" not in captured["json"]


def test_create_plan_draft_uses_api_key_without_app_id(monkeypatch):
    """学习计划草稿生成只依赖 Bearer appKey，不再提交 appId。"""
    from app.services.platform_client import PlatformClient

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            status_code=201,
            json={
                "planId": "plan-001",
                "appId": "platform-app-001",
                "jobTitle": "安全员",
                "jobDescription": "负责现场安全",
                "status": "draft",
                "abilityGroups": [],
                "documents": [],
                "evidenceChunkIds": [],
                "recommendReason": "",
                "readingOrder": [],
                "version": 1,
                "createdAt": "2026-06-04T00:00:00+00:00",
                "updatedAt": "2026-06-04T00:00:00+00:00",
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    PlatformClient("http://platform/api/v1", "key").create_plan_draft(
        "安全员入职计划",
        "安全员",
        "负责现场安全",
    )

    assert captured["headers"]["Authorization"] == "Bearer key"
    assert captured["json"] == {
        "planName": "安全员入职计划",
        "jobTitle": "安全员",
        "jobDescription": "负责现场安全",
    }


def test_list_plan_drafts_uses_platform_api_key(monkeypatch):
    """外部应用应通过 App API Key 查询平台已持久化的学习计划草稿。"""
    from app.services.platform_client import PlatformClient

    captured = {}

    def fake_get(url, headers, timeout):
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return httpx.Response(
            status_code=200,
            json=[{"planId": "plan-001", "status": "draft"}],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = PlatformClient("http://platform/api/v1", "key").list_plan_drafts()

    assert captured["url"] == "http://platform/api/v1/training/plans/drafts"
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert result[0]["planId"] == "plan-001"


def test_delete_plan_draft_uses_platform_api_key(monkeypatch):
    """外部应用删除平台草稿时应使用当前 App API Key。"""
    from app.services.platform_client import PlatformClient

    captured = {}

    def fake_delete(url, headers, timeout):
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return httpx.Response(
            status_code=200,
            json={"planId": "plan-001", "status": "deleted"},
            request=httpx.Request("DELETE", url),
        )

    monkeypatch.setattr(httpx, "delete", fake_delete)

    result = PlatformClient("http://platform/api/v1", "key").delete_plan_draft("plan-001")

    assert captured["url"] == "http://platform/api/v1/training/plans/drafts/plan-001"
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert result["status"] == "deleted"


def test_create_question_drafts_uses_api_key_without_app_id(monkeypatch):
    """题库草稿生成不允许通过请求体切换 App。"""
    from app.services.platform_client import PlatformClient

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(status_code=201, json=[], request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    PlatformClient("http://platform/api/v1", "key").create_question_drafts(
        "plan-001",
        "安全员",
        ["基础认知"],
        3,
        ["doc-001"],
    )

    assert "appId" not in captured["json"]
    assert captured["json"]["planId"] == "plan-001"
    assert captured["json"]["documentIds"] == ["doc-001"]


def test_grade_subjective_answer_does_not_send_question_id(monkeypatch):
    """主观题评分只向平台发送评分材料，不发送题库 questionId。"""
    from app.services.platform_client import PlatformClient

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return httpx.Response(
            status_code=200,
            json={"score": 5, "passed": True, "reason": "ok", "matchedCriteria": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    PlatformClient("http://platform/api/v1", "key").grade_subjective_answer({
        "content": "说明处理步骤",
        "answer": "先识别风险，再记录上报。",
        "rubric": {"totalScore": 5, "criteria": [{"name": "识别风险", "score": 2}]},
        "evidenceChunkIds": ["chunk-001"],
    })

    assert captured["url"].endswith("/training/post-quizzes/subjective-grading")
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert "questionId" not in captured["json"]

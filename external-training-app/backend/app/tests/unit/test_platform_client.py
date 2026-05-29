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

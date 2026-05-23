from app.services.qa_providers import HttpLlmProvider


def test_http_llm_rewrite_query_normalizes_answer_like_output():
    """Query rewrite 只能产出短检索式，避免把答案型长文本传给检索链路。"""
    provider = object.__new__(HttpLlmProvider)
    provider._chat = lambda _messages, **_kwargs: """
### 一、处置方式
1. 内部调剂：优先在其他部门使用。
2. 退货处理：与供应商协商退货。
3. 折价销售：低于成本价处理。
4. 报废处理：无法利用的报废。
"""

    rewritten = provider.rewrite_query("呆滞物料的处置方式有哪些？")

    assert "\n" not in rewritten
    assert "###" not in rewritten
    assert "1." not in rewritten
    assert len(rewritten) <= 160
    assert "呆滞物料" in rewritten


def test_http_llm_rewrite_query_limits_provider_output(monkeypatch):
    """Query rewrite 请求限制输出长度，减少短问题被模型长答拖慢的概率。"""
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "呆滞物料处置方式有哪些"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

    def fake_post(*_args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("httpx.post", fake_post)
    provider = object.__new__(HttpLlmProvider)
    provider._endpoint = "http://example.test/chat"
    provider._api_key = None
    provider._model = "test-model"
    provider.last_usage = {}

    rewritten = provider.rewrite_query("呆滞物料的处置方式有哪些？")

    assert rewritten == "呆滞物料处置方式有哪些"
    assert captured["json"]["max_tokens"] == 64

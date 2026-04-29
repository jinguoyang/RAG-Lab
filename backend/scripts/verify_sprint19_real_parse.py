"""Sprint 19 真实解析与 Chunk 入库验收脚本。

脚本优先验证本地可重复的解析、切分和 Embedding 契约，不依赖真实外部网络。
真实 Provider 连通性留给环境复测；这里确保代码路径不再用占位 Chunk 冒充成功。
"""

from pathlib import Path
import sys
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
EXAMPLE_DIR = ROOT_DIR / "docs" / "examples"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.chunk_payload import build_chunk_index_payload  # noqa: E402
from app.services.document_parsing import DocumentParseError, parse_document  # noqa: E402
from app.services.qa_providers import HttpEmbeddingProvider, HttpLlmProvider  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """用明确失败原因标记 Sprint 19 验收缺口。"""
    if not condition:
        raise AssertionError(message)


def _example_by_extension(extension: str) -> Path:
    """按扩展名读取样例文件，缺失时直接暴露准备问题。"""
    matches = sorted(EXAMPLE_DIR.glob(f"*{extension}"))
    _assert(matches, f"docs/examples 缺少 {extension} 样例文件")
    return matches[0]


def verify_real_document_parsers() -> None:
    """校验 txt、md、pdf、docx 都能解析为真实 Chunk 和结构化 metadata。"""
    expected = {
        ".txt": {"requires_page": False, "requires_section": False},
        ".md": {"requires_page": False, "requires_section": True},
        ".pdf": {"requires_page": True, "requires_section": False},
        ".docx": {"requires_page": False, "requires_section": True},
    }
    for extension, rules in expected.items():
        path = _example_by_extension(extension)
        parsed = parse_document(path.name, None, path.read_bytes(), chunk_size=700, chunk_overlap=80)
        _assert(parsed.chunks, f"{extension} 未生成 Chunk")
        _assert(parsed.parser_name != "placeholder", f"{extension} 仍在使用占位解析器")
        _assert(parsed.parser_version, f"{extension} 缺少 parser version")
        _assert(all(chunk.content.strip() for chunk in parsed.chunks), f"{extension} 生成了空 Chunk")
        _assert(
            all("占位 Chunk" not in chunk.content for chunk in parsed.chunks),
            f"{extension} 不能用占位 Chunk 冒充解析成功",
        )
        _assert(
            all(chunk.metadata.get("parserName") == parsed.parser_name for chunk in parsed.chunks),
            f"{extension} Chunk metadata 缺少 parserName",
        )
        if rules["requires_page"]:
            _assert(any(chunk.page_no is not None for chunk in parsed.chunks), f"{extension} 缺少页码 metadata")
        if rules["requires_section"]:
            _assert(any(chunk.section for chunk in parsed.chunks), f"{extension} 缺少章节 metadata")


def verify_unsupported_binary_fails() -> None:
    """校验无法识别的二进制文件显式失败，不创建成功占位 Chunk。"""
    try:
        parse_document("bad.bin", "application/octet-stream", b"\x00\x01\x02\x03")
    except DocumentParseError as exc:
        _assert(exc.error_code == "UNSUPPORTED_FILE_TYPE", "不支持格式应返回稳定错误码")
        return
    raise AssertionError("不支持格式必须解析失败，不能生成占位 Chunk")


def verify_chunk_payload_contract() -> None:
    """校验后续 Milvus/OpenSearch/Neo4j 复用的 Chunk payload 字段完整。"""
    kb_id = uuid4()
    document_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    payload = build_chunk_index_payload(
        chunk={
            "chunk_id": chunk_id,
            "kb_id": kb_id,
            "document_id": document_id,
            "version_id": version_id,
            "content": "真实 Chunk 正文",
            "content_hash": "abc123",
            "page_no": 3,
            "section": "测试章节",
            "security_level": "public",
            "status": "active",
            "metadata": {"parserName": "plain_text"},
        },
        document_status="active",
        version_status="active",
        access_filter={
            "allowSubjectKeys": ["role:kb_owner"],
            "denySubjectKeys": [],
            "filterHash": "filter-1",
        },
        embedding=[0.1, 0.2, 0.3],
    )
    for key in [
        "chunkId",
        "kbId",
        "documentId",
        "versionId",
        "content",
        "contentHash",
        "pageNo",
        "section",
        "securityLevel",
        "documentStatus",
        "versionStatus",
        "chunkStatus",
        "allowSubjectKeys",
        "denySubjectKeys",
        "filterHash",
        "embedding",
        "embeddingDimension",
    ]:
        _assert(key in payload, f"Chunk payload 缺少字段: {key}")
    _assert(payload["embeddingDimension"] == 3, "Chunk payload 未记录 embedding 维度")


def verify_embedding_http_contract() -> None:
    """校验 Embedding Provider 使用 OpenAI-compatible 请求和响应契约。"""
    import httpx

    calls: list[dict] = []
    original_post = httpx.post

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"embedding": [0.25, 0.5]}]}

    def fake_post(endpoint: str, headers: dict, json: dict, timeout: int) -> FakeResponse:
        calls.append({"endpoint": endpoint, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    class SettingsStub:
        embedding_endpoint = "https://embedding.example.test/v1/embeddings"
        embedding_api_key = "secret"
        embedding_model = "text-embedding-v2"

    try:
        httpx.post = fake_post
        vector = HttpEmbeddingProvider(SettingsStub()).embed_query("真实 Chunk 正文")
    finally:
        httpx.post = original_post

    _assert(vector == [0.25, 0.5], "Embedding Provider 未解析 OpenAI-compatible embedding 响应")
    _assert(calls, "Embedding Provider 未发起 HTTP 请求")
    call = calls[0]
    _assert(call["json"] == {"model": "text-embedding-v2", "input": "真实 Chunk 正文"}, "Embedding 请求体不符合契约")
    _assert(call["headers"].get("Authorization") == "Bearer secret", "Embedding 请求未携带 Bearer API Key")


def verify_llm_http_contract() -> None:
    """校验 LLM Provider 使用 OpenAI-compatible Chat Completion 契约。"""
    import httpx

    calls: list[dict] = []
    original_post = httpx.post

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "重写后的问题"}}]}

    def fake_post(endpoint: str, headers: dict, json: dict, timeout: int) -> FakeResponse:
        calls.append({"endpoint": endpoint, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    class SettingsStub:
        llm_endpoint = "https://llm.example.test/v1/chat/completions"
        llm_api_key = "secret"
        llm_model = "qwen3.5-flash"

    try:
        httpx.post = fake_post
        rewritten = HttpLlmProvider(SettingsStub()).rewrite_query("原始问题")
    finally:
        httpx.post = original_post

    _assert(rewritten == "重写后的问题", "LLM Provider 未解析 Chat Completion 响应")
    _assert(calls, "LLM Provider 未发起 HTTP 请求")
    call = calls[0]
    _assert(call["json"]["model"] == "qwen3.5-flash", "LLM 请求体缺少模型名")
    _assert(call["json"]["messages"][0]["role"] == "system", "LLM 请求体不符合 messages 契约")
    _assert(call["headers"].get("Authorization") == "Bearer secret", "LLM 请求未携带 Bearer API Key")


def verify_ingest_worker_uses_real_parser_contract() -> None:
    """校验真实入库 Worker 已接入解析器、Embedding 和标准 Chunk payload。"""
    source = (BACKEND_DIR / "app/services/document_service.py").read_text(encoding="utf-8")
    _assert("parse_document(" in source, "入库 Worker 未调用真实文档解析器")
    _assert("build_chunk_index_payload(" in source, "入库 Worker 未构造标准 Chunk payload")
    _assert(
        "get_qa_run_providers().embedding" in source or "provider_set.embedding" in source,
        "入库 Worker 未接入 Embedding Provider 契约",
    )
    _assert("占位 Chunk" not in source, "入库 Worker 仍包含占位 Chunk 成功路径")


def main() -> None:
    """执行 Sprint 19 真实解析和 Embedding 契约验收。"""
    verify_real_document_parsers()
    verify_unsupported_binary_fails()
    verify_chunk_payload_contract()
    verify_embedding_http_contract()
    verify_llm_http_contract()
    verify_ingest_worker_uses_real_parser_contract()
    print("Sprint 19 real parse verification passed.")


if __name__ == "__main__":
    main()

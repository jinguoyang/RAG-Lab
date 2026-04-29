"""Sprint 15 Provider 生产化接入的最小验证脚本。

当前脚本先覆盖 B-065：Provider 配置状态、本地校验和脱敏展示。
它不发起真实网络探测，避免本地开发环境依赖外部服务在线。
"""

from pathlib import Path
import os
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """用明确错误信息标记验收失败点，便于快速定位回归。"""
    if not condition:
        raise AssertionError(message)


def _dependency_by_name(payload: dict, name: str) -> dict:
    """从健康检查响应中取指定依赖，缺失时给出可读失败原因。"""
    for item in payload.get("dependencies", []):
        if item.get("name") == name:
            return item
    raise AssertionError(f"缺少依赖项: {name}")


def verify_provider_config_masking() -> None:
    """校验真实 Provider 配置缺失会降级，且响应体不泄露密钥原文。"""
    os.environ["RAG_LAB_LLM_PROVIDER"] = "openai_compatible"
    os.environ["RAG_LAB_LLM_ENDPOINT"] = "https://llm.example.test/v1?token=should-not-leak"
    os.environ["RAG_LAB_LLM_API_KEY"] = "super-secret-api-key"
    os.environ["RAG_LAB_EMBEDDING_PROVIDER"] = "openai_compatible"
    os.environ["RAG_LAB_EMBEDDING_ENDPOINT"] = ""
    os.environ["RAG_LAB_EMBEDDING_API_KEY"] = ""
    get_settings.cache_clear()

    client = TestClient(create_app())
    response = client.get("/api/v1/health/dependencies")
    _assert(response.status_code == 200, "Provider 配置健康检查接口不可用")

    response_text = response.text
    _assert("super-secret-api-key" not in response_text, "健康检查响应泄露了 LLM API Key")
    _assert("should-not-leak" not in response_text, "健康检查响应泄露了 endpoint query 敏感参数")

    payload = response.json()
    llm = _dependency_by_name(payload, "llm")
    embedding = _dependency_by_name(payload, "embedding")

    _assert(llm["status"] == "configured", "LLM 完整配置应标记为 configured")
    _assert(embedding["status"] == "missing", "Embedding 缺少 endpoint/api key 应标记为 missing")
    _assert(payload["status"] == "degraded", "存在缺失 Provider 配置时整体状态应为 degraded")

    llm_config = {item["key"]: item for item in llm["config"]}
    _assert(llm_config["RAG_LAB_LLM_API_KEY"]["displayValue"] == "***redacted***", "LLM API Key 未脱敏")
    _assert(
        llm_config["RAG_LAB_LLM_ENDPOINT"]["displayValue"] == "https://llm.example.test/v1",
        "LLM endpoint 应移除 query 后展示",
    )


def verify_provider_diagnostics_contract() -> None:
    """校验 LLM、Embedding、Rerank 诊断接口覆盖连通性和限流摘要。"""
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/api/v1/health/provider-diagnostics")
    _assert(response.status_code == 200, "Provider 诊断接口不可用")
    payload = response.json()
    names = {item["name"] for item in payload["diagnostics"]}
    _assert({"llm", "embedding", "rerank"}.issubset(names), "Provider 诊断缺少 LLM/Embedding/Rerank")
    for item in payload["diagnostics"]:
        _assert("connectivityStatus" in item, f"{item['name']} 缺少连通性诊断状态")
        _assert("rateLimitStatus" in item, f"{item['name']} 缺少限流诊断状态")
        _assert("config" in item, f"{item['name']} 缺少脱敏配置摘要")


def verify_index_rebuild_contract() -> None:
    """校验副本重建支持范围收窄和失败原因记录。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/index-sync-jobs/rebuild" in paths,
        "OpenAPI 缺少副本重建入口",
    )
    schemas = schema.get("components", {}).get("schemas", {})
    _assert("IndexSyncRebuildRequest" in schemas, "OpenAPI 缺少 IndexSyncRebuildRequest")

    source = (BACKEND_DIR / "app/services/document_service.py").read_text(encoding="utf-8")
    _assert("document_id: UUID | None = None" in source, "副本重建未支持按文档收窄范围")
    _assert("version_id: UUID | None = None" in source, "副本重建未支持按版本收窄范围")
    _assert("No active chunks found for rebuild scope." in source, "副本重建空范围未记录失败原因")


def main() -> None:
    """执行 Sprint 15 当前已落地范围的验收检查。"""
    verify_provider_config_masking()
    verify_provider_diagnostics_contract()
    verify_index_rebuild_contract()
    print("Sprint 15 provider readiness verification passed.")


if __name__ == "__main__":
    main()

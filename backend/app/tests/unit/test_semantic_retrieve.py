"""语义检索测试：验证 retrieve 接口使用向量检索替代 ILIKE。"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.app_runtime_service import retrieve_app_runtime_evidence


def _make_mock_context(kb_id=None):
    ctx = MagicMock()
    ctx.kb_row = {"kb_id": kb_id or uuid4()}
    ctx.app_row = {"app_id": uuid4()}
    return ctx


class TestSemanticRetrieve:
    """retrieve_app_runtime_evidence 应使用 EmbeddingProvider + DenseRetrievalProvider。"""

    @patch("app.services.app_runtime_service._resolve_runtime_context_without_quota")
    @patch("app.services.app_runtime_service._build_provider_set")
    def test_retrieve_uses_vector_search(self, mock_providers, mock_ctx):
        """当 dense_retrieval_provider != local 时，应走 Milvus 向量检索。"""
        from app.schemas.app_runtime import AppRuntimeRetrieveRequest

        mock_ctx.return_value = _make_mock_context()

        # mock embedding provider
        mock_embedding = MagicMock()
        mock_embedding.embed_query.return_value = [0.1] * 1536

        # mock dense provider
        mock_dense = MagicMock()
        candidate = MagicMock()
        candidate.chunk_id = str(uuid4())
        candidate.content = "test content"
        candidate.metadata = {"chunk_index": 0}
        mock_dense.retrieve.return_value = [candidate]

        mock_provider_set = MagicMock()
        mock_provider_set.embedding = mock_embedding
        mock_provider_set.dense = mock_dense
        mock_providers.return_value = mock_provider_set

        # mock session
        mock_session = MagicMock()
        mock_row = {
            "chunk_id": uuid4(), "chunk_index": 0,
            "content": "test content", "metadata": {},
        }
        mock_session.execute.return_value.mappings.return_value.all.return_value = [mock_row]

        request = AppRuntimeRetrieveRequest(query="test query", topK=5)
        with patch("app.services.app_runtime_service.get_settings") as mock_settings:
            mock_settings.return_value.dense_retrieval_provider = "milvus"
            mock_settings.return_value.provider_top_k = 5
            # Will fail until Step 3 implements the vector path
            result = retrieve_app_runtime_evidence(mock_session, "cred", request)

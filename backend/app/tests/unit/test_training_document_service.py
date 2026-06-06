"""员工培训知识库文档查询服务测试。"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.training_document_service import list_training_documents


def _result(rows: list[dict]) -> MagicMock:
    """构造 SQLAlchemy mappings 查询结果。"""
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    return result


def _mock_context(monkeypatch) -> None:
    """固定培训 App 所属知识库。"""
    monkeypatch.setattr(
        "app.services.training_document_service.resolve_training_context",
        lambda *_args, **_kwargs: SimpleNamespace(kb_row={"kb_id": "kb-001"}),
    )


def test_lists_bound_document_without_chunks(monkeypatch):
    """知识库有效绑定文档即使没有 Chunk，也应出现在可选列表中。"""
    session = MagicMock()
    session.execute.side_effect = [
        _result(
            [
                {
                    "document_id": "doc-001",
                    "name": "呆滞物料管理办法V1.1.docx",
                    "metadata": {},
                }
            ]
        ),
        _result([]),
    ]
    _mock_context(monkeypatch)

    documents = list_training_documents(session, "credential")

    assert [document.documentId for document in documents] == ["doc-001"]
    assert documents[0].title == "呆滞物料管理办法V1.1.docx"
    assert documents[0].summary is None


def test_search_matches_keyword_after_summary_preview(monkeypatch):
    """关键词位于摘要截断范围之外时，仍应返回对应文档。"""
    content = f"{'前置内容' * 50} 呆滞物资处理要求"
    session = MagicMock()
    session.execute.side_effect = [
        _result(
            [
                {
                    "document_id": "doc-001",
                    "name": "周转存贮通用工艺规程.pdf",
                    "metadata": {},
                }
            ]
        ),
        _result(
            [
                {
                    "document_id": "doc-001",
                    "heading": "物资存贮期限",
                    "section": "附录 A",
                    "content": content,
                    "metadata": {},
                    "chunk_index": 10,
                    "row_number": 1,
                }
            ]
        ),
    ]
    _mock_context(monkeypatch)

    documents = list_training_documents(session, "credential", query="呆滞")

    assert [document.documentId for document in documents] == ["doc-001"]
    assert "呆滞" not in (documents[0].summary or "")
